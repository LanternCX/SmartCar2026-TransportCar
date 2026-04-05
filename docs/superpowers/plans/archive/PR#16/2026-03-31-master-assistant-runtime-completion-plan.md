# 主辅包独立直烧运行补全实施计划

> **给执行代理的要求：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项实现本计划，步骤使用复选框 `- [ ]` 跟踪。

**目标：** 让 `src/master` 与 `src/assistant` 都成为可独立上传、上电即进入持续运行、并在联合运行时形成完整控制链路的真实板端运行包。

**架构：** 先把主辅 `main.py` 从“返回对象”收紧为“正常分支直接进入持续循环”的真实入口，同时保留主机侧可控测试钩子；再修辅车 owner 的完整硬件装配边界，禁止入口层回写半套装配；最后补齐双边独立上传与 Stage 2 smoke 口径，让“主车独立”“辅车独立”“双边联合”三层验证边界清晰分离。

**技术栈：** Python 3.10、MicroPython 兼容代码、pytest、mpy-cli、Stage 2 smoke、HIL 留证文档。

---

## 文件结构与职责

- Modify: `src/master/main.py`
  把主车入口改成“测试可控 + 板端持续循环”的真实单入口，并继续保留按钮脚本分发。
- Modify: `src/assistant/main.py`
  把辅车入口改成“测试可控 + 板端持续循环”的真实单入口，并恢复完整硬件装配边界。
- Modify: `src/master/app.py`
  补主车运行循环的持续执行入口，避免板端语义只停留在单步对象。
- Modify: `src/assistant/app.py`
  移除把半套装配回写到 owner 的行为，保证运行时 owner 持有完整硬件边界。
- Modify: `tests/unit/master/test_app.py`
  先写主车入口持续循环与主车独立根目录执行语义的失败测试。
- Modify: `tests/unit/assistant/test_app.py`
  先写辅车入口持续循环、完整装配边界与辅车独立根目录执行语义的失败测试。
- Modify: `tests/unit/master/test_runtime_loop.py`
  为主车连续循环行为补最小单元测试。
- Modify: `tests/unit/assistant/test_runtime_loop.py`
  为辅车连续循环与完整装配持有补最小单元测试。
- Modify: `.mpy-cli.toml`
  明确默认上传口径的限制，避免继续把“双边独立直烧”误判成已完成。
- Modify: `tools/run_stage2_smoke.py`
  让工具显式支持主车与辅车两套根目录口径，而不是只默认主车。
- Create: `tests/unit/tools/test_run_stage2_smoke.py`
  为双边 smoke 入口参数和失败归因先写失败测试。
- Modify: `tests/hil/2026-03-30-visual-center-follow.md`
  补联合链路观察项，明确“主车持续读相机并控辅车”“上电默认航向保持”是必须留证项。

## 实施任务

### TDD 固定收口要求

- [ ] 每个任务必须严格按 `RED -> GREEN -> REFACTOR` 执行
- [ ] 每个失败测试都要先单独运行，确认失败原因正确
- [ ] 每个任务完成后至少重跑该任务对应测试集
- [ ] 只有在主机侧验证通过后，才能进入工具口径或 HIL 文档补充

### Task 1: 把主辅 `main.py` 收口为真实持续运行入口

**Files:**
- Modify: `src/master/main.py`
- Modify: `src/assistant/main.py`
- Modify: `src/master/app.py`
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/assistant/test_app.py`

- [ ] **Step 1: 先写失败测试，锁定正常分支会直接进入持续循环而不是只返回对象**

```python
def test_master_main_runs_runtime_loop_until_step_limit() -> None:
    from master.main import main

    class FakeLoop:
        def __init__(self):
            self.calls = []

        def step(self, now_ms):
            self.calls.append(now_ms)

    loop = FakeLoop()
    result = main(
        button_reader=lambda pin: False,
        loop_factory=lambda: loop,
        tick_source=lambda: 100,
        step_limit=3,
    )

    assert result == loop
    assert loop.calls == [100, 100, 100]
```

```python
def test_assistant_main_runs_runtime_loop_until_step_limit() -> None:
    from assistant.main import main

    class FakeLoop:
        def __init__(self):
            self.calls = []

        def step(self, now_ms):
            self.calls.append(now_ms)

    loop = FakeLoop()
    result = main(
        button_reader=lambda pin: False,
        loop_factory=lambda: loop,
        tick_source=lambda: 200,
        step_limit=2,
    )

    assert result == loop
    assert loop.calls == [200, 200]
```

- [ ] **Step 2: 运行入口测试，确认当前实现因只返回对象而失败**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py -q`
Expected: FAIL，暴露正常分支没有进入持续循环。

- [ ] **Step 3: 写最小实现，让 `main.py` 在正常分支直接驱动循环，同时保留测试钩子**

