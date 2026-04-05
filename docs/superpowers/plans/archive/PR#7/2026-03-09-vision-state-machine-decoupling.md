# Vision State Machine Decoupling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 解耦视觉状态机日志系统与状态元信息管理，让 `VisionStateMachine` 只负责状态跳转与控制意图计算。

**Architecture:** 新增独立的状态注册管理模块、状态定义模块和视觉调试模块。`TransportCar` 仅注入调试 sink 并通过注册表查询状态名，状态机本体只维护状态 ID 和跳转逻辑。

**Tech Stack:** Python 3.10+, pytest, MicroPython-compatible services layer

---

### Task 1: 落盘状态元信息与日志解耦设计

**Files:**
- Create: `docs/superpowers/specs/2026-03-09-vision-state-machine-decoupling-design.md`
- Create: `docs/superpowers/plans/2026-03-09-vision-state-machine-decoupling.md`

**Step 1: 写入设计文档**

- 记录状态注册表、状态定义文件、日志 sink 注入和 `TransportCar` 的最小职责。

**Step 2: 自检路径存在**

Run: `python3 - <<'PY'
from pathlib import Path
paths = [
    Path('docs/superpowers/specs/2026-03-09-vision-state-machine-decoupling-design.md'),
    Path('docs/superpowers/plans/2026-03-09-vision-state-machine-decoupling.md'),
]
for path in paths:
    assert path.is_file(), path
print('ok')
PY`
Expected: `ok`

### Task 2: 状态注册表（RED -> GREEN）

**Files:**
- Create: `src/services/vision_state_registry.py`
- Create: `src/services/vision_state_defs.py`
- Create: `tests/unit/services/test_vision_state_registry.py`

**Step 1: Write the failing test**

```python
def test_registry_returns_registered_state_name() -> None:
    assert vision_state_registry.get_state_name(SMState.ALIGN_DX) == "ALIGN_DX"
```

```python
def test_registry_returns_registered_reason_name() -> None:
    assert vision_state_registry.get_reason_name(
        VisionTransitionReason.ENTER_PUSHING
    ) == "enter_pushing"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_state_registry.py -q`
Expected: FAIL because registry module does not exist yet

**Step 3: Write minimal implementation**

- 实现状态/原因定义对象与注册表。
- 在独立定义模块中注册默认状态与原因。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_state_registry.py -q`
Expected: PASS

### Task 3: 视觉调试模块（RED -> GREEN）

**Files:**
- Create: `src/services/vision_debug.py`
- Modify: `tests/unit/services/test_vision_state_machine.py`

**Step 1: Write the failing test**

```python
def test_format_transition_event_uses_registry_names() -> None:
    text = format_transition_event(
        build_transition_event(
            old_state=SMState.ALIGN_DIST,
            new_state=SMState.ALIGN_ANGLE,
            reason=VisionTransitionReason.ANGLE_ERROR_REENTRY,
            stable_counter=0,
            observation_x=200.0,
            observation_y=120.0,
            heading_deg=0.0,
            odom_x=0.0,
            odom_y=0.0,
            now_ms=1234,
        )
    )

    assert "VSM TRANS ALIGN_DIST->ALIGN_ANGLE" in text
    assert "reason=angle_error_reentry" in text
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py -q`
Expected: FAIL because debug module is missing

**Step 3: Write minimal implementation**

- 实现事件对象、格式化函数和 UART sink 构造函数。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py -q`
Expected: PASS

### Task 4: 状态机接入注册表与调试 sink（RED -> GREEN）

**Files:**
- Modify: `src/services/vision_state_machine.py`
- Modify: `tests/unit/services/test_vision_state_machine.py`

**Step 1: Write the failing test**

```python
def test_debug_sink_receives_transition_event() -> None:
    events = []
    machine = VisionStateMachine(
        build_test_config(initial_state=SMState.ALIGN_DIST).config,
        initial_state=SMState.ALIGN_DIST,
        debug_sink=events.append,
    )

    machine.step(build_inputs((200.0, 120.0), now_ms=1234))

    assert events[0].reason == VisionTransitionReason.ANGLE_ERROR_REENTRY
```
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py -q`
Expected: FAIL because state machine still emits plain text directly

**Step 3: Write minimal implementation**

- 让状态机通过状态注册表查询元信息。
- 让状态机对外发出结构化迁移事件。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py -q`
Expected: PASS

### Task 5: TransportCar 集成解耦（RED -> GREEN）

**Files:**
- Modify: `src/services/transport_car.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`

**Step 1: Write the failing test**

```python
def test_transport_car_reads_state_name_from_registry() -> None:
    car = build_transport_car()
    car.vision_state_machine.state = SMState.ALIGN_DX

    assert car._get_vision_state_name() == "ALIGN_DX"
```

```python
def test_transport_car_debug_sink_writes_formatted_text_to_uart3() -> None:
    car = build_transport_car()
    event = build_transition_event(
        old_state=SMState.ALIGN_DIST,
        new_state=SMState.ALIGN_ANGLE,
        reason=VisionTransitionReason.ANGLE_ERROR_REENTRY,
        stable_counter=0,
    )

    car._emit_vision_debug(event)

    assert "VSM TRANS ALIGN_DIST->ALIGN_ANGLE" in car.uart3.messages[-1]
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: FAIL because `TransportCar` still owns formatting details or local state-name map

**Step 3: Write minimal implementation**

- 去掉 `TransportCar` 中本地状态名字典。
- 注入调试 sink，并通过独立模块完成格式化。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS

### Task 6: 回归验证与 Stage 2 验证（REFACTOR）

**Files:**
- Modify: `src/services/stage2_smoke.py` (only if import path markers need alignment)

**Step 1: Run targeted tests**

Run: `python3 -m pytest tests/unit/services/test_vision_state_registry.py tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS

**Step 2: Run broader host regression**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS

**Step 3: Run Stage 2 smoke**

Run: `python3 tools/run_stage2_smoke.py --port /dev/cu.usbmodem11101`
Expected: `status=ok reason=ok`
