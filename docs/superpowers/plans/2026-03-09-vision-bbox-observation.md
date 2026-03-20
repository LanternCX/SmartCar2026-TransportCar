# Vision BBox Observation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将视觉输入从单点 `x,y` 升级为完整识别框 `left,top,right,bottom`，让状态机基于框中心和框底边完成稳定的对正与状态跳转。

**Architecture:** 在 `vision_protocol` 中引入完整框观测模型，并在状态机中把横向判据切换为 `center_x`、纵向判据切换为 `bottom`。`TransportCar` 的视觉集成与 `?vision` 快照同步升级为完整框语义，避免状态机在信息不全时做错误跳转。

**Tech Stack:** Python 3.10+, pytest, MicroPython-compatible services layer

---

### Task 1: 落盘设计与计划文档

**Files:**
- Create: `docs/superpowers/specs/2026-03-09-vision-bbox-observation-design.md`
- Create: `docs/superpowers/plans/2026-03-09-vision-bbox-observation.md`

**Step 1: 写入设计文档**

- 记录完整框协议、状态机判据切换和诊断字段补全方案。

**Step 2: 自检路径存在**

Run: `python3 - <<'PY'
from pathlib import Path
paths = [
    Path('docs/superpowers/specs/2026-03-09-vision-bbox-observation-design.md'),
    Path('docs/superpowers/plans/2026-03-09-vision-bbox-observation.md'),
]
for path in paths:
    assert path.is_file(), path
print('ok')
PY`
Expected: `ok`

### Task 2: 视觉协议升级为完整框（RED -> GREEN）

**Files:**
- Modify: `src/services/vision_protocol.py`
- Modify: `tests/unit/services/test_vision_protocol.py`

**Step 1: Write the failing test**

```python
def test_parse_bbox_packet_from_uart6() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation(
        "left=100,top=20,right=140,bottom=90", source="uart6", now_ms=1000
    )

    assert parsed.consumed is True
    assert parsed.observation.center_x == 120.0
    assert parsed.observation.bottom == 90.0
```

```python
def test_legacy_xy_packet_is_consumed_but_not_cached() -> None:
    protocol = VisionProtocol(timeout_ms=200)

    parsed = protocol.try_parse_observation("x=123,y=45", source="uart6", now_ms=1000)

    assert parsed.consumed is True
    assert parsed.observation is None
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py -q`
Expected: FAIL because protocol still only returns `x,y` observation or `None`

**Step 3: Write minimal implementation**

- 引入完整框 `VisionObservation`
- 引入区分“已消费 / 未消费”的解析结果对象
- 让旧 `x,y` 在 `UART6` 上被视为不完整视觉载荷并吞掉

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py -q`
Expected: PASS

### Task 3: 状态机改用中心和底边（RED -> GREEN）

**Files:**
- Modify: `src/services/vision_state_machine.py`
- Modify: `src/config/params.py`
- Modify: `tests/unit/services/test_vision_state_machine.py`

**Step 1: Write the failing test**

```python
def test_align_angle_uses_box_center_x() -> None:
    machine = build_test_config(initial_state=SMState.ALIGN_ANGLE)

    result = machine.step(build_inputs((150.0, 20.0, 190.0, 90.0)))

    assert result.intent.d_angle_deg == 0.0
```

```python
def test_align_dist_uses_box_bottom_for_distance() -> None:
    machine = build_test_config(initial_state=SMState.ALIGN_DIST)

    result = machine.step(build_inputs((150.0, 20.0, 190.0, 210.0)))

    assert result.intent.dy_body != 0.0
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py -q`
Expected: FAIL because state machine still directly读取 `x/y`

**Step 3: Write minimal implementation**

- 将横向误差改为 `observation.center_x - target_center_x_px`
- 将纵向误差改为 `observation.bottom - target_bottom_px`
- 将配置项语义切换到 `target_bottom_px`

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py -q`
Expected: PASS

### Task 4: TransportCar 集成完整框观测（RED -> GREEN）

**Files:**
- Modify: `src/services/transport_car.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Modify: `tests/unit/services/test_transport_car_diag_snapshots.py`

**Step 1: Write the failing test**

```python
def test_uart6_bbox_packet_updates_visual_observation() -> None:
    car = build_transport_car()

    car._handle_uart_line("left=100,top=20,right=140,bottom=90", source="uart6")

    observation = car.vision_protocol.get_observation(now_ms=1000)
    assert observation is not None
    assert observation.center_x == 120.0
    assert observation.bottom == 90.0
```

```python
def test_legacy_xy_packet_is_not_forwarded_to_manual_command_router() -> None:
    car = build_transport_car()

    car._handle_uart_line("x=120,y=80", source="uart6")

    assert car.apply_calls == []
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_diag_snapshots.py -q`
Expected: FAIL because `TransportCar` 仍按旧协议处理 `x,y`

**Step 3: Write minimal implementation**

- 让 `TransportCar` 使用新的解析结果对象决定是否吞掉 `UART6` 视觉载荷
- 让 `build_vision_snapshot()` 输出完整框和派生字段

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_diag_snapshots.py -q`
Expected: PASS

### Task 5: 诊断协议与文档回归（RED -> GREEN）

**Files:**
- Modify: `tests/contract/services/commands/test_diag_queries.py`
- Modify: `docs/Protocol.md`

**Step 1: Write the failing test**

```python
def test_query_vision_formats_full_bbox_snapshot() -> None:
    ctx = FakeCommandContext()
    ctx.build_vision_snapshot = lambda: {
        "state": "ALIGN_DX",
        "obs_age_ms": 80,
        "obs_left": 100.0,
        "obs_top": 20.0,
        "obs_right": 140.0,
        "obs_bottom": 90.0,
        "obs_center_x": 120.0,
        "obs_center_y": 55.0,
        "target_x": 0.2,
        "target_y": 0.4,
        "target_angle": 15.0,
    }
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/services/commands/test_diag_queries.py -q`
Expected: FAIL because contract 仍断言旧 `obs_x/obs_y`

**Step 3: Write minimal implementation**

- 更新 contract 测试
- 更新协议文档中的视觉帧和 `?vision` 字段说明

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/services/commands/test_diag_queries.py -q`
Expected: PASS

### Task 6: 主机侧回归验证与设备留证准备（REFACTOR）

**Files:**
- Modify: `tests/hil/scenarios/vision_bbox_alignment.md`

**Step 1: Run targeted tests**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_diag_snapshots.py tests/contract/services/commands/test_diag_queries.py -q`
Expected: PASS

**Step 2: Run broader host regression**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS

**Step 3: 补 HIL 场景说明**

- 记录“完整框输入、底边对正、旧 `x,y` 不再驱动视觉状态机”的板端验证步骤
