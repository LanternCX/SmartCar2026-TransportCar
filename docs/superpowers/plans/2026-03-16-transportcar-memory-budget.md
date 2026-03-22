# 搬运车最小内存占用重构 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 `TransportCar` 从 God object 重构为“最小核心 + 按需装配”的运行时编排器, 并把最小内存占用指标写入项目规范和 code review 门禁。

**Architecture:** 先建立内存资产台账和板端测量基线, 再抽出 `RuntimeCore`、`MinimalCommandRuntime`、`MinimalDiagnostics` 等 owner, 最后将控制、视觉、完整命令系统按功能延迟装配。整个过程以板端 `mem_free` 指标和最小诊断面存活为第一验收标准, 不是以文件拆分本身为标准。

**Tech Stack:** Python, MicroPython, pytest, mpy-cli, RT1021, repo-local `docs/superpowers/memory/`

---

### Task 1: 固化内存资产台账和 review 目标

**Files:**
- Create: `docs/developer/transportcar-memory-assets.md`
- Modify: `docs/superpowers/specs/2026-03-16-transportcar-memory-budget-design.md`
- Modify: `docs/superpowers/memory/milestone/entries/2026-03/2026-03-16-1.md`

**Step 1: 写出台账模板**

```markdown
| Asset | Owner | Phase | Class | Trigger | Duplicate | Action | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| uart3 | RuntimeCore | core_init | A | boot | no | keep | stage2 probe |
```

**Step 2: 先录入首批资产**

- `uart3/uart6`
- `oom_count/last_oom_stage`
- `router`
- `vision runtime`
- `chassis_state`

**Step 3: 更新设计文档中的指标定义**

- 补齐 `mem_free_after_import`
- 补齐 `mem_free_after_core_init`
- 补齐 `diag_survival`

**Step 4: 自检**

Run: `python3 -m pytest --collect-only -q`
Expected: 仅校验测试集可收集, 不新增失败

**Step 5: Commit**

```bash
git add docs/developer/transportcar-memory-assets.md docs/superpowers/specs/2026-03-16-transportcar-memory-budget-design.md docs/superpowers/memory/milestone/entries/2026-03/2026-03-16-1.md
git commit -m "docs(memory): add transport runtime asset ledger"
```

### Task 2: 建立板端内存测量探针契约

**Files:**
- Modify: `tools/stage2_full_trace_probe.py`
- Create: `tests/unit/tools/test_stage2_full_trace_probe_contract.py`

**Step 1: 写失败测试**

```python
def test_stage2_full_trace_probe_reports_required_stages() -> None:
    output = build_expected_trace_lines()
    assert "TRACE after_import_transport_car" in output
    assert "TRACE after_core_init" in output
    assert "TRACE after_feature_init" in output
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/tools/test_stage2_full_trace_probe_contract.py -q`
Expected: FAIL, 因当前探针尚未输出完整阶段

**Step 3: 最小实现**

```python
def _print_mem(tag):
    gc.collect()
    print("TRACE %s mem_free=%d" % (tag, gc.mem_free()))
```

并把阶段扩展到:
- `after_import_transport_car`
- `after_core_init`
- `after_feature_init`
- `runtime_idle`

**Step 4: 跑测试确认通过**

Run: `python3 -m pytest tests/unit/tools/test_stage2_full_trace_probe_contract.py -q`
Expected: PASS

**Step 5: 板端验证**

Run: `mpy-cli upload --local "tools/stage2_full_trace_probe.py" --remote ".agent/stage2_full_trace_probe.py" --port "/dev/cu.usbmodem11101" --no-interactive --yes && mpy-cli run --path ".agent/stage2_full_trace_probe.py" --port "/dev/cu.usbmodem11101" --no-interactive --yes`
Expected: 输出完整 TRACE 阶段和 `mem_free`

**Step 6: Commit**

```bash
git add tools/stage2_full_trace_probe.py tests/unit/tools/test_stage2_full_trace_probe_contract.py
git commit -m "test(memory): define board trace probe stages"
```

### Task 3: 抽出 RuntimeCore

**Files:**
- Create: `src/services/runtime/runtime_core.py`
- Modify: `src/services/transport_car.py`
- Test: `tests/unit/services/test_runtime_core.py`
- Test: `tests/unit/services/test_transport_car_logging.py`

**Step 1: 写失败测试**

```python
def test_runtime_core_owns_uart_role_and_oom_fields() -> None:
    core = RuntimeCore(vehicle_role="main")
    assert core.vehicle_role == "main"
    assert hasattr(core, "uart3")
    assert core.oom_count == 0
```

**Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/unit/services/test_runtime_core.py -q`
Expected: FAIL, 因 `RuntimeCore` 尚不存在

**Step 3: 最小实现**

```python
class RuntimeCore:
    def __init__(self, vehicle_role, uart3=None, uart6=None):
        self.vehicle_role = vehicle_role
        self.uart3 = uart3 if uart3 is not None else create_uart3()
        self.uart6 = uart6 if uart6 is not None else create_uart6()
        self.oom_count = 0
        self.last_oom_stage = None
        self.last_exception_text = "none"
```

**Step 4: 让 `TransportCar` 只持有 `RuntimeCore` 引用**

- `TransportCar` 中删除重复字段 owner
- `_emit_error_log()` / `_record_oom()` 改为写入 `RuntimeCore`

**Step 5: 跑测试确认通过**

Run: `python3 -m pytest tests/unit/services/test_runtime_core.py tests/unit/services/test_transport_car_logging.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add src/services/runtime/runtime_core.py src/services/transport_car.py tests/unit/services/test_runtime_core.py tests/unit/services/test_transport_car_logging.py
git commit -m "refactor(runtime): extract transport runtime core"
```

### Task 4: 抽出 MinimalDiagnostics

**Files:**
- Create: `src/services/runtime/minimal_diagnostics.py`
- Modify: `src/services/runtime/diagnostics_facade.py`
- Modify: `src/services/transport_car.py`
- Test: `tests/unit/services/test_minimal_diagnostics.py`
- Test: `tests/contract/services/commands/test_diag_queries.py`

**Step 1: 写失败测试**

```python
def test_minimal_diagnostics_reads_core_without_copying_state() -> None:
    diag = MinimalDiagnostics(core=fake_core)
    snapshot = diag.build_health_snapshot()
    assert snapshot["oom_count"] == 1
```

**Step 2: 跑测试确认失败**

Run: `python3 -m pytest tests/unit/services/test_minimal_diagnostics.py -q`
Expected: FAIL

**Step 3: 最小实现**

```python
class MinimalDiagnostics:
    def __init__(self, core, motion=None, vision=None):
        self._core = core
        self._motion = motion
        self._vision = vision
```

并保证 diagnostics 只读 owner, 不缓存第二份状态

**Step 4: 跑单测和 contract**

Run: `python3 -m pytest tests/unit/services/test_minimal_diagnostics.py tests/contract/services/commands/test_diag_queries.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/services/runtime/minimal_diagnostics.py src/services/runtime/diagnostics_facade.py src/services/transport_car.py tests/unit/services/test_minimal_diagnostics.py tests/contract/services/commands/test_diag_queries.py
git commit -m "refactor(diagnostics): extract minimal diagnostics owner"
```

### Task 5: 抽出 MinimalCommandRuntime 并保活最小 query

**Files:**
- Create: `src/services/runtime/minimal_command_runtime.py`
- Modify: `src/services/runtime/uart_ingress.py`
- Modify: `src/services/transport_car.py`
- Test: `tests/unit/services/test_minimal_command_runtime.py`
- Test: `tests/unit/services/test_uart_ingress.py`

**Step 1: 写失败测试**

```python
def test_minimal_command_runtime_only_registers_health_tick_vision_queries() -> None:
    runtime = MinimalCommandRuntime(...)
    assert runtime.registered_query_tokens() == ("health", "tick", "vision")
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/services/test_minimal_command_runtime.py -q`
Expected: FAIL

**Step 3: 最小实现**

```python
MINIMAL_QUERY_TOKENS = ("health", "tick", "vision")
```

并将完整 handlers 装配从构造期移动到显式 `activate_full_commands()`

**Step 4: 运行测试**

Run: `python3 -m pytest tests/unit/services/test_minimal_command_runtime.py tests/unit/services/test_uart_ingress.py -q`
Expected: PASS

**Step 5: 板端验证**

Run: `python3 tools/run_stage2_smoke.py --port "/dev/cu.usbmodem11101"`
Expected: 至少 `status=ok`; 如仍是 `lite`, 也必须能稳定回答最小 query

**Step 6: Commit**

```bash
git add src/services/runtime/minimal_command_runtime.py src/services/runtime/uart_ingress.py src/services/transport_car.py tests/unit/services/test_minimal_command_runtime.py tests/unit/services/test_uart_ingress.py
git commit -m "refactor(command): preserve minimal query runtime"
```

### Task 6: 抽出 MotionRuntime

**Files:**
- Create: `src/services/runtime/motion_runtime.py`
- Modify: `src/services/transport_car.py`
- Test: `tests/unit/services/test_motion_runtime.py`
- Test: `tests/unit/services/test_transport_car_diag_mode.py`

**Step 1: 写失败测试**

```python
def test_motion_runtime_owns_chassis_and_pid_chain() -> None:
    motion = MotionRuntime(diagnostic_mode=True)
    assert motion.chassis_state is not None
    assert motion.controller is not None
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/services/test_motion_runtime.py -q`
Expected: FAIL

**Step 3: 最小实现**

```python
class MotionRuntime:
    def __init__(self, diagnostic_mode=False):
        self.diagnostic_mode = bool(diagnostic_mode)
        self.chassis_state = ChassisState()
