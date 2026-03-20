# src Runtime Memory Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 对当前仓库 `src/` 上线运行时代码做一次 repo 级低内存重构, 去掉不必要的模块级全局变量, 收口运行时状态 owner, 并降低日志与视觉链路的常驻内存和高频分配。

**Architecture:** 先重构 `src/diagnostics/` 让 logger 自身瘦身并在低内存时主动退让, 再把 `src/vision/` 重构为单 owner + 固定槽位模型, 最后收缩 `src/services/transport_car.py` 与其依赖的数据流。其余 `src/` 运行时代码按统一 checklist 做逐文件审查, 删除不必要的全局变量, 副本状态和历史兼容结构。

**Tech Stack:** Python, pytest, MicroPython-friendly runtime objects, host-side unit and contract tests

---

### Task 1: 锁定 logger 瘦身目标

**Files:**
- Modify: `tests/unit/services/test_logging.py`
- Modify: `tests/unit/services/test_transport_car_logging.py`
- Test: `tests/unit/services/test_logging.py`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write the failing test**

补测试锁定以下行为:

```python
def test_log_manager_module_does_not_keep_legacy_runtime_tables() -> None:
    import diagnostics.manager as manager_module

    assert hasattr(manager_module, "LEVEL_NAME_TO_VALUE") is False
    assert hasattr(manager_module, "LEVEL_VALUE_TO_NAME") is False
    assert hasattr(manager_module, "VALID_FILTER_MODES") is False


def test_logger_is_cached_per_module_name() -> None:
    manager = LogManager()

    assert manager.get_logger("vision.state") is manager.get_logger("vision.state")
```

再补一个行为测试, 锁定被等级过滤的高频日志不会要求先格式化完整消息。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_logging.py -k "legacy_runtime_tables or cached_per_module_name" -q`

Expected: FAIL, 因为当前 `diagnostics.manager` 仍保留全局表且 `get_logger()` 每次新建对象

**Step 3: Write minimal implementation**

在 `src/diagnostics/manager.py` 中:

```python
class LogManager:
    def __init__(self, ...):
        self._loggers = {}

    def get_logger(self, module_name: str):
        logger = self._loggers.get(module_name)
        if logger is None:
            logger = Logger(self, module_name)
            self._loggers[module_name] = logger
        return logger
```

并把全局映射表改为紧凑分支或最小常量表达, 删除运行时无用协议占位类。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_logging.py -k "legacy_runtime_tables or cached_per_module_name" -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/services/test_logging.py tests/unit/services/test_transport_car_logging.py src/diagnostics/manager.py
git commit -m "refactor(diagnostics): shrink logger runtime footprint"
```

### Task 2: 重构 logger 的低分配发射路径

**Files:**
- Modify: `tests/unit/services/test_logging.py`
- Modify: `src/diagnostics/manager.py`
- Modify: `src/diagnostics/format.py`
- Modify: `src/diagnostics/sink.py`
- Test: `tests/unit/services/test_logging.py`

**Step 1: Write the failing test**

补测试锁定:

```python
def test_high_frequency_log_is_dropped_after_format_memory_error() -> None:
    sink = MemoryErrorSink()
    manager = LogManager(sinks=[sink])
    logger = manager.get_logger("vision.state")

    logger.info("POLL")
    logger.info("POLL")

    assert sink.lines in ([], ["I [vision.state  ] POLL\r\n"])


def test_filtered_debug_log_does_not_require_message_concatenation() -> None:
    manager = LogManager(level=LOG_INFO)

    assert manager.should_emit(LOG_DEBUG, "vision.state") is False
```

如果需要, 用一个会在格式化阶段抛 `MemoryError` 的替身来锁定“高频日志直接退让, 不持续打印 `log.oom`”。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_logging.py -k "format_memory_error or concatenation" -q`

Expected: FAIL, 因为当前实现仍会构造 fallback 文本并持续走格式化链路

**Step 3: Write minimal implementation**

在 `src/diagnostics/manager.py` 中实现更短发射路径:

```python
def emit(self, level: int, module_name: str, message: str) -> None:
    if level < self.level:
        return
    if not self._module_allowed(module_name):
        return
    try:
        text = format_log_record(level, module_name, message, self.color_enabled)
    except MemoryError:
        if level <= self._drop_level:
            return
        return
    self._write_to_sinks(level, text)
```

同时把 `format.py` 改成不依赖额外 `LogRecord` 对象的轻量接口, 常见 ASCII/无色场景优先走快路径。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_logging.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/services/test_logging.py src/diagnostics/manager.py src/diagnostics/format.py src/diagnostics/sink.py
git commit -m "refactor(diagnostics): add low-allocation log emit path"
```

### Task 3: 锁定视觉运行时 owner 边界

**Files:**
- Create: `src/vision/runtime.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Modify: `tests/unit/services/test_vision_protocol.py`
- Modify: `tests/unit/services/test_vision_state_machine.py`
- Test: `tests/unit/services/test_transport_car_vision_integration.py`
- Test: `tests/unit/services/test_vision_protocol.py`

**Step 1: Write the failing test**

补测试锁定新的 owner 关系:

```python
def test_vision_runtime_is_single_owner_for_frames_and_target() -> None:
    runtime = VisionRuntime(timeout_ms=200)

    assert runtime.latest_observation is None
    assert runtime.resolved_target is None
    assert runtime.cam_a.frame is None
    assert runtime.cam_b.frame is None


def test_transport_car_does_not_keep_legacy_vision_duplicates() -> None:
    car = TransportCar(vehicle_role="main")

    assert "vision_protocol" not in car.__dict__
    assert "vision_state_machine" not in car.__dict__
    assert "_vision_resolved_target" not in car.__dict__
```

再补一个测试, 锁定 `camera_frames` 这种临时聚合不再是选择入口。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_vision_protocol.py -k "single_owner or legacy_vision_duplicates" -q`

Expected: FAIL, 因为当前视觉状态仍分散在 `protocol/coordinator/transport_car` 多处

**Step 3: Write minimal implementation**

创建 `src/vision/runtime.py`, 先定义最小 owner 结构:

```python
class VisionCameraSlot:
    __slots__ = ("camera_id", "frame", "pending_frame_id", "pending_items", "timestamp_ms")


class VisionRuntime:
    __slots__ = (
        "timeout_ms",
        "cam_a",
        "cam_b",
        "latest_observation",
        "selected_input",
        "resolved_target",
        "snapshot_buffer",
    )
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_vision_protocol.py -k "single_owner or legacy_vision_duplicates" -q`

Expected: PASS

**Step 5: Commit**

```bash
git add src/vision/runtime.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_vision_protocol.py tests/unit/services/test_vision_state_machine.py
git commit -m "refactor(vision): introduce single runtime owner"
```

### Task 4: 让协议解析直接写入视觉 owner

**Files:**
- Modify: `src/vision/protocol.py`
- Modify: `src/vision/runtime.py`
- Modify: `tests/unit/services/test_vision_protocol.py`
- Test: `tests/unit/services/test_vision_protocol.py`

**Step 1: Write the failing test**

补测试锁定:

```python
def test_protocol_writes_frame_result_into_runtime_slot() -> None:
    runtime = VisionRuntime(timeout_ms=200)
    protocol = VisionProtocol(runtime)

    protocol.try_parse_observation(
        "camera_id=cam_a,frame_id=1,category=cargo,left=1,top=2,right=3,bottom=4",
        source="uart6",
        now_ms=1000,
    )
    protocol.try_parse_observation("camera_id=cam_a,frame_id=1,frame_end=1", source="uart6", now_ms=1001)

    assert runtime.cam_a.frame is not None
    assert runtime.latest_observation is not None
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py -k "runtime_slot" -q`

Expected: FAIL, 因为当前 `VisionProtocol` 仍自己持有 `_latest` 和 `_latest_frame`

**Step 3: Write minimal implementation**

把 `VisionProtocol` 改成围绕 `VisionRuntime` 工作:

```python
class VisionProtocol:
    def __init__(self, runtime: VisionRuntime):
        self.runtime = runtime

    def _slot_for_camera(self, camera_id: str):
        return self.runtime.get_slot(camera_id)
```

删除协议内部重复保存的 latest/pending 缓存, 统一写入 owner。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_vision_protocol.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add src/vision/protocol.py src/vision/runtime.py tests/unit/services/test_vision_protocol.py
git commit -m "refactor(vision): route protocol state into runtime owner"
```

### Task 5: 让 coordinator 降为 facade 并复用 owner

**Files:**
- Modify: `src/vision/coordinator.py`
- Modify: `src/vision/transforms.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Modify: `tests/unit/services/test_vision_state_machine.py`
- Test: `tests/unit/services/test_transport_car_vision_integration.py`

**Step 1: Write the failing test**

补测试锁定:

```python
def test_coordinator_build_snapshot_reads_runtime_buffer() -> None:
    coordinator = build_runtime_backed_coordinator()

    snapshot = coordinator.build_snapshot(1000)

    assert snapshot["state"] == "IDLE"


def test_select_state_machine_input_no_longer_requires_camera_frames_dict() -> None:
    runtime = VisionRuntime(timeout_ms=200)

    selected = select_state_machine_input(runtime=runtime)

    assert selected.observation is None
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py -k "runtime_buffer or camera_frames_dict" -q`

Expected: FAIL, 因为当前 coordinator 和 transforms 仍依赖散落状态与 `camera_frames` 聚合

**Step 3: Write minimal implementation**

在 `src/vision/coordinator.py` 中保留外部 facade 形状, 但内部只代理 `VisionRuntime`:

```python
class VisionCoordinator:
    def __init__(self, runtime, protocol, state_machine, frame_logger=None):
        self.runtime = runtime
        self.protocol = protocol
        self.state_machine = state_machine
```

把 `select_state_machine_input()` 改成直接接受 `runtime` 或槽位输入, 去掉高频 `camera_frames` 中间 `dict`。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_vision_state_machine.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add src/vision/coordinator.py src/vision/transforms.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_vision_state_machine.py
git commit -m "refactor(vision): make coordinator a runtime facade"
```

### Task 6: 收缩 `TransportCar` 为编排层

**Files:**
- Modify: `src/services/transport_car.py`
- Modify: `src/services/runtime/uart_ingress.py`
- Modify: `src/services/runtime/diagnostics_facade.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Modify: `tests/unit/services/test_transport_car_logging.py`
- Modify: `tests/unit/services/test_transport_car_diag_mode.py`
- Modify: `tests/unit/services/test_transport_car_diag_snapshots.py`
- Test: `tests/unit/services/test_transport_car_vision_integration.py`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: Write the failing test**

补测试锁定:

```python
def test_transport_car_keeps_only_runtime_owners() -> None:
    car = TransportCar(vehicle_role="main")

    assert "vision_runtime" in car.__dict__
    assert "vision_protocol" not in car.__dict__
    assert "vision_state_machine" not in car.__dict__


def test_diagnostics_facade_reads_from_runtime_owner() -> None:
    facade = DiagnosticsFacade(runtime)

    assert facade.build_vision_snapshot()["state"] == "DISABLED"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_diag_mode.py tests/unit/services/test_transport_car_diag_snapshots.py -k "runtime_owners or reads_from_runtime_owner" -q`

Expected: FAIL, 因为当前 `TransportCar` 仍直接挂多处视觉与诊断对象

**Step 3: Write minimal implementation**

在 `src/services/transport_car.py` 中:

```python
def _build_vision_coordinator(self):
    runtime = VisionRuntime(timeout_ms=VISION_OBSERVATION_TIMEOUT_MS)
    protocol = VisionProtocol(runtime)
    machine = VisionStateMachine(self._build_vision_state_config(), debug_sink=self._emit_vision_debug)
    self.vision_runtime = runtime
    return VisionCoordinator(runtime=runtime, protocol=protocol, state_machine=machine, frame_logger=self._log_vision_frame_boundary)
```

同时把诊断 facade 改成从 runtime owner 读取, 删掉历史重复入口。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_diag_mode.py tests/unit/services/test_transport_car_diag_snapshots.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add src/services/transport_car.py src/services/runtime/uart_ingress.py src/services/runtime/diagnostics_facade.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_diag_mode.py tests/unit/services/test_transport_car_diag_snapshots.py
git commit -m "refactor(services): shrink runtime orchestration state"
```

### Task 7: 对其余 `src/` 运行时代码做逐文件内存清查

**Files:**
- Modify: `src/control/*.py`
- Modify: `src/filters/*.py`
- Modify: `src/storage/*.py`
- Modify: `src/hardware/*.py`
- Modify: `src/config/*.py`
- Modify: `src/utils/*.py`
- Modify: `tests/unit/services/test_micropython_compatibility.py`
- Modify: `tests/unit/services/test_legacy_path_removal.py`
- Test: `tests/unit`

**Step 1: Write the failing test**

优先补 1 个 repo 级结构测试, 锁定明显的模块级冗余不会回流:

```python
def test_runtime_modules_do_not_expose_unneeded_legacy_state() -> None:
    import diagnostics.manager as manager_module
    import services.transport_car as transport_car_module

    assert hasattr(manager_module, "LEVEL_NAME_TO_VALUE") is False
    assert hasattr(transport_car_module.TransportCar, "vision_protocol") is False
```

然后按实际清查到的问题补对应失败测试, 一次锁一个结构问题。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_micropython_compatibility.py tests/unit/services/test_legacy_path_removal.py -q`

Expected: FAIL 或出现需要新增断言的缺口

**Step 3: Write minimal implementation**

按文件逐个清理:

- 删除不必要模块级全局变量
- 删除无价值 wrapper/helper
- 删除重复状态副本
- 把能懒加载的对象改为按需创建

每次改动只处理一类明确问题, 不做装饰性改写。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit -q`

Expected: PASS

**Step 5: Commit**

```bash
git add src/control src/filters src/storage src/hardware src/config src/utils tests/unit/services/test_micropython_compatibility.py tests/unit/services/test_legacy_path_removal.py
git commit -m "refactor(runtime): remove redundant module-level state"
```

### Task 8: 记录结论并做最终回归

**Files:**
- Modify: `.progress/entries/2026/2026-03-15-1.md`
- Modify: `.progress/PROGRESS.md`
- Test: `tests/unit`
- Test: `tests/contract`

**Step 1: Update progress**

把以下结论写入 `.progress/`:

- 本轮已对 `src/` 上线运行时代码做 repo 级低内存重构
- 已重点清理 logger 自身常驻结构和视觉运行时分散 owner
- 这类问题既可能来自代码侧对象生命周期/冗余状态, 也可能与板子硬件或 MicroPython 固件状态异常有关

**Step 2: Run final regression**

Run: `python3 -m pytest tests/unit tests/contract -q`

Expected: PASS

**Step 3: Commit**

```bash
git add .progress/entries/2026/2026-03-15-1.md .progress/PROGRESS.md
git commit -m "docs(progress): record repo-wide runtime memory refactor"
```
