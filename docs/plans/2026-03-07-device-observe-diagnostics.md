# Device Observe Diagnostics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为真实板级 Stage 3 观测测试建立一套可脚本化的运行时诊断能力，让 agent 能通过 `mpy-cli` 主动触发、读取并归因设备状态。

**Architecture:** 以 `TransportCar` 运行时快照为核心，同时暴露 `UART6` 查询处理器和 USB/`mpy-cli` 临时观测探针。主机侧新增执行器脚本，统一编排上传、运行、删除和结果判定流程，并保持 5ms 控制周期约束不被诊断逻辑破坏。

**Tech Stack:** Python 3.10+, pytest, MicroPython-compatible services layer, mpy-cli, subprocess

---

### Task 1: 设计与计划文档落盘

**Files:**
- Create: `docs/plans/2026-03-07-device-observe-diagnostics-design.md`
- Create: `docs/plans/2026-03-07-device-observe-diagnostics.md`

**Step 1: 写入设计和实施计划文档**

- 记录双入口观测模型、运行时快照设计、主机侧执行器职责和失败分类。

**Step 2: Run doc existence check**

Run: `python3 - <<'PY'
from pathlib import Path
paths = [
    Path('docs/plans/2026-03-07-device-observe-diagnostics-design.md'),
    Path('docs/plans/2026-03-07-device-observe-diagnostics.md'),
]
for path in paths:
    assert path.is_file(), path
print('ok')
PY`
Expected: `ok`

**Step 3: Commit**

```bash
git add docs/plans/2026-03-07-device-observe-diagnostics-design.md docs/plans/2026-03-07-device-observe-diagnostics.md
git commit -m "docs: add device observe diagnostics design"
```

### Task 2: 运行时诊断快照（RED -> GREEN）

**Files:**
- Modify: `src/services/transport_car.py`
- Create: `tests/unit/services/test_transport_car_diag_snapshots.py`

**Step 1: Write the failing test**

```python
def test_build_tick_snapshot_reports_overrun_statistics() -> None:
    car = build_transport_car_for_diag()
    car.tick_count = 12
    car.last_loop_dt_us = 5400
    car.max_loop_dt_us = 6200
    car.loop_dt_total_us = 60000
    car.loop_overrun_count = 2

    snapshot = car.build_tick_snapshot()

    assert snapshot["count"] == 12
    assert snapshot["last_us"] == 5400
    assert snapshot["max_us"] == 6200
    assert snapshot["avg_us"] == 5000
    assert snapshot["overrun"] == 2
```

```python
def test_build_vision_snapshot_uses_latest_observation_and_target() -> None:
    car = build_transport_car_for_diag()
    car._now_ms = lambda: 1500
    car.vision_protocol = FakeVisionProtocolWithObservation(x=120.0, y=80.0, observed_at_ms=1400)
    car._vision_resolved_target = FakeResolvedTarget(x=0.2, y=0.4, angle_deg=15.0, rear_only_mode=False)

    snapshot = car.build_vision_snapshot()

    assert snapshot["obs_age_ms"] == 100
    assert snapshot["obs_x"] == 120.0
    assert snapshot["target_angle"] == 15.0
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_snapshots.py -q`
Expected: FAIL because snapshot methods or runtime fields are missing

**Step 3: Write minimal implementation**

- 为 `TransportCar` 增加轻量诊断字段和快照方法。
- 在 `_handle_tick()` 中更新周期统计。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_snapshots.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/services/transport_car.py tests/unit/services/test_transport_car_diag_snapshots.py
git commit -m "feat(services): add transport diagnostics snapshots"
```

### Task 3: 诊断查询处理器（RED -> GREEN）

**Files:**
- Create: `src/services/commands/query_health.py`
- Create: `src/services/commands/query_tick.py`
- Create: `src/services/commands/query_imu.py`
- Create: `src/services/commands/query_enc.py`
- Create: `src/services/commands/query_motor.py`
- Create: `src/services/commands/query_vision.py`
- Modify: `tests/fakes/fake_context.py`
- Create: `tests/contract/services/commands/test_diag_queries.py`

**Step 1: Write the failing test**

```python
def test_query_tick_formats_runtime_statistics() -> None:
    ctx = FakeCommandContext()
    ctx.build_tick_snapshot = lambda: {
        "count": 12,
        "last_us": 5010,
        "max_us": 6400,
        "avg_us": 5050,
        "overrun": 1,
    }

    query_tick.handle(ctx)

    assert ctx.uart6.messages == ["?tick=count:12,last_us:5010,max_us:6400,avg_us:5050,overrun:1\r\n"]