```

逐步迁移 `imu`、电机、编码器、姿态和控制链 owner

**Step 4: 运行测试**

Run: `python3 -m pytest tests/unit/services/test_motion_runtime.py tests/unit/services/test_transport_car_diag_mode.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/services/runtime/motion_runtime.py src/services/transport_car.py tests/unit/services/test_motion_runtime.py tests/unit/services/test_transport_car_diag_mode.py
git commit -m "refactor(motion): extract transport motion runtime"
```

### Task 7: 抽出 VisionRuntimeService 并按角色 / 功能装配

**Files:**
- Create: `src/services/runtime/vision_runtime_service.py`
- Modify: `src/services/transport_car.py`
- Test: `tests/unit/services/test_transport_car_vision_integration.py`
- Test: `tests/unit/services/test_vision_state_machine.py`

**Step 1: 写失败测试**

```python
def test_aux_role_does_not_activate_full_vision_runtime() -> None:
    service = VisionRuntimeService(vehicle_role="aux")
    assert service.enabled is False
```

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: FAIL

**Step 3: 最小实现**

```python
class VisionRuntimeService:
    def __init__(self, vehicle_role):
        self.enabled = vehicle_role == "main"
```

然后把协议缓存、状态机推进、frame slot owner 从 `TransportCar` 迁出

**Step 4: 运行测试**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_vision_state_machine.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/services/runtime/vision_runtime_service.py src/services/transport_car.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_vision_state_machine.py
git commit -m "refactor(vision): extract role-aware vision runtime"
```

### Task 8: 更新代码规范和 code review 门禁

**Files:**
- Modify: `AGENTS.md`
- Modify: `.agents/skills/code-standards/SKILL.md`
- Modify: `.agents/skills/code-standards/README.md`
- Create: `docs/developer/memory-review.md`

**Step 1: 先写文档差异草案**

```markdown
## 内存占用门禁
- review 一号目标是最小内存占用指标
- 结构更清晰不能替代内存证据
```

**Step 2: 加入硬规则**

- import-time 禁止自动发现 / 自动注册
- 模块级可变运行时全局为阻断项
- 所有新增常驻对象必须标注 A / B / C / D / E 类
- review 必须输出内存证据

**Step 3: 自检文档一致性**

Run: `python3 -m pytest --collect-only -q`
Expected: PASS, 不因规范改动破坏测试导入

**Step 4: Commit**

```bash
git add AGENTS.md .agents/skills/code-standards/SKILL.md .agents/skills/code-standards/README.md docs/developer/memory-review.md
git commit -m "docs(standards): gate reviews by memory budget"
```

### Task 9: 板端验收与 HIL 留证

**Files:**
- Modify: `tests/hil/2026-03-dual-camera-polling.md`
- Modify: `docs/superpowers/memory/milestone/INDEX.md`
- Modify: `docs/superpowers/memory/milestone/entries/2026-03/2026-03-16-1.md`

**Step 1: 运行主机测试**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS

**Step 2: 运行板端 Stage 2**

Run: `python3 tools/run_stage2_smoke.py --port "/dev/cu.usbmodem11101"`
Expected: `status=ok`, 且 full 路径指标优于重构前

**Step 3: 运行板端 trace probe**

Run: `mpy-cli run --path ".agent/stage2_full_trace_probe.py" --port "/dev/cu.usbmodem11101" --no-interactive --yes`
Expected: 输出 `after_import / after_core_init / after_feature_init / runtime_idle`

**Step 4: 更新 HIL 记录**

- 记录 `mem_free` 基线
- 记录最小诊断面是否存活
- 记录主车 / 辅车装配差异

**Step 5: Commit**

```bash
git add tests/hil/2026-03-dual-camera-polling.md docs/superpowers/memory/milestone/INDEX.md docs/superpowers/memory/milestone/entries/2026-03/2026-03-16-1.md
git commit -m "test(hil): record transport runtime memory evidence"
```