```python
def _run_loop(loop, tick_source, step_limit=None):
    steps = 0
    while step_limit is None or steps < step_limit:
        loop.step(tick_source())
        steps += 1
    return loop


def main(button_reader=None, loop_factory=None, tick_source=None, step_limit=None):
    if _read_button_state("C8", button_reader):
        ...
    loop = loop_factory() if loop_factory is not None else _build_runtime_loop()
    return _run_loop(loop, tick_source or _ticks_ms, step_limit=step_limit)
```

- [ ] **Step 4: 重跑入口测试，确认正常分支已经进入持续循环**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py -q`
Expected: PASS。

- [ ] **Step 5: 做最小重整并再次确认通过**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py -q`
Expected: PASS。

### Task 2: 恢复辅车运行时 owner 的完整硬件装配边界

**Files:**
- Modify: `src/assistant/main.py`
- Modify: `src/assistant/app.py`
- Modify: `tests/unit/assistant/test_app.py`
- Modify: `tests/unit/assistant/test_runtime_loop.py`

- [ ] **Step 1: 先写失败测试，锁定辅车入口与 owner 都持有完整硬件装配**

```python
def test_assistant_main_passes_full_hw_bundle_to_runtime_loop() -> None:
    from assistant.main import main

    captured = {}
    full_bundle = {
        "uart": {"uart3": object()},
        "motors": {"m": object()},
        "encoders": {"e": object()},
        "imu": {"heading_deg": lambda: 0.0},
    }

    class FakeLoop:
        def __init__(self, hw_bundle):
            captured["hw_bundle"] = hw_bundle

        def step(self, now_ms):
            return None

    result = main(
        button_reader=lambda pin: False,
        loop_factory=lambda: FakeLoop(full_bundle),
        tick_source=lambda: 0,
        step_limit=1,
    )

    assert result is not None
    assert captured["hw_bundle"] is full_bundle
    assert "imu" in captured["hw_bundle"]
    assert "encoders" in captured["hw_bundle"]
```

```python
def test_assistant_runtime_loop_keeps_full_hw_bundle_on_runtime_owner() -> None:
    from assistant.app import AssistantRuntimeLoop

    full_bundle = {
        "uart": {"uart3": object()},
        "motors": {"m": object()},
        "encoders": {"e": object()},
        "imu": {"heading_deg": lambda: 0.0},
    }
    loop = AssistantRuntimeLoop(full_bundle)

    assert loop.app.runtime.core.hw_bundle is full_bundle
```

- [ ] **Step 2: 运行辅车入口与运行循环测试，确认当前实现仍在裁剪装配边界**

Run: `python3 -m pytest tests/unit/assistant/test_app.py tests/unit/assistant/test_runtime_loop.py -q`
Expected: FAIL，暴露入口只传了 `uart3 + motors`，并把半套装配回写给 owner。

- [ ] **Step 3: 写最小实现，去掉入口裁剪与 owner 回写半套装配行为**

```python
def _build_runtime_loop():
    hw_bundle = build_hw_bundle()
    return AssistantRuntimeLoop(hw_bundle)


class AssistantRuntimeLoop:
    def __init__(self, hw_bundle, app=None):
        self.hw_bundle = hw_bundle
        self.app = app or AssistantApp(hw_bundle=hw_bundle)
```

- [ ] **Step 4: 重跑辅车相关测试，确认完整装配边界恢复**

Run: `python3 -m pytest tests/unit/assistant/test_app.py tests/unit/assistant/test_runtime_loop.py -q`
Expected: PASS。

- [ ] **Step 5: 做最小重整并再次确认通过**

Run: `python3 -m pytest tests/unit/assistant/test_app.py tests/unit/assistant/test_runtime_loop.py -q`
Expected: PASS。

### Task 3: 把主车持续读视觉并控辅车的入口语义锁成测试

**Files:**
- Modify: `tests/unit/master/test_runtime_loop.py`
- Modify: `tests/unit/master/test_app.py`
- Modify: `src/master/app.py`

- [ ] **Step 1: 先写失败测试，锁定主车持续循环会重复读取视觉并持续向辅车写控制**

```python
def test_master_runtime_loop_reads_multiple_frames_across_multiple_steps() -> None:
    from master.app import MasterRuntimeLoop

    class FakeUart:
        def __init__(self, lines=None):
            self.lines = list(lines or [])
            self.writes = []

        def read_line(self):
            if not self.lines:
                return None
            return self.lines.pop(0)

        def write_line(self, payload):
            self.writes.append(payload)

    uart6 = FakeUart([
        "vision=1,camera_id=cam_a,seq=1,valid=1,target=follower,err_x=12,err_y=0",
        "vision=1,camera_id=cam_a,seq=2,valid=1,target=follower,err_x=8,err_y=0",
    ])
    uart8 = FakeUart()
    uart3 = FakeUart()

    loop = MasterRuntimeLoop({"uart6": uart6, "uart8": uart8, "uart3": uart3})
    loop.step(now_ms=100)
    loop.step(now_ms=110)

    assert len(uart3.writes) == 2
    assert uart3.writes[0] != ""
    assert uart3.writes[1] != ""
```

