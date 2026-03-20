# Board Runtime Memory Plan Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 对当前仓库板端运行时代码做启动期, 初始化期, 运行期和诊断期的全流程内存治理, 降低 import-time 峰值, 延迟非关键装配, 压低运行期分配, 并保留低内存时的最小可观测性。

**Architecture:** 先消除 `services.commanding.handlers` 的自动发现导入峰值, 再把 `TransportCar` 构造改成 staged init, 最后继续清理主循环高频分配和固化 `health/tick/vision` 观测面。整个过程保持外部命令协议与查询语义基本不变, 只重排内部装配与状态归属。

**Tech Stack:** Python, pytest, MicroPython-friendly runtime assembly, board-side diagnostics

---

### Task 1: 消除 handler 自动发现的启动期峰值

**Files:**
- Modify: `src/services/commanding/handlers/__init__.py`
- Modify: `tests/unit/services/test_transport_car_diag_mode.py`
- Modify: `tests/unit/services/test_command_router.py`
- Test: `tests/unit/services/test_transport_car_diag_mode.py`

**Step 1: Write the failing test**

```python
def test_load_all_handlers_uses_static_module_list_without_directory_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    monkeypatch.setattr(handler_module.os, "listdir", lambda *_args: (_ for _ in ()).throw(AssertionError("should not scan")))
    monkeypatch.setattr(handler_module, "_import_handler_module", lambda name: calls.append(name))

    handler_module.load_all_handlers()

    assert calls == EXPECTED_ALL_HANDLER_MODULES
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py -k static_module_list -q`

Expected: FAIL, 因为当前实现仍依赖 `os.listdir()` 自动发现

**Step 3: Write minimal implementation**

- 用静态模块元组替代目录扫描
- 保留 `load_all_handlers()` / `load_query_handlers()` 外部行为
- 避免在 import-time 构造多余列表和排序结果

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py tests/unit/services/test_command_router.py -q`

Expected: PASS

### Task 2: 将 `TransportCar` 改为 staged init

**Files:**
- Modify: `src/services/transport_car.py`
- Modify: `tests/unit/services/test_transport_car_logging.py`
- Modify: `tests/unit/services/test_transport_car_diag_snapshots.py`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write the failing test**

```python
def test_transport_car_initializes_core_runtime_before_optional_features() -> None:
    car = TransportCar(vehicle_role="main")

    assert car.uart3 is not None
    assert car.logger_manager is not None
    assert car.command_session is not None
    assert hasattr(car, "vision_runtime")
```

再补一个测试, 锁定辅车或最小模式下不会过早创建主车特有功能对象。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py -k core_runtime_before_optional_features -q`

Expected: FAIL

**Step 3: Write minimal implementation**

- 把构造流程拆成 `_init_core_runtime()` 与 `_init_optional_features()`
- 先拉起 uart/logger/chassis state/minimal diagnostics
- 再按 role 装配 vision 和扩展能力

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_diag_snapshots.py -q`

Expected: PASS

### Task 3: 压低运行期高频分配

**Files:**
- Modify: `src/services/transport_car.py`
- Modify: `src/services/runtime/diagnostics_facade.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Modify: `tests/unit/services/test_transport_car_logging.py`
- Test: `tests/unit/services/test_transport_car_vision_integration.py`

**Step 1: Write the failing test**

```python
def test_runtime_queries_reuse_owner_state_without_new_container_path() -> None:
    car = build_transport_car()

    first = car.get_diagnostics_facade().build_health_snapshot()
    second = car.get_diagnostics_facade().build_health_snapshot()

    assert first.keys() == second.keys()
```

再补测试锁定剩余高频 closure/list/dict 热点不回流。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_logging.py -k reuse -q`

Expected: FAIL 或暴露仍未收口的高频分配点

**Step 3: Write minimal implementation**

- 继续清理 `TransportCar` 主循环中的短生命周期分配
- 对 diagnostics facade 按需补充可复用结构, 但不引入新重对象

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_logging.py -q`

Expected: PASS

### Task 4: 固化最小诊断面并覆盖 OOM 观测

**Files:**
- Modify: `src/services/runtime/diagnostics_facade.py`
- Modify: `tests/unit/services/test_transport_car_diag_snapshots.py`
- Modify: `tests/contract/services/commands/test_diag_queries.py`
- Test: `tests/unit/services/test_transport_car_diag_snapshots.py`
- Test: `tests/contract/services/commands/test_diag_queries.py`

**Step 1: Write the failing test**

补测试锁定 `?health` / `?tick` / `?vision` 在低内存治理后仍保留最小关键字段, 包括 `oom_count` / `oom_stage`。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_snapshots.py tests/contract/services/commands/test_diag_queries.py -k health -q`

Expected: FAIL（若字段或顺序发生漂移）

**Step 3: Write minimal implementation**

- 固化最小诊断字段
- 避免后续重构时诊断面回流到重日志依赖

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_snapshots.py tests/contract/services/commands/test_diag_queries.py -q`

Expected: PASS

### Task 5: 板端回归前的主机验证

**Files:**
- Test: `tests/unit`
- Test: `tests/contract`

**Step 1: Run full host regression**

Run: `python3 -m pytest tests/unit tests/contract -q`

Expected: PASS

### Task 6: 板端 Stage 3 / HIL 手动验证与记录

**Files:**
- Modify: `tests/hil/README.md`
- Modify: `tests/hil/2026-03-dual-camera-polling.md`
- Modify: `.progress/entries/2026/2026-03-15-1.md`
- Modify: `.progress/PROGRESS.md`

**Step 1: User-run Stage 3 observe**

由用户手动执行板端验证, 重点记录:
- 是否还会在启动期 import 链 OOM
- `?health` 中 `oom_count/oom_stage` 是否可用
- 视觉接通后状态机是否还能推进

**Step 2: HIL evidence**

用户完成板端验证后, 再把观察到的结果写入 `tests/hil/` 和 `.progress/`

**Step 3: Commit**

```bash
git add tests/hil .progress
git commit -m "docs(hil): record board memory validation"
```
