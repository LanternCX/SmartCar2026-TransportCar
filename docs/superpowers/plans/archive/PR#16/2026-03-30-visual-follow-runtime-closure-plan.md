# 主车静止视觉控辅车随动运行收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前唯一主线收口成一套可独立烧录、真实可运行、参数归位清晰，并能做板端与内存留证的主辅车运行框架。

**Architecture:** 先修正主辅车根目录直烧后的导入与入口问题，再让主车双路视觉输入和辅车执行链通过真实串口循环闭合，随后把当前主线需要的 Legacy 参数分别迁入主车与辅车各自的参数入口并接入新运行时，最后补上 smoke、HIL 与内存留证。主辅车参数分别保留各自独立入口，因为两台车本来就允许独立微调；整个实现严格限定在“主车不动、视觉控辅车随动”主线，不顺手恢复主车主动运动、灰度链路或其他 Legacy 模式。

**Tech Stack:** Python 3.10、MicroPython 兼容代码、pytest、mpy-cli、主机侧单元测试、契约测试、HIL 留证文档。

---

## 文件结构与职责

- Modify: `src/master/main.py`
  去掉包名前缀依赖，让 `src/master` 作为设备根目录时能直接启动。
- Modify: `src/master/app.py`
  增加主车真实运行循环入口，负责串口读取、视觉推进和控制发送。
- Modify: `src/master/protocol.py`
  保持当前主线最小协议，同时为主车循环发送提供明确输出接口。
- Modify: `src/master/config.py`
  增加主线运行循环与参数入口需要的配置项。
- Modify: `src/master/hw/uart.py`
  增加面向主车主线循环的逐行读取与发送薄封装。
- Modify: `src/master/vision/parser.py`
  保持视觉报文解析边界，并兼顾板端循环中的逐行消费。
- Modify: `src/master/vision/ingress.py`
  保持双路缓存、选路和新鲜度语义。
- Modify: `src/master/vision/state_machine.py`
  保持当前主线低频阶段判断。
- Modify: `src/master/vision/decision.py`
  继续负责二维控制语义，并接入归位后的参数入口。
- Modify: `src/assistant/main.py`
  去掉包名前缀依赖，让 `src/assistant` 作为设备根目录时能直接启动。
- Modify: `src/assistant/app.py`
  增加辅车真实运行循环入口，负责串口收包、执行和最小状态回传。
- Modify: `src/assistant/config.py`
  增加当前主线执行与参数入口需要的配置项。
- Modify: `src/assistant/hw/uart.py`
  增加面向辅车主线循环的逐行读取与发送薄封装。
- Modify: `src/assistant/hw/motors.py`
  增加当前主线真实执行所需的最小输出接口。
- Modify: `src/assistant/ctrl/chassis.py`
  让辅车执行链真正经过 `hw/` 层，不再只改内存状态。
- Create: `src/master/runtime_params.py`
  主车当前主线参数入口，保证 `src/master` 可独立直烧运行，并允许主车单独微调。
- Create: `src/assistant/runtime_params.py`
  辅车当前主线参数入口，保证 `src/assistant` 可独立直烧运行，并允许辅车单独微调。
- Modify: `tests/unit/master/test_app.py`
  增加主车真实循环入口与根目录导入的失败测试。
- Create: `tests/unit/master/test_runtime_loop.py`
  覆盖主车双路视觉读取、决策和发送链路。
- Modify: `tests/unit/assistant/test_app.py`
  增加辅车真实循环入口与根目录导入的失败测试。
- Create: `tests/unit/assistant/test_runtime_loop.py`
  覆盖辅车收包、执行、超时和状态回传链路。
- Create: `tests/unit/master/test_runtime_params.py`
  锁定主车当前主线参数总入口的具体项名和读取关系。
- Create: `tests/unit/assistant/test_runtime_params.py`
  锁定辅车当前主线参数总入口的具体项名和读取关系。
- Modify: `tests/contract/master_assistant/test_motion_protocol.py`
  保持主辅协议契约，并补主线循环依赖的最小约束。
- Modify: `tests/hil/2026-03-30-visual-center-follow.md`
  补充本轮 smoke、HIL 与内存留证的固定口径。
- Modify: `.mpy-cli.toml`
  保证当前主车板端部署计划对齐当前运行目录；辅车部署步骤通过文档明确说明单独切换方式。

## 实施任务

### Task 1: 收口根目录直烧入口

**Files:**
- Modify: `src/master/main.py`
- Modify: `src/master/app.py`
- Modify: `src/assistant/main.py`
- Modify: `src/assistant/app.py`
- Test: `tests/unit/master/test_app.py`
- Test: `tests/unit/assistant/test_app.py`

- [ ] **Step 1: 先写失败测试，锁定主辅车根目录直烧后不依赖包名前缀**

```python
def test_master_main_can_load_when_master_is_device_root() -> None:
    import sys
    from pathlib import Path

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "master"
    sys.path.insert(0, str(runtime_root))
    try:
        import main  # type: ignore

        assert main.main is not None
    finally:
        sys.path.pop(0)
        sys.modules.pop("main", None)
```

```python
def test_assistant_main_can_load_when_assistant_is_device_root() -> None:
    import sys
    from pathlib import Path

    runtime_root = Path(__file__).resolve().parents[3] / "src" / "assistant"
    sys.path.insert(0, str(runtime_root))
    try:
        import main  # type: ignore

        assert main.main is not None
    finally:
        sys.path.pop(0)
        sys.modules.pop("main", None)
```

- [ ] **Step 2: 运行入口测试，确认当前实现确实失败**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py -q`
Expected: FAIL，提示 `master.*` / `assistant.*` 包导入在根目录直烧场景下不可用。

- [ ] **Step 3: 最小修改主辅车入口与装配导入，让根目录直烧可运行**

```python
# src/master/main.py
from app import MasterApp


def main():
    return MasterApp()
```

```python
# src/assistant/main.py
from app import AssistantApp


def main():
    return AssistantApp()
```

- [ ] **Step 4: 重跑入口测试，确认主辅车根目录直烧入口可导入**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py -q`
Expected: PASS。

### Task 2: 打通主车真实输入输出循环

**Files:**
- Modify: `src/master/app.py`
- Modify: `src/master/hw/uart.py`
- Modify: `src/master/protocol.py`
- Test: `tests/unit/master/test_runtime_loop.py`

- [ ] **Step 1: 先写失败测试，锁定主车会从双路视觉串口读入并向 UART3 发出控制**

```python
def test_master_runtime_loop_reads_vision_and_writes_follow_command() -> None:
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
        "vision=1,camera_id=cam_a,seq=1,valid=1,target=follower,err_x=12,err_y=-6"
    ])
    uart8 = FakeUart()
    uart3 = FakeUart()

    loop = MasterRuntimeLoop({"uart6": uart6, "uart8": uart8, "uart3": uart3})
    loop.step(now_ms=100)

    assert uart3.writes == ["follow=1,seq=1,valid=1,dx=12.000,dy=-6.000"]
```

- [ ] **Step 2: 运行主车循环测试，确认当前还没有真实循环入口**

Run: `python3 -m pytest tests/unit/master/test_runtime_loop.py -q`
Expected: FAIL，提示缺少主车运行循环或 UART 逐行接口。

- [ ] **Step 3: 最小实现主车运行循环与 UART 逐行读写薄封装**

```python
class MasterRuntimeLoop:
    def __init__(self, uart_bundle, app=None):
        self.uart_bundle = uart_bundle
        self.app = app or MasterApp()

    def step(self, now_ms):
        for name in ("uart6", "uart8"):
            line = self.uart_bundle[name].read_line()
            if line:
                result = self.app.step({"uart": name, "line": line, "now_ms": now_ms})
                self.uart_bundle["uart3"].write_line(result["assistant_command"])
                return result
        return self.app.step({"now_ms": now_ms})
```

- [ ] **Step 4: 重跑主车循环测试，确认主车输入输出链路闭合**

Run: `python3 -m pytest tests/unit/master/test_runtime_loop.py tests/unit/master/test_app.py -q`
Expected: PASS。

### Task 3: 打通辅车真实接收执行循环

**Files:**
- Modify: `src/assistant/app.py`
- Modify: `src/assistant/hw/uart.py`
- Modify: `src/assistant/hw/motors.py`
- Modify: `src/assistant/ctrl/chassis.py`
- Test: `tests/unit/assistant/test_runtime_loop.py`

- [ ] **Step 1: 先写失败测试，锁定辅车闭环关键行为：收包、执行、超时停机、最小状态回传**

```python
def test_assistant_runtime_loop_closes_follow_timeout_and_state_chain() -> None:
    from assistant.app import AssistantRuntimeLoop

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

    class FakeMotor:
        def __init__(self):
            self.last_duty = None

        def set_duty(self, duty):
            self.last_duty = duty

    uart3 = FakeUart([
        "follow=1,seq=8,valid=1,dx=0.10,dy=0.00",
        "STATE?",
    ])
    motors = {"m": FakeMotor(), "l": FakeMotor(), "r": FakeMotor()}

    loop = AssistantRuntimeLoop({"uart3": uart3, "motors": motors})
    loop.step(now_ms=0)
    loop.step(now_ms=20)

    assert any(motor.last_duty is not None for motor in motors.values())
    assert "TIMEOUT,last_seq=8" in uart3.writes
    assert any(str(item).startswith("state=1,") for item in uart3.writes)
```

- [ ] **Step 2: 运行辅车循环测试，确认当前执行链还没接到硬件层**

Run: `python3 -m pytest tests/unit/assistant/test_runtime_loop.py -q`
Expected: FAIL。

- [ ] **Step 3: 最小实现辅车运行循环，并让当前主线执行链经过 `hw/motors.py`**

```python
class AssistantRuntimeLoop:
    def __init__(self, hw_bundle, app=None):
        self.hw_bundle = hw_bundle
        self.app = app or AssistantApp()

    def step(self, now_ms):
        line = self.hw_bundle["uart3"].read_line()
        if line:
            reply = self.app.handle_line(line, now_ms=now_ms)
            if reply:
                self.hw_bundle["uart3"].write_line(reply)
        tick_reply = self.app.tick(now_ms=now_ms)
        if tick_reply:
            self.hw_bundle["uart3"].write_line(tick_reply)
```

- [ ] **Step 4: 重跑辅车循环测试，确认接收、执行和回包路径闭合**

Run: `python3 -m pytest tests/unit/assistant/test_runtime_loop.py tests/unit/assistant/test_app.py -q`
Expected: PASS。

### Task 4: 迁移当前主线参数到主辅双入口

**Files:**
- Create: `src/master/runtime_params.py`
- Create: `src/assistant/runtime_params.py`
- Modify: `src/master/config.py`
- Modify: `src/assistant/config.py`
- Modify: `src/master/vision/decision.py`
- Modify: `src/assistant/ctrl/chassis.py`
- Test: `tests/unit/master/test_runtime_params.py`
- Test: `tests/unit/assistant/test_runtime_params.py`

- [ ] **Step 1: 先写失败测试，锁定主辅车根目录下都存在可独立烧录且可分别微调的参数入口**

```python
def test_master_runtime_params_exposes_required_keys() -> None:
    import runtime_params

    expected = {
        "FOLLOW_TIMEOUT_MS",
        "FOLLOW_CONTROL_KP_X",
        "FOLLOW_CONTROL_KP_Y",
        "FOLLOW_CENTER_DEADZONE_PX",
        "CONTROL_TICK_MS",
        "FOLLOW_OUTPUT_LIMIT",
        "PID_MAP",
        "SPEED_FILTER_WINDOW",
        "SPEED_DIFF_MAX_DELTA",
        "GYRO_LPF_ALPHA",
    }

    assert expected.issubset(set(dir(runtime_params)))
    assert set(runtime_params.PID_MAP.keys()) == {"m", "l", "r"}
```

```python
def test_assistant_runtime_params_exposes_required_keys() -> None:
    import runtime_params

    expected = {
        "FOLLOW_TIMEOUT_MS",
        "CONTROL_TICK_MS",
        "FOLLOW_OUTPUT_LIMIT",
        "PID_MAP",
        "SPEED_FILTER_WINDOW",
        "SPEED_DIFF_MAX_DELTA",
        "GYRO_LPF_ALPHA",
    }

    assert expected.issubset(set(dir(runtime_params)))
    assert set(runtime_params.PID_MAP.keys()) == {"m", "l", "r"}
```

