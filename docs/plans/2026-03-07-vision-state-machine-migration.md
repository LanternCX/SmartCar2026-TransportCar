# Vision State Machine Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `../SmartCar2026-Vision` 的状态机跳转迁移到当前仓库，并让 OpenArt 端仅通过 `UART6` 回传视觉目标点 `x,y`，同时保持现有底盘控制行为与外部命令协议稳定。

**Architecture:** 采用“双链路并存”方案：保留现有带 `command_lock` 的外部命令链路，新增一条仅服务视觉连续跟踪的内部状态机链路。视觉链路解析 `UART6` 纯 `x,y` 包，生成内部 `dx/dy/d_angle` 风格控制意图，再在每个控制周期转换为绝对 `x/y/angle` 目标喂给现有位置环。

**Tech Stack:** Python 3.10+, pytest, MicroPython-compatible services layer

---

### Task 1: 设计文档与协议约束落盘

**Files:**
- Create: `docs/plans/2026-03-07-vision-state-machine-migration-design.md`
- Create: `docs/plans/2026-03-07-vision-state-machine-migration.md`

**Step 1: 写入设计与实施计划文档**

- 记录双链路并存、视觉协议边界、适度加锁策略和固定 `push_angle` 决策。

**Step 2: 自检文档路径与命名**

Run: `python3 - <<'PY'
from pathlib import Path
paths = [
    Path('docs/plans/2026-03-07-vision-state-machine-migration-design.md'),
    Path('docs/plans/2026-03-07-vision-state-machine-migration.md'),
]
for path in paths:
    assert path.is_file(), path
print('ok')
PY`
Expected: `ok`

### Task 2: Vision Protocol（RED -> GREEN）

**Files:**
- Create: `src/services/vision_protocol.py`
- Create: `tests/unit/services/test_vision_protocol.py`

**Step 1: Write the failing test**

```python
def test_parse_xy_packet_from_uart6() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation("x=123,y=45", source="uart6", now_ms=1000)

    assert parsed is not None
    assert parsed.x == 123.0
    assert parsed.y == 45.0
```

```python
def test_reject_non_visual_packet() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation("x=1,y=2,angle=3", source="uart6", now_ms=1000)

    assert parsed is None
```

```python
def test_observation_timeout_marks_target_lost() -> None:
    protocol = VisionProtocol(timeout_ms=200)
    protocol.try_parse_observation("x=123,y=45", source="uart6", now_ms=1000)

    assert protocol.get_observation(now_ms=1301) is None
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py -q`
Expected: FAIL with `ModuleNotFoundError` or missing symbol errors

**Step 3: Write minimal implementation**

- 实现仅识别 `UART6` 上纯 `x,y` 双键包的解析器。
- 提供最新观测缓存与超时读取接口。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py -q`
Expected: PASS

### Task 3: Vision State Machine（RED -> GREEN）

**Files:**
- Create: `src/services/vision_state_machine.py`
- Create: `tests/unit/services/test_vision_state_machine.py`
- Modify: `src/config/params.py`

**Step 1: Write the failing test**

```python
def test_idle_enters_align_angle_when_observation_arrives() -> None:
    machine = VisionStateMachine(config=build_test_config())

    state = machine.step(build_inputs(obs=(200.0, 120.0)))

    assert state.name == "ALIGN_ANGLE"
```

```python
def test_align_dist_returns_to_align_angle_when_x_error_grows() -> None:
    machine = VisionStateMachine(config=build_test_config(initial_state=SMState.ALIGN_DIST))

    state = machine.step(build_inputs(obs=(240.0, 120.0)))

    assert state.name == "ALIGN_ANGLE"
```

```python
def test_align_dx_enters_pushing_when_heading_matches_push_angle() -> None:
    machine = VisionStateMachine(config=build_test_config(initial_state=SMState.ALIGN_DX))

    state = machine.step(build_inputs(obs=(160.0, 120.0), heading_deg=-90.0))

    assert state.name == "PUSHING"
```

```python
def test_pushing_finishes_after_push_distance_reached() -> None:
    machine = VisionStateMachine(config=build_test_config(initial_state=SMState.PUSHING))
    machine.start_push(0.0, 0.0)

    state = machine.step(build_inputs(obs=(160.0, 120.0), odom=(0.0, 0.25), heading_deg=-90.0))

    assert state.name == "RETURNING"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py -q`
Expected: FAIL with `ModuleNotFoundError` or missing behavior errors

**Step 3: Write minimal implementation**

- 实现状态常量、运行时上下文、单步状态推进和丢目标回空闲逻辑。
- 将 Vision 仓库中的死区、回退、绕行、推行和返回规则映射到本机状态字段。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py -q`
Expected: PASS

### Task 4: Relative Intent Adaptation（RED -> GREEN）

**Files:**
- Modify: `src/services/vision_state_machine.py`
- Create: `tests/unit/services/test_vision_control_adapter.py`

**Step 1: Write the failing test**

```python
def test_relative_intent_converts_to_absolute_targets() -> None:
    intent = VisionControlIntent(active=True, dx_body=1.0, dy_body=0.0, d_angle_deg=15.0)

    target = resolve_relative_intent(intent, odom_x=2.0, odom_y=3.0, heading_deg=90.0)

    assert target.x == 2.0
    assert target.y == 4.0
    assert target.angle_deg == 105.0
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_control_adapter.py -q`
Expected: FAIL because helper is missing or incorrect

**Step 3: Write minimal implementation**

- 提供将内部 `dx/dy/d_angle` 相对控制意图转换为本周期绝对 `x/y/angle` 目标的纯函数。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_control_adapter.py -q`
Expected: PASS

### Task 5: TransportCar 集成（RED -> GREEN）

**Files:**
- Modify: `src/services/transport_car.py`
- Modify: `tests/fakes/fake_context.py` (only if test helper needs extension)
- Create: `tests/unit/services/test_transport_car_vision_integration.py`

**Step 1: Write the failing test**

```python
def test_uart6_xy_packet_updates_visual_observation() -> None:
    car = build_testable_transport_car()

    car.feed_uart6("x=120,y=80\n")
    car._process_uart()

    assert car.vision_protocol.get_observation(now_ms=car._now_ms()) is not None
```

```python
def test_visual_control_overrides_last_cmd_without_changing_manual_lock_chain() -> None:
    car = build_testable_transport_car()
    car.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    car.set_visual_intent(dx_body=0.1, dy_body=0.0, d_angle_deg=0.0)

    cmd_x, cmd_y = car._resolve_active_planar_target()

    assert (cmd_x, cmd_y) != (0.0, 0.0)
    assert car.command_lock is False
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: FAIL because visual integration path does not exist yet

**Step 3: Write minimal implementation**

- 在 `_process_uart()` 中优先解析 `UART6` 纯 `x,y` 包。
- 在控制周期中推进视觉状态机并解析当前视觉控制目标。
- 视觉活跃时优先采用视觉目标，但不改写现有手动命令的 `command_lock` 链路。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS

### Task 6: 文档与回归验证（REFACTOR）

**Files:**
- Modify: `Readme.md`
- Modify: `tests/hil/README.md`
- Modify: `tests/hil/scenarios/basic_motion.md`

**Step 1: 更新文档**

- 补充 `UART6` 纯 `x,y` 视觉协议说明。
- 说明视觉内部闭环与外部 `command_lock` 双链路策略。
- 增加视觉场景的 HIL 验证说明。

**Step 2: Run targeted tests**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py tests/unit/services/test_vision_state_machine.py tests/unit/services/test_vision_control_adapter.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS

**Step 3: Run full host-side regression**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS
