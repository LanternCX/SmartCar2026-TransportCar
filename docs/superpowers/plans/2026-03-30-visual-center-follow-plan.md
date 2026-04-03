# 辅车色标二维回中 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现当前阶段唯一主线：主车持续接收两路视觉中的辅车色标位置，主车自己不主动运动，只根据二维偏差向辅车下发 `dx/dy` 控制，辅车执行随动，把色标拉回中心；进入固定像素死区后保持，色标丢失立即停住。

**Architecture:** 先确认并固化双 UART 视觉误差到统一车体 `x/y` 方向的归一化规则，再把当前主线协议与主机侧逻辑收缩成最小闭环，最后改写辅车执行侧与最小状态回传。当前阶段不实现灰度链路，不实现角度控制，不实现主车主动运动，也不把入口重构并入本次最小闭环任务。

**Tech Stack:** Python 3.8+、MicroPython 兼容代码、pytest、主机侧单元测试与契约测试。

---

## 文件结构与职责

- 修改：`src/master/protocol.py`
  当前阶段主辅协议构造，收口为 `seq + valid + dx + dy` 的最小主线。
- 修改：`src/assistant/protocol.py`
  解析当前阶段最小跟随协议，不再把 `d_angle` 当作当前主线输入。
- 修改：`src/master/decision.py`
  只根据统一后的二维误差生成 `dx/dy`，并显式处理死区保持与无效目标。
- 修改：`src/master/app.py`
  编排低频状态判断与高频控制目标刷新，不让主车自身动作进入当前默认链路。
- 修改：`src/master/vision_ingress.py`
  支持双 UART 持续接收、误差方向归一化、最新数据优先、同样新鲜时 `UART6` 固定优先。
- 修改：`src/master/vision_state_machine.py`
  收缩为 `MARKER_MISSING / TRACKING / CENTER_HOLD` 最小低频状态机。
- 修改：`src/assistant/motion_runtime.py`
  辅车只消费二维平移控制量，保持最小状态回传与超时停机。
- 修改：`src/assistant/status.py`
  输出最小状态面，并显式带上 `last_seq`。
- 修改：`tests/unit/master/test_vision_ingress.py`
  验证双 UART 输入、新鲜度比较、`UART6` 固定优先与无效输入归零。
- 修改：`tests/unit/master/test_vision_state_machine.py`
  验证最小低频状态机只处理 `MARKER_MISSING / TRACKING / CENTER_HOLD`。
- 修改：`tests/unit/master/test_decision.py`
  验证二维偏差到 `dx/dy` 的映射、死区保持、无效目标立即归零。
- 修改：`tests/unit/master/test_app.py`
  验证当前阶段主车只输出辅车二维跟随命令，不驱动自身动作。
- 修改：`tests/unit/assistant/test_protocol.py`
  验证辅车协议解析只关注当前阶段二维平移主线。
- 修改：`tests/unit/assistant/test_motion_runtime.py`
  验证辅车消费二维跟随命令、无效目标立即保持、超时停机。
- Create: `tests/unit/assistant/test_status.py`
  固定最小状态回传文本，避免只在说明里保留契约。
- 修改：`tests/contract/master_assistant/test_motion_protocol.py`
  固化当前阶段最小主辅协议与最小状态回传契约。
- Create: `tests/hil/2026-03-30-visual-center-follow.md`
  记录当前阶段最小上板验证步骤、预期与结果占位。

## 实施任务

### Task 1: 固化双 UART 误差归一化门禁

**Files:**
- Modify: `src/master/vision_ingress.py`
- Test: `tests/unit/master/test_vision_ingress.py`

- [ ] **Step 1: 先写失败测试，固定双路误差要归一到同一 `x/y` 语义**

```python
def test_prepare_observation_requires_both_uarts_to_expose_same_xy_semantics() -> None:
    from master.vision_ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    uart6 = ingress.prepare_observation({
        "uart": "uart6",
        "line": "vision=1,camera_id=cam_a,seq=2,valid=1,target=follower,err_x=10,err_y=5",
    })
    uart8 = ingress.prepare_observation({
        "uart": "uart8",
        "line": "vision=1,camera_id=cam_b,seq=3,valid=1,target=follower,err_x=10,err_y=5",
    })

    assert (uart6["err_x"], uart6["err_y"]) == (uart8["err_x"], uart8["err_y"])
```

- [ ] **Step 2: 运行测试确认当前实现还没有把归一化行为锁死**

Run: `python3 -m pytest tests/unit/master/test_vision_ingress.py -q`
Expected: FAIL，提示当前实现尚未把双路输入锁定到同一语义下。

- [ ] **Step 3: 最小实现统一误差入口，并把当前协议要求写死为“两路 UART 都直接输出已经归一到 `x+ = 右移`、`y+ = 前进` 语义的 `err_x/err_y`”**

```python
def _normalize_marker_error(self, uart_name: str, err_x: float, err_y: float):
    # 当前阶段要求双路视觉都直接输出统一语义，本层只做入口收口，不再二次翻转。
    return float(err_x), float(err_y)
```

- [ ] **Step 4: 重跑测试，确认双路都经由统一入口归一化**

Run: `python3 -m pytest tests/unit/master/test_vision_ingress.py -q`
Expected: PASS。

- [ ] **Step 5: 提交误差归一化门禁**

```bash
git add tests/unit/master/test_vision_ingress.py src/master/vision_ingress.py
git commit -m "test: lock marker error normalization semantics"
```

### Task 2: 收缩当前阶段主辅协议

**Files:**
- Modify: `src/master/protocol.py`
- Modify: `src/assistant/protocol.py`
- Test: `tests/contract/master_assistant/test_motion_protocol.py`
- Test: `tests/unit/assistant/test_protocol.py`

- [ ] **Step 1: 先写失败测试，固定当前阶段最小协议**

```python
def test_master_assistant_motion_protocol_contract() -> None:
    from master.protocol import build_follow_command
    from assistant.protocol import parse_command

    command = build_follow_command(seq=7, valid=1, dx=0.10, dy=0.0)
    parsed = parse_command(command)

    assert parsed.kind == "follow"
    assert parsed.seq == 7
    assert parsed.valid == 1
    assert parsed.dx == 0.10
    assert parsed.dy == 0.0
```

- [ ] **Step 2: 运行单测确认现状失败**

Run: `python3 -m pytest tests/contract/master_assistant/test_motion_protocol.py tests/unit/assistant/test_protocol.py -q`
Expected: 由于当前协议仍带 `d_angle` 或测试断言不匹配而失败。

- [ ] **Step 3: 最小修改协议构造与解析**

```python
def build_follow_command(seq: int, valid: int, dx: float, dy: float) -> str:
    return "follow=1,seq=%d,valid=%d,dx=%.3f,dy=%.3f" % (
        int(seq),
        1 if int(valid) else 0,
        float(dx),
        float(dy),
    )
```

```python
if payload.get("follow") == "1":
    return Command(
        kind="follow",
        seq=int(payload["seq"]),
        valid=int(payload["valid"]),
        dx=float(payload.get("dx", 0.0)),
        dy=float(payload.get("dy", 0.0)),
    )
```

- [ ] **Step 4: 重跑协议相关测试**

Run: `python3 -m pytest tests/contract/master_assistant/test_motion_protocol.py tests/unit/assistant/test_protocol.py -q`
Expected: PASS。

- [ ] **Step 5: 提交这个最小协议收缩**

```bash
git add tests/contract/master_assistant/test_motion_protocol.py tests/unit/assistant/test_protocol.py src/master/protocol.py src/assistant/protocol.py
git commit -m "feat: shrink follow protocol to planar control"
```

### Task 3: 固化主车双 UART 视觉接入与选路规则

**Files:**
- Modify: `src/master/vision_ingress.py`
- Test: `tests/unit/master/test_vision_ingress.py`