```

```python
def test_query_vision_formats_target_and_observation() -> None:
    ctx = FakeCommandContext()
    ctx.build_vision_snapshot = lambda: {
        "state": "ALIGN_DX",
        "obs_age_ms": 80,
        "obs_x": 120.0,
        "obs_y": 75.0,
        "target_x": 0.2,
        "target_y": 0.4,
        "target_angle": 15.0,
    }

    query_vision.handle(ctx)

    assert ctx.uart6.messages == ["?vision=state:ALIGN_DX,obs_age_ms:80,obs_x:120.0,obs_y:75.0,target_x:0.2,target_y:0.4,target_angle:15.0\r\n"]
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/services/commands/test_diag_queries.py -q`
Expected: FAIL because query handlers are missing

**Step 3: Write minimal implementation**

- 新增诊断查询处理器。
- 为 `FakeCommandContext` 扩展对应快照方法。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/services/commands/test_diag_queries.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/services/commands/query_health.py src/services/commands/query_tick.py src/services/commands/query_imu.py src/services/commands/query_enc.py src/services/commands/query_motor.py src/services/commands/query_vision.py tests/fakes/fake_context.py tests/contract/services/commands/test_diag_queries.py
git commit -m "feat(services): add runtime diagnostic queries"
```

### Task 4: 设备侧观测探针与主机执行器（RED -> GREEN）

**Files:**
- Create: `tools/device_observe_probe.py`
- Create: `tools/run_device_observe.py`
- Create: `tests/unit/tools/test_run_device_observe.py`

**Step 1: Write the failing test**

```python
def test_build_mpy_cli_commands_include_upload_run_and_delete() -> None:
    commands = build_probe_commands(port="/dev/cu.usbmodem1101")

    assert commands[0][:3] == ["mpy-cli", "plan", "--port"]
    assert any(cmd[1] == "upload" for cmd in commands)
    assert any(cmd[1] == "run" for cmd in commands)
    assert any(cmd[1] == "delete" for cmd in commands)
```

```python
def test_parse_probe_output_marks_observe_failure_on_overrun() -> None:
    result = parse_probe_output(
        "OBSERVE tick count=20 last_us=5100 max_us=9001 avg_us=5200 overrun=3\n"
    )

    assert result.status == "observe_failed"
    assert "overrun" in result.reason
```
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/tools/test_run_device_observe.py -q`
Expected: FAIL because host-side runner helpers are missing

**Step 3: Write minimal implementation**

- 提供 `mpy-cli` 命令编排 helper。
- 提供观测输出解析与失败分类。
- 增加版本化的设备侧观测探针脚本。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/tools/test_run_device_observe.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tools/device_observe_probe.py tools/run_device_observe.py tests/unit/tools/test_run_device_observe.py
git commit -m "feat(test): add stage3 device observe runner"
```

### Task 5: 文档、HIL 场景与回归验证（REFACTOR）

**Files:**
- Modify: `tests/README.md`
- Modify: `tests/hil/README.md`
- Modify: `tests/hil/scenarios/basic_motion.md`
- Modify: `Readme.md`

**Step 1: 更新设备阶段说明**

- 说明 Stage 2 / Stage 3 的定位、执行方式和留证要求。
- 在协议文档中补充新增查询列表。

**Step 2: Run targeted tests**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_snapshots.py tests/contract/services/commands/test_diag_queries.py tests/unit/tools/test_run_device_observe.py -q`
Expected: PASS

**Step 3: Run full host-side regression**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS

**Step 4: Commit**

```bash
git add tests/README.md tests/hil/README.md tests/hil/scenarios/basic_motion.md Readme.md
git commit -m "docs: document staged device diagnostics workflow"
```