```python
def test_master_and_assistant_runtime_params_are_independent() -> None:
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "src"
    master_spec = importlib.util.spec_from_file_location(
        "master_runtime_params", root / "master" / "runtime_params.py"
    )
    assistant_spec = importlib.util.spec_from_file_location(
        "assistant_runtime_params", root / "assistant" / "runtime_params.py"
    )
    master_params = importlib.util.module_from_spec(master_spec)
    assistant_params = importlib.util.module_from_spec(assistant_spec)
    master_spec.loader.exec_module(master_params)
    assistant_spec.loader.exec_module(assistant_params)

    assert master_params is not assistant_params
```

- [ ] **Step 2: 运行参数测试，确认当前没有统一入口**

Run: `python3 -m pytest tests/unit/master/test_runtime_params.py tests/unit/assistant/test_runtime_params.py -q`
Expected: FAIL。

- [ ] **Step 3: 最小创建主辅参数入口，并让两边运行时改从各自根目录读取**

```python
# src/master/runtime_params.py
FOLLOW_TIMEOUT_MS = 150
FOLLOW_CONTROL_KP_X = 1.0
FOLLOW_CONTROL_KP_Y = 1.0
FOLLOW_CENTER_DEADZONE_PX = 8.0
CONTROL_TICK_MS = 5
FOLLOW_OUTPUT_LIMIT = 10000
PID_MAP = {"m": (100, 500, 1), "l": (100, 500, 1), "r": (100, 500, 1)}
SPEED_FILTER_WINDOW = 5
SPEED_DIFF_MAX_DELTA = 5.0
GYRO_LPF_ALPHA = 0.2
YAW_KP = 0.16  # 当前主线未启用
YAW_KI = 0.1   # 当前主线未启用
YAW_I_MAX = 100.0  # 当前主线未启用
AUTO_OMEGA_MAX = 15.0  # 当前主线未启用
```

```python
# src/assistant/runtime_params.py
FOLLOW_TIMEOUT_MS = 150
CONTROL_TICK_MS = 5
FOLLOW_OUTPUT_LIMIT = 10000
PID_MAP = {"m": (100, 500, 1), "l": (100, 500, 1), "r": (100, 500, 1)}
SPEED_FILTER_WINDOW = 5
SPEED_DIFF_MAX_DELTA = 5.0
GYRO_LPF_ALPHA = 0.2
YAW_KP = 0.16  # 当前主线未启用
YAW_KI = 0.1   # 当前主线未启用
YAW_I_MAX = 100.0  # 当前主线未启用
AUTO_OMEGA_MAX = 15.0  # 当前主线未启用
```

- [ ] **Step 4: 重跑参数测试，确认当前主线参数已经归位并可读取**

Run: `python3 -m pytest tests/unit/master/test_runtime_params.py tests/unit/assistant/test_runtime_params.py -q`
Expected: PASS。

### Task 5: 让参数逐项进入当前主线运行链

**Files:**
- Modify: `src/master/runtime_params.py`
- Modify: `src/assistant/runtime_params.py`
- Modify: `src/master/vision/state_machine.py`
- Modify: `src/master/vision/decision.py`
- Modify: `src/assistant/ctrl/chassis.py`
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/assistant/test_app.py`

- [ ] **Step 1: 先写失败测试，逐项锁定 spec 点名参数会被真实读取**

```python
def test_master_app_uses_runtime_param_deadzone() -> None:
    import master.runtime_params as runtime_params
    from master.app import MasterApp

    runtime_params.FOLLOW_CENTER_DEADZONE_PX = 20.0
    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    result = app.step({
        "uart": "uart6",
        "line": "vision=1,camera_id=cam_a,seq=10,valid=1,target=follower,err_x=12,err_y=0",
    })

    assert result["phase"] == "CENTER_HOLD"
