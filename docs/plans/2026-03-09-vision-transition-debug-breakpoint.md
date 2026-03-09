# Vision Transition Debug Breakpoint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在视觉状态机每次真实状态迁移后自动进入 `TransportCar.debug()` 等待, 直到 `uart3` 收到 `debug=1` 再继续执行。

**Architecture:** 保持 `VisionStateMachine` 只负责产生结构化迁移事件, 不直接依赖 UART 或 `TransportCar`。由 `TransportCar` 的视觉调试 sink 在输出迁移日志后触发阻塞等待, 这样状态机仍保持纯逻辑, 调试能力集中在编排层。

**Tech Stack:** Python, pytest, MicroPython-compatible services layer

---

### Task 1: 为迁移后断点编写失败测试

**Files:**
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Modify: `tests/unit/services/test_transport_car_debug_breakpoint.py`

**Step 1: Write the failing test**

```python
def test_transport_car_debug_sink_waits_after_transition_event() -> None:
    car = build_transport_car()
    car.debug_calls = 0
    car.debug = lambda: setattr(car, "debug_calls", car.debug_calls + 1) or True

    event = build_transition_event(...)

    car._emit_vision_debug(event)

    assert car.debug_calls == 1
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: FAIL because `_emit_vision_debug()` 目前只写日志, 不触发 `debug()`

**Step 3: Write minimal implementation**

在 `TransportCar` 的视觉调试输出路径中, 仅当发生真实迁移事件时, 输出日志后调用 `self.debug()`。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS

### Task 2: 更新 HIL 场景

**Files:**
- Modify: `tests/hil/scenarios/debug_breakpoint.md`

**Step 1: Write the scenario update**

补充“视觉状态机每次真实状态迁移后在 uart3 输出迁移日志并暂停, 逐次发送 `debug=1` 放行”的板端验证步骤。

**Step 2: Verify the doc reflects runtime behavior**

Run: `python3 -m pytest tests/unit/services/test_transport_car_debug_breakpoint.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS

### Task 3: 运行回归验证

**Files:**
- Modify: `src/services/transport_car.py`

**Step 1: Run focused tests**

Run: `python3 -m pytest tests/unit/services/test_transport_car_debug_breakpoint.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS

**Step 2: Run full host regression**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS
