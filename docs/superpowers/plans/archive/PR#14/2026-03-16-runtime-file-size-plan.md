# 运行时代码 300 行门禁重构 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将受门禁约束的 `src` 运行时代码拆分到 `<= 300` 非注释代码行, 同时继续按职责拆分 `vision.protocol` / `vision.state_machine`, 保持 owner 架构与现有 host 侧行为稳定。

**Architecture:** 采用“薄壳 + 子模块分拆”方案, 保留原公开 import 路径, 把 `TransportCar`、diagnostics facade、vision protocol、vision state machine 和 log manager 的重实现拆到内部子模块。整个过程以 TDD 推进, 每个阶段先加失败测试, 再搬迁最小实现, 最后用行数门禁测试、布局测试和全量 host 回归锁定结构不回弹。

**Tech Stack:** Python, MicroPython, pytest, RT1021, repo-local `docs/superpowers/memory/`

---

### Task 1: 新增 `src` 运行时代码 300 行门禁测试

**Files:**
- Create: `tests/unit/test_src_runtime_file_sizes.py`
- Modify: `docs/superpowers/specs/2026-03-16-runtime-file-size-design.md`

**Step 1: Write the failing test**

```python
def test_runtime_python_files_stay_within_300_lines() -> None:
    assert oversized == []
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_src_runtime_file_sizes.py -q`
Expected: FAIL, 至少列出当前 5 个超限文件

**Step 3: Write minimal implementation**

在测试中只检查当前 review 范围的 `src` 运行时代码文件:

- `src/services/transport_car.py`
- `src/services/runtime/diagnostics_facade.py`
- `src/vision/protocol.py`
- `src/vision/state_machine.py`
- `src/diagnostics/manager.py`

**Step 4: Run test to verify failure message is clear**

Run: `python3 -m pytest tests/unit/test_src_runtime_file_sizes.py -q`
Expected: FAIL, 输出具体超限文件和行数

### Task 2: 将平铺 `transport_*` 重构为 `services.car` 分包

**Files:**
- Create: `src/services/car/__init__.py`
- Create: `src/services/car/core.py`
- Create: `src/services/car/bootstrap.py`
- Create: `src/services/car/loop.py`
- Create: `src/services/car/vision.py`
- Create: `src/services/car/compat.py`
- Delete: `src/services/transport_car.py`
- Delete: `src/services/transport_bootstrap.py`
- Delete: `src/services/transport_loop.py`
- Delete: `src/services/transport_vision.py`
- Delete: `src/services/transport_compat.py`
- Modify: `src/services/stage2_smoke/full.py`
- Modify: `src/script/remote_control.py`
- Test: `tests/unit/services/test_transport_car_logging.py`
- Test: `tests/unit/services/test_transport_car_diag_mode.py`
- Test: `tests/unit/services/test_transport_car_vision_integration.py`
- Test: `tests/unit/test_src_runtime_file_sizes.py`
- Test: `tests/unit/test_services_package_layout.py`

**Step 1: Write the failing test**

```python
def test_services_car_core_module_stays_within_300_lines() -> None:
    assert _line_count("src/services/car/core.py") <= 300


def test_services_root_uses_car_package_instead_of_transport_prefix_files() -> None:
    assert not Path("src/services/transport_car.py").exists()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_src_runtime_file_sizes.py tests/unit/test_services_package_layout.py -q`
Expected: FAIL, 因为新 `services.car` 包尚不存在且旧平铺 `transport_*.py` 仍存在

**Step 3: Write minimal implementation**

- 把当前 facade 和 helper 收进 `src/services/car/` 包
- 包内文件名改为 `core.py` / `bootstrap.py` / `loop.py` / `vision.py` / `compat.py`
- `src/services/car/__init__.py` 统一导出 `TransportCar` 与测试所需 monkeypatch 出口
- 更新 `src` 和 `tests` 中对 `services.transport_car` 的依赖为 `services.car`
- 删除 `src/services/` 根目录下旧 `transport_*.py` 平铺模块

**Step 4: Run focused tests**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_diag_mode.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/test_src_runtime_file_sizes.py tests/unit/test_services_package_layout.py -q`
Expected: PASS

### Task 3: 拆分 `diagnostics_facade.py`

**Files:**
- Create: `src/services/runtime/diag_format.py`
- Create: `src/services/runtime/diag_health.py`
- Create: `src/services/runtime/diag_motion.py`
- Create: `src/services/runtime/diag_vision.py`
- Modify: `src/services/runtime/diagnostics_facade.py`
- Test: `tests/unit/services/test_transport_car_diag_snapshots.py`
- Test: `tests/contract/services/commands/test_diag_queries.py`

**Step 1: Write the failing test**

```python
def test_diagnostics_facade_module_stays_within_300_lines() -> None:
    assert _line_count("src/services/runtime/diagnostics_facade.py") <= 300
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_src_runtime_file_sizes.py -q`
Expected: FAIL, `src/services/runtime/diagnostics_facade.py` 超限

**Step 3: Write minimal implementation**

- 保留 `DiagnosticsFacade` 公开 facade
- 把 health / tick / motion / vision snapshot 构建拆入子模块
- 保持 query 格式、字段顺序和 facade 契约不变

**Step 4: Run focused tests**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_snapshots.py tests/contract/services/commands/test_diag_queries.py -q`
Expected: PASS

### Task 4: 拆分 `vision/protocol.py`

**Files:**
- Create: `src/vision/protocol/__init__.py`
- Create: `src/vision/protocol/query.py`
- Create: `src/vision/protocol/parse.py`
- Create: `src/vision/protocol/batch.py`
- Delete: `src/vision/protocol.py`
- Delete: `src/vision/protocol_query.py`
- Delete: `src/vision/protocol_parse.py`
- Delete: `src/vision/protocol_batch.py`
- Test: `tests/unit/test_services_package_layout.py`
- Test: `tests/unit/services/test_vision_protocol.py`
- Test: `tests/contract/services/test_transport_runtime_protocol.py`

**Step 1: Write the failing test**

```python
def test_vision_protocol_uses_split_submodules() -> None:
    root = Path("src/vision")
    assert (root / "protocol").is_dir()
    assert (root / "protocol/query.py").is_file()
    assert (root / "protocol/parse.py").is_file()
    assert (root / "protocol/batch.py").is_file()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_services_package_layout.py -q`
Expected: FAIL, 新子模块尚不存在

**Step 3: Write minimal implementation**

- 保留 `VisionProtocol`、`VisionFrame`、`VisionObservation` 等公开入口
- 把 query helper、payload parse、invalid batch / pending frame commit 拆到子模块
- 保持 UART6 frame 协议行为不变

**Step 4: Run focused tests**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py tests/contract/services/test_transport_runtime_protocol.py -q`
Expected: PASS

### Task 5: 拆分 `vision/state_machine.py`

**Files:**
- Create: `src/vision/state_machine/__init__.py`
- Create: `src/vision/state_machine/types.py`
- Create: `src/vision/state_machine/core.py`
- Create: `src/vision/state_machine/actions.py`
- Delete: `src/vision/state_machine.py`
- Delete: `src/vision/state_machine_types.py`
- Delete: `src/vision/state_machine_core.py`
- Delete: `src/vision/state_machine_actions.py`
- Test: `tests/unit/test_services_package_layout.py`
- Test: `tests/unit/services/test_vision_state_machine.py`
- Test: `tests/unit/services/test_transport_car_vision_integration.py`

**Step 1: Write the failing test**

```python
def test_vision_state_machine_uses_split_submodules() -> None:
    root = Path("src/vision")
    assert (root / "state_machine").is_dir()
    assert (root / "state_machine/types.py").is_file()
    assert (root / "state_machine/core.py").is_file()
    assert (root / "state_machine/actions.py").is_file()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_services_package_layout.py -q`
Expected: FAIL, 新子模块尚不存在

**Step 3: Write minimal implementation**

- 保留公开 config / inputs / result / state machine 入口
- 把 transition core 和 action helper 下沉到子模块
- 保持状态迁移、debug event 和 intent 语义不变

**Step 4: Run focused tests**

Run: `python3 -m pytest tests/unit/services/test_vision_state_machine.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS

### Task 6: 拆分 `diagnostics/manager.py`

**Files:**
- Create: `src/diagnostics/log_config.py`
- Create: `src/diagnostics/log_emit.py`
- Create: `src/diagnostics/log_logger.py`
- Modify: `src/diagnostics/manager.py`
- Test: `tests/unit/services/test_logging.py`
- Test: `tests/contract/services/commands/test_log_commands.py`

**Step 1: Write the failing test**

```python
def test_log_manager_module_stays_within_300_lines() -> None:
    assert _line_count("src/diagnostics/manager.py") <= 300
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_src_runtime_file_sizes.py -q`
Expected: FAIL, `src/diagnostics/manager.py` 超限

**Step 3: Write minimal implementation**

- 保留 `LogManager`、`Logger`、`build_uart3_logger_manager()` 公共入口
- 把 level / filter config、emit / sink、logger wrapper 拆开
- 保持 OOM fallback、filter mode 和 query response 契约不变

**Step 4: Run focused tests**

Run: `python3 -m pytest tests/unit/services/test_logging.py tests/contract/services/commands/test_log_commands.py -q`
Expected: PASS

### Task 7: 最终 host 验证与进度记录

**Files:**
- Modify: `docs/superpowers/memory/milestone/INDEX.md`
- Create: `docs/superpowers/memory/milestone/entries/2026-03/2026-03-16-3.md`

**Step 1: Run full host verification**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS

**Step 2: Run file-size gate verification**

Run: `python3 -m pytest tests/unit/test_src_runtime_file_sizes.py -q`
Expected: PASS, 所有受约束 `src` 文件都 <= 300 行

**Step 3: Record memory**

记录:

- 哪 5 个 `src` 文件被压到 <= 300 行
- 采用了哪些新子模块
- 全量 host 测试结果
- 板端 Stage 2 / HIL 仍受串口状态阻塞

**Step 4: Run final collection check**

Run: `python3 -m pytest --collect-only -q`
Expected: PASS