```

```python
def test_master_app_uses_runtime_param_follow_timeout() -> None:
    import master.runtime_params as runtime_params
    from master.app import MasterApp

    runtime_params.FOLLOW_TIMEOUT_MS = 10
    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step({
        "uart": "uart6",
        "line": "vision=1,camera_id=cam_a,seq=1,valid=1,target=follower,err_x=12,err_y=0",
        "now_ms": 0,
    })
    result = app.step({"now_ms": 20})

    assert result["phase"] == "MARKER_MISSING"
```

```python
def test_master_app_uses_runtime_param_control_gains() -> None:
    import master.runtime_params as runtime_params
    from master.app import MasterApp

    runtime_params.FOLLOW_CONTROL_KP_X = 2.0
    runtime_params.FOLLOW_CONTROL_KP_Y = 3.0
    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    result = app.step({
        "uart": "uart6",
        "line": "vision=1,camera_id=cam_a,seq=1,valid=1,target=follower,err_x=2,err_y=-1",
    })

    assert result["assistant_command"] == "follow=1,seq=1,valid=1,dx=4.000,dy=-3.000"
```

```python
def test_assistant_app_uses_runtime_param_follow_timeout() -> None:
    import assistant.runtime_params as runtime_params
    from assistant.app import AssistantApp

    runtime_params.FOLLOW_TIMEOUT_MS = 10
    app = AssistantApp(timeout_ms=runtime_params.FOLLOW_TIMEOUT_MS)
    app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=0)

    assert app.tick(now_ms=20) == "TIMEOUT,last_seq=8"
```

```python
def test_assistant_runtime_uses_runtime_param_output_limit() -> None:
    import assistant.runtime_params as runtime_params
    from assistant.ctrl.chassis import ChassisRuntime
    from assistant.protocol import parse_command

    runtime_params.FOLLOW_OUTPUT_LIMIT = 123
    runtime = ChassisRuntime(timeout_ms=runtime_params.FOLLOW_TIMEOUT_MS)
    runtime.apply_command(parse_command("follow=1,seq=1,valid=1,dx=999.0,dy=0.0"), now_ms=0)

    assert runtime.state.velocity_command[0] <= 123
```

```python
def test_assistant_runtime_exposes_runtime_pid_and_filter_params() -> None:
    import assistant.runtime_params as runtime_params

    assert runtime_params.PID_MAP["m"] == (100, 500, 1)
    assert runtime_params.PID_MAP["l"] == (100, 500, 1)
    assert runtime_params.PID_MAP["r"] == (100, 500, 1)
    assert runtime_params.SPEED_FILTER_WINDOW == 5
    assert runtime_params.SPEED_DIFF_MAX_DELTA == 5.0
    assert runtime_params.GYRO_LPF_ALPHA == 0.2
```

```python
def test_assistant_runtime_reads_runtime_pid_and_filter_params() -> None:
    import assistant.runtime_params as runtime_params
    from assistant.ctrl.chassis import ChassisRuntime

    runtime_params.PID_MAP = {"m": (1, 2, 3), "l": (4, 5, 6), "r": (7, 8, 9)}
    runtime_params.SPEED_FILTER_WINDOW = 9
    runtime_params.SPEED_DIFF_MAX_DELTA = 1.5
    runtime_params.GYRO_LPF_ALPHA = 0.5

    runtime = ChassisRuntime(timeout_ms=runtime_params.FOLLOW_TIMEOUT_MS)

    assert runtime.pid_map == runtime_params.PID_MAP
    assert runtime.speed_filter_window == 9
    assert runtime.speed_diff_max_delta == 1.5
    assert runtime.gyro_lpf_alpha == 0.5
```

- [ ] **Step 2: 运行主线参数接入测试，确认当前实现仍使用散落旧值**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py tests/unit/master/test_runtime_params.py tests/unit/assistant/test_runtime_params.py -q`
Expected: FAIL。

- [ ] **Step 3: 最小修改状态机、决策和辅车执行链，让主线参数统一从各自新入口读取**

```python
import runtime_params


class MarkerStateMachine:
    def __init__(self, deadzone_px=None):
        if deadzone_px is None:
            deadzone_px = runtime_params.FOLLOW_CENTER_DEADZONE_PX
        self.deadzone_px = float(deadzone_px)
```

```python
dx = float(observation.get("err_x", 0.0)) * runtime_params.FOLLOW_CONTROL_KP_X
dy = float(observation.get("err_y", 0.0)) * runtime_params.FOLLOW_CONTROL_KP_Y
```

```python
limited_dx = max(-runtime_params.FOLLOW_OUTPUT_LIMIT, min(runtime_params.FOLLOW_OUTPUT_LIMIT, command.dx))
```

```python
self.pid_map = dict(runtime_params.PID_MAP)
self.speed_filter_window = int(runtime_params.SPEED_FILTER_WINDOW)
self.speed_diff_max_delta = float(runtime_params.SPEED_DIFF_MAX_DELTA)
self.gyro_lpf_alpha = float(runtime_params.GYRO_LPF_ALPHA)
```

- [ ] **Step 4: 重跑主线参数接入测试，确认参数真正进入运行链**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_app.py tests/unit/master/test_runtime_params.py tests/unit/assistant/test_runtime_params.py -q`
Expected: PASS。

### Task 6: 固定板端前置确认与 smoke 入口

**Files:**
- Modify: `.mpy-cli.toml`
- Modify: `tests/hil/2026-03-30-visual-center-follow.md`
- Modify: `tools/run_stage2_smoke.py`

- [ ] **Step 1: 先写失败测试，锁定 smoke 结果必须记录固定留证字段**

```python
def test_stage2_smoke_result_requires_memory_and_diag_fields() -> None:
    from tools.run_stage2_smoke import Stage2RunResult

    details = {
        "memory": {
            "mem_free_after_import": "1",
            "mem_free_after_core_init": "1",
            "mem_free_after_feature_init": "1",
            "mem_free_runtime_idle": "1",
        },
        "diag_survival": {"ok": "1"},
    }

    result = Stage2RunResult("ok", "ok", details)
    assert "memory" in result.details
    assert "diag_survival" in result.details
```

- [ ] **Step 2: 运行 smoke 相关测试，确认当前留证口径还不完整**

Run: `python3 -m pytest tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: FAIL。

- [ ] **Step 3: 最小更新部署配置、smoke 工具和 HIL 文档，记录主车部署入口、辅车部署入口和固定留证字段**

```text
- 主车部署入口
- 辅车部署入口
- 主车启动证据
- 辅车启动证据
- 串口收发证据
- 主线现象记录
- mem_free_after_import
- mem_free_after_core_init
- mem_free_after_feature_init
- mem_free_runtime_idle
- diag_survival
```

- [ ] **Step 4: 重跑 smoke 相关测试，确认留证口径已收口**

Run: `python3 -m pytest tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: PASS。

### Task 7: 写清板端与内存留证说明

**Files:**
- Modify: `tests/hil/2026-03-30-visual-center-follow.md`

- [ ] **Step 1: 在 HIL 文档中加入设备前置确认说明，避免默认假设端口和视觉链路已在线**

- [ ] **Step 2: 为主车板端 smoke 写清楚“当前写了什么、板上应该看到什么表现”**

```text
- 主车部署后会持续读取 UART6/UART8
- 有有效色标时应通过 UART3 持续发出 follow 控制
- 无效或超时后应改发 valid=0 的保持控制
```

- [ ] **Step 3: 为辅车板端 smoke 写清楚“当前写了什么、板上应该看到什么表现”**

```text
- 辅车收到 follow 后应进入 BUSY
- 超时后应停住并回 TIMEOUT
- 查询状态时应看到 last_seq 与 follow_active
```

- [ ] **Step 4: 为 Legacy 基线和新框架基线分别写清同口径内存采集说明**

```text
- Legacy 基线: 主车不动, 只保留视觉接收与辅车控制链
- 新框架基线: 主车不动, 只保留当前主线常驻对象
- 同时记录 mem_free_after_import / mem_free_after_core_init / mem_free_after_feature_init / mem_free_runtime_idle / diag_survival
```

### Task 8: 运行最终验证集

**Files:**
- Verify: `tests/unit/**/*.py`
- Verify: `tests/contract/master_assistant/test_motion_protocol.py`

- [ ] **Step 1: 运行目标验证集，确认主机侧主线、契约和参数收口全部通过**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS。
