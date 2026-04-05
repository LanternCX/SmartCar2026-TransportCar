# OOM Health Signal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 给 `?health` 增加轻量 `oom_count` / `oom_stage` 观测, 用最小代价判断系统最近是否发生过 OOM。

**Architecture:** 在运行时对象上维护两个最小 OOM 字段, 由 `LogManager` 在 `format` / `sink` 的 `MemoryError` catch 中通过轻量回调上报。`DiagnosticsFacade` 只读这两个字段并输出到 `health` 查询, 不增加额外重对象或长文本日志。

**Tech Stack:** Python, pytest, MicroPython-friendly runtime diagnostics

---

### Task 1: 锁定 `?health` 的 OOM 字段

**Files:**
- Modify: `tests/unit/services/test_transport_car_diag_snapshots.py`
- Modify: `tests/unit/services/test_logging.py`

**Step 1: Write the failing test**

```python
def test_diagnostics_facade_reports_oom_fields_in_health_snapshot() -> None:
    runtime = types.SimpleNamespace(..., oom_count=3, last_oom_stage="format")
    facade = DiagnosticsFacade(runtime)

    assert facade.build_health_snapshot()["oom_count"] == 3
    assert facade.build_health_snapshot()["oom_stage"] == "format"
```

```python
def test_log_manager_reports_format_and_sink_oom_via_callback() -> None:
    events = []
    manager = LogManager(..., oom_callback=lambda stage: events.append(stage))
    ...
    assert events == ["format", "sink"]
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_snapshots.py tests/unit/services/test_logging.py -k "oom_fields or oom_via_callback" -q`

Expected: FAIL

**Step 3: Write minimal implementation**

- `LogManager` 增加可选 `oom_callback`
- 在 `format` / `sink` 的 `MemoryError` catch 中上报短 stage token
- `DiagnosticsFacade.build_health_snapshot()` 输出 `oom_count` / `oom_stage`

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_snapshots.py tests/unit/services/test_logging.py -q`

Expected: PASS

### Task 2: 接到 `TransportCar` 运行时 owner

**Files:**
- Modify: `src/services/transport_car.py`
- Modify: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write the failing test**

```python
def test_transport_car_records_logger_oom_into_runtime_health_fields() -> None:
    car = build_transport_car()
    ...
    assert car.oom_count == 1
    assert car.last_oom_stage == "format"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py -k oom -q`

Expected: FAIL

**Step 3: Write minimal implementation**

- `TransportCar` 初始化 `oom_count` / `last_oom_stage`
- 为 `LogManager` 传入轻量 OOM 回调, 仅做计数和短 stage 记录

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py -q`

Expected: PASS

### Task 3: 最终回归

**Files:**
- Test: `tests/unit/services/test_logging.py`
- Test: `tests/unit/services/test_transport_car_diag_snapshots.py`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Run regression**

Run: `python3 -m pytest tests/unit/services/test_logging.py tests/unit/services/test_transport_car_diag_snapshots.py tests/unit/services/test_transport_car_logging.py -q`

Expected: PASS