- [ ] **Step 1: 先写失败测试，锁定“最新优先、同样新鲜时 UART6 优先”**

```python
def test_select_current_target_prefers_uart6_when_reports_are_equally_fresh() -> None:
    from master.vision_ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))
    ingress.prepare_observation({
        "uart": "uart8",
        "line": "vision=1,camera_id=cam_b,seq=5,valid=1,target=follower,err_x=10,err_y=5",
    })
    ingress.prepare_observation({
        "uart": "uart6",
        "line": "vision=1,camera_id=cam_a,seq=5,valid=1,target=follower,err_x=1,err_y=2",
    })

    assert ingress.select_current_target()["camera_id"] == "cam_a"
```

- [ ] **Step 2: 运行视觉入口测试，确认新增断言失败**

Run: `python3 -m pytest tests/unit/master/test_vision_ingress.py -q`
Expected: FAIL，提示缺少统一选路或优先级行为。

- [ ] **Step 3: 最小实现双 UART 最新结果缓存与固定优先级选路**

```python
def select_current_target(self):
    fresh_items = []
    for uart_name in ("uart6", "uart8"):
        item = self._latest_by_uart.get(uart_name)
        if item and item.get("source_status") == "active":
            fresh_items.append(item)
    if not fresh_items:
        return self._build_idle_observation("missing")
    fresh_items.sort(key=lambda item: (int(item["vision_seq"]), item["active_uart"] == "uart6"), reverse=True)
    return dict(fresh_items[0])
```

- [ ] **Step 4: 重跑视觉入口测试**

Run: `python3 -m pytest tests/unit/master/test_vision_ingress.py -q`
Expected: PASS。

- [ ] **Step 5: 提交双 UART 选路收口**

```bash
git add tests/unit/master/test_vision_ingress.py src/master/vision_ingress.py
git commit -m "feat: prioritize fresh uart6 vision reports"
```

### Task 4: 固化低频状态机与高频控制解耦

**Files:**
- Modify: `src/master/vision_state_machine.py`
- Modify: `src/master/decision.py`
- Test: `tests/unit/master/test_vision_state_machine.py`
- Test: `tests/unit/master/test_decision.py`

- [ ] **Step 1: 先写失败测试，固定最小状态机与死区保持**

```python
def test_state_machine_enters_center_hold_when_error_is_inside_deadzone() -> None:
    from master.vision_state_machine import MarkerStateMachine

    machine = MarkerStateMachine(deadzone_px=8.0)

    result = machine.step(valid=1, err_x=3.0, err_y=-4.0)

    assert result["phase"] == "center_hold"
```

```python
def test_decision_outputs_zero_planar_command_when_target_is_invalid() -> None:
    from master.decision import decide_from_observation

    decision = decide_from_observation({"control_seq": 3, "valid": 0})

    assert decision.assistant_command == "follow=1,seq=3,valid=0,dx=0.000,dy=0.000"
```

```python
def test_decision_outputs_zero_when_report_is_stale() -> None:
    from master.decision import decide_from_observation

    decision = decide_from_observation({"control_seq": 4, "valid": 1, "stale": 1})

    assert decision.assistant_command == "follow=1,seq=4,valid=0,dx=0.000,dy=0.000"
```

- [ ] **Step 2: 运行主车状态机与决策测试，确认失败**

Run: `python3 -m pytest tests/unit/master/test_vision_state_machine.py tests/unit/master/test_decision.py -q`
Expected: FAIL，提示阶段名或协议文本不一致。

- [ ] **Step 3: 最小实现低频状态机与高频平移控制映射**

```python
if not valid:
    return {"phase": "marker_missing", "hold": True}
if abs(err_x) <= deadzone_px and abs(err_y) <= deadzone_px:
    return {"phase": "center_hold", "hold": True}
return {"phase": "tracking", "hold": False}
```

```python
if int(observation.get("valid", 0)) != 1:
    return _build_idle_decision(control_seq)
if observation.get("phase") == "center_hold":
    return _build_idle_decision(control_seq)
dx = float(observation.get("err_x", 0.0)) * FOLLOW_CONTROL_KP_X
dy = float(observation.get("err_y", 0.0)) * FOLLOW_CONTROL_KP_Y
```

- [ ] **Step 4: 重跑主车状态机与决策测试**

Run: `python3 -m pytest tests/unit/master/test_vision_state_machine.py tests/unit/master/test_decision.py -q`
Expected: PASS。

- [ ] **Step 5: 提交状态机/控制解耦收口**

```bash
git add tests/unit/master/test_vision_state_machine.py tests/unit/master/test_decision.py src/master/vision_state_machine.py src/master/decision.py
git commit -m "feat: split marker state from planar control"
```

### Task 5: 改写主车应用编排为当前阶段最小闭环

**Files:**
- Modify: `src/master/app.py`
- Test: `tests/unit/master/test_app.py`

- [ ] **Step 1: 先写失败测试，锁定“主车不动、只控辅车”**

```python
def test_master_app_only_drives_assistant_in_current_stage() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    result = app.step({
        "uart": "uart6",
        "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
    })

    assert result["self_target"] == {"kind": "hold"}
    assert result["assistant_command"].startswith("follow=1,seq=1,valid=1")
```

```python
def test_master_app_zeroes_command_when_selected_report_is_expired() -> None:
    from master.app import MasterApp

    app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
    app.step({
        "uart": "uart6",
        "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
    })

    result = app.step({"uart": "uart6"})

    assert result["assistant_command"].startswith("follow=1,seq=")
```

- [ ] **Step 2: 运行主车应用测试，确认失败**

Run: `python3 -m pytest tests/unit/master/test_app.py -q`
Expected: FAIL，提示结果结构或协议文本不匹配。

- [ ] **Step 3: 最小实现应用层编排**

```python
prepared = self.ingress.prepare_observation(observation)
selected = self.ingress.select_current_target()
state_output = self.state_machine.step(
    valid=selected.get("valid", 0),
    err_x=selected.get("err_x", 0.0),
    err_y=selected.get("err_y", 0.0),
)
selected.update(state_output)
selected["control_seq"] = self.motion_runtime.next_control_seq()
decision = decide_from_observation(selected)
```

- [ ] **Step 4: 重跑主车应用测试**

Run: `python3 -m pytest tests/unit/master/test_app.py -q`
Expected: PASS。

- [ ] **Step 5: 提交主车最小闭环编排**

```bash
git add tests/unit/master/test_app.py src/master/app.py
git commit -m "feat: wire marker centering master pipeline"
```

### Task 6: 改写辅车执行侧为二维跟随 + 最小状态回传

**Files:**
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/status.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`
- Test: `tests/unit/assistant/test_status.py`
- Test: `tests/contract/master_assistant/test_motion_protocol.py`

> 说明：本任务中的 `IGNORED`、`HOLD`、`BUSY` 只是运行时内部返回值示例，不属于对外最小状态回传契约。对外契约仍只认 `IDLE / BUSY / TIMEOUT`。

- [ ] **Step 1: 先写失败测试，锁定二维跟随与最小状态**

```python
def test_motion_runtime_accepts_follow_command_and_updates_state() -> None:
    from assistant.motion_runtime import MotionRuntime
    from assistant.protocol import parse_command

    runtime = MotionRuntime(timeout_ms=100)
    result = runtime.apply_command(
        parse_command("follow=1,seq=7,valid=1,dx=0.10,dy=-0.05"),
        now_ms=1,
    )

    assert result == "BUSY"
    assert runtime.state.last_seq == 7
```

```python
def test_assistant_state_reply_keeps_minimal_fields() -> None:
    from assistant.status import AssistantState, render_state

    state = AssistantState()
    state.follow_active = True
    state.last_seq = 7

    line = render_state(state)

    assert "last_seq=7" in line
    assert "follow_active=1" in line
```

```python
def test_assistant_state_contract_keeps_last_seq_and_state_label() -> None:
    from assistant.status import AssistantState, render_state

    state = AssistantState()
    state.last_seq = 8
    state.follow_active = False
    state.last_error = "timeout_stop"

    line = render_state(state)

    assert "last_seq=8" in line
    assert "state_label=" in line
```

```python
def test_assistant_state_reply_contract_has_required_minimal_fields() -> None:
    from assistant.status import AssistantState, render_state

    state = AssistantState()
    state.last_seq = 9
    state.follow_active = True

    line = render_state(state)

    assert line.startswith("state=1,")
    assert "state_label=BUSY" in line
    assert "last_seq=9" in line
    assert "follow_active=1" in line
```

```python
def test_assistant_state_reply_only_uses_supported_state_labels() -> None:
    from assistant.status import AssistantState, render_state

    state = AssistantState()
    state.last_seq = 4
    state.follow_active = False
    state.state_label = "TIMEOUT"

    line = render_state(state)

    assert "state_label=TIMEOUT" in line
```

- [ ] **Step 2: 运行辅车运行时与契约测试，确认失败**

Run: `python3 -m pytest tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_status.py tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: FAIL，提示旧 `d_angle` 相关路径不匹配。

- [ ] **Step 3: 最小实现二维执行与最小状态面**

```python
if command.kind == "follow":
    if int(command.seq) <= int(self.state.last_seq):
        return "IGNORED"
    self.state.last_seq = int(command.seq)
    if not command.valid:
        self.state.follow_active = False
        self.state.state_label = "IDLE"
        self.state.velocity_command = (0.0, 0.0, 0.0)
        return "HOLD"
    self.state.follow_active = True
    self.state.state_label = "BUSY"
    self.state.velocity_command = (command.dx, command.dy, 0.0)
    return "BUSY"
```

- [ ] **Step 4: 重跑辅车运行时与契约测试**

Run: `python3 -m pytest tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_status.py tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: PASS。

- [ ] **Step 5: 提交辅车二维执行侧**

```bash
git add tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_status.py tests/contract/master_assistant/test_motion_protocol.py src/assistant/motion_runtime.py src/assistant/status.py
git commit -m "feat: execute planar marker follow on assistant"
```

### Task 7: 补齐当前阶段最小 HIL 出口与主机侧全量回归

**Files:**
- Create: `tests/hil/2026-03-30-visual-center-follow.md`
- Test: `tests/unit/test_runtime_entry_layout.py`

- [ ] **Step 1: 写 HIL 留证模板与当前阶段最小上板步骤**

```markdown
# 2026-03-30 visual center follow

## Stage 2
- 上传 `master` / `assistant`
- 验证模块可导入
- 验证主辅协议可发可收

## Stage 3
- 人工推动主车
- 观察辅车是否把色标拉回中心
- 记录死区保持与丢失即停现象
```

- [ ] **Step 2: 运行主机侧全量回归**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS。

- [ ] **Step 3: 检查 HIL 文档与当前阶段范围说明是否一致**

Run: `python3 -m pytest tests/unit/master/test_app.py tests/unit/assistant/test_motion_runtime.py tests/contract/master_assistant/test_motion_protocol.py -q`
Expected: PASS。

- [ ] **Step 4: 提交当前阶段计划定义的主机侧闭环与 HIL 出口**

```bash
git add tests/hil/2026-03-30-visual-center-follow.md
git commit -m "test: add hil checklist for marker centering"
```

## 额外说明

- 当前计划只覆盖“辅车色标二维回中”主线，不实现灰度链路。
- 当前计划不实现主车主动运动，不实现 `d_angle` 控制，不展开搬运状态机。
- 若实施过程中发现双 UART 原始误差到统一 `x/y` 参考系的正负映射仍缺硬件事实，必须再次向用户确认，禁止猜测。
- 本计划的完成条件不是只看主机侧测试通过，还包括 `tests/hil/2026-03-30-visual-center-follow.md` 已创建并可用于后续设备留证。