- [ ] **Step 2: 运行主车运行循环测试，确认当前收口不够清晰或行为未被锁定**

Run: `python3 -m pytest tests/unit/master/test_runtime_loop.py tests/unit/master/test_app.py -q`
Expected: FAIL 或测试缺失，暴露持续循环语义未被锁定。

- [ ] **Step 3: 写最小实现或重整，让主车循环入口和测试语义一致**

```python
class MasterRuntimeLoop:
    def step(self, now_ms):
        ...
        self.uart_bundle["uart3"].write_line(result["assistant_command"])
        return result
```

- [ ] **Step 4: 重跑主车入口与运行循环测试**

Run: `python3 -m pytest tests/unit/master/test_runtime_loop.py tests/unit/master/test_app.py -q`
Expected: PASS。

- [ ] **Step 5: 做最小重整并再次确认通过**

Run: `python3 -m pytest tests/unit/master/test_runtime_loop.py tests/unit/master/test_app.py -q`
Expected: PASS。

### Task 4: 补齐主辅双边独立上传与 Stage 2 smoke 口径

**Files:**
- Modify: `.mpy-cli.toml`
- Modify: `tools/run_stage2_smoke.py`
- Create: `tests/unit/tools/test_run_stage2_smoke.py`

- [ ] **Step 1: 先写失败测试，锁定 smoke 工具必须显式支持 `master` 与 `assistant` 两种运行根目录**

```python
def test_build_probe_commands_supports_master_source_dir() -> None:
    from tools.run_stage2_smoke import build_probe_commands

    commands = build_probe_commands(port="/dev/null", source_dir="src/master")

    assert any("src/master" in " ".join(command) for command in commands)
```

```python
def test_build_probe_commands_supports_assistant_source_dir() -> None:
    from tools.run_stage2_smoke import build_probe_commands

    commands = build_probe_commands(port="/dev/null", source_dir="src/assistant")

    assert any("src/assistant" in " ".join(command) for command in commands)
```

- [ ] **Step 2: 运行 smoke 工具测试，确认当前实现只默认主车路径**

Run: `python3 -m pytest tests/unit/tools/test_run_stage2_smoke.py -q`
Expected: FAIL，暴露工具没有双边根目录参数。

- [ ] **Step 3: 写最小实现，让 smoke 工具显式接收运行根目录参数，并更新默认配置说明**

```python
def build_probe_commands(port, source_dir):
    common = ["--port", port, "--no-interactive", "--yes", "--source-dir", source_dir]
    ...
```

- [ ] **Step 4: 重跑 smoke 工具测试**

Run: `python3 -m pytest tests/unit/tools/test_run_stage2_smoke.py -q`
Expected: PASS。

- [ ] **Step 5: 做最小重整并再次确认通过**

Run: `python3 -m pytest tests/unit/tools/test_run_stage2_smoke.py -q`
Expected: PASS。

### Task 5: 统一主机侧回归并补 HIL 留证口径

**Files:**
- Modify: `tests/hil/2026-03-30-visual-center-follow.md`

- [ ] **Step 1: 补 HIL 文档条目，明确三层验证边界与必须观察项**

```text
- 主车独立层：上电后持续接收 UART6/UART8，主循环不退出
- 辅车独立层：上电后持续监听 UART3，默认航向保持开启
- 联合链路层：主车持续读摄像头并控制辅车，辅车随动且朝向稳定
```

- [ ] **Step 2: 运行主机侧联合回归，确认本轮代码层收口通过**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS。

- [ ] **Step 3: 如有设备条件，再执行双边 Stage 2 smoke**

Run: `python3 tools/run_stage2_smoke.py --port <port> --source-dir src/master`
Expected: 主车独立 smoke 成功。

Run: `python3 tools/run_stage2_smoke.py --port <port> --source-dir src/assistant`
Expected: 辅车独立 smoke 成功。

- [ ] **Step 4: 更新 HIL 留证结果，不把 Stage 2 误写成联合链路完成**

## 完成标准

- 主车 `main.py` 正常分支上电后直接进入持续循环，不再只是返回对象
- 辅车 `main.py` 正常分支上电后直接进入持续循环，且 owner 持有完整装配
- 主车持续读取视觉输入并持续向辅车下发控制的语义被测试锁定
- Stage 2 工具显式区分主车与辅车根目录，不能再只默认主车
- 主机侧回归通过，设备侧 smoke 与 HIL 留证口径清晰分层
