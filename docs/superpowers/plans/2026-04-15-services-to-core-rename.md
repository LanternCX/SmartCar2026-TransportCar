# services 改名为 core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前正式运行时包从 `src/services/` 硬切迁移到 `src/core/`，同步导入、测试和正式文档，不保留兼容层。

**Architecture:** 当前正式运行时已经收敛为共享底盘运行内核与诊断辅助两块内容，适合从 `services` 语义切到 `core` 语义。迁移采用最小硬切方案：`services.core` 改为 `core.runtime`，`services.diagnostics` 改为 `core.diagnostics`，并通过 `core.__init__` 统一导出 `TransportCar`，让主辅运行入口只依赖 `from core import TransportCar`。

**Tech Stack:** MicroPython 运行时代码、Python 主机侧 `pytest`、当前 `src/vision/*` 角色入口装配

---

### Task 1: 锁定 core 包布局与导入边界

**Files:**
- Modify: `tests/unit/test_runtime_entry_layout.py`
- Modify: `tests/unit/test_role_vision_layer_factory.py`
- Modify: `tests/contract/test_non_query_command_reply_contract.py`

- [ ] **Step 1: 写出失败测试**

```python
def test_src_runtime_root_matches_main_entry_layout() -> None:
    assert (SRC_ROOT / "main.py").exists()
    assert not (SRC_ROOT / "boot.py").exists()

    for directory_name in (
        "command",
        "config",
        "control",
        "core",
        "filters",
        "hardware",
        "script",
        "storage",
        "utils",
        "vision",
    ):
        assert (SRC_ROOT / directory_name).is_dir()

    assert (SRC_ROOT / "core" / "__init__.py").exists()
    assert (SRC_ROOT / "core" / "runtime.py").exists()
    assert (SRC_ROOT / "core" / "diagnostics.py").exists()
    assert not (SRC_ROOT / "services" / "__init__.py").exists()
    assert not (SRC_ROOT / "services" / "core.py").exists()
    assert not (SRC_ROOT / "services" / "diagnostics.py").exists()
```

```python
def test_master_runtime_builds_shared_transport_car(monkeypatch) -> None:
    runtime_module = import_runtime_module("vision.master.runtime", monkeypatch)
    core_module = ModuleType("core")

    class _TransportCar:
        pass

    setattr(core_module, "TransportCar", _TransportCar)
    monkeypatch.setitem(sys.modules, "core", core_module)

    car = runtime_module.create_transport_car()

    assert isinstance(car, _TransportCar)


def test_assistant_runtime_builds_shared_transport_car(monkeypatch) -> None:
    runtime_module = import_runtime_module("vision.assistant.runtime", monkeypatch)
    core_module = ModuleType("core")

    class _TransportCar:
        pass

    setattr(core_module, "TransportCar", _TransportCar)
    monkeypatch.setitem(sys.modules, "core", core_module)

    car = runtime_module.create_transport_car()

    assert isinstance(car, _TransportCar)
```

```python
def _import_transport_car_module():
    _install_transport_car_stubs()
    sys.modules.pop("core.runtime", None)
    return importlib.import_module("core.runtime")
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python3 -m pytest tests/unit/test_runtime_entry_layout.py tests/unit/test_role_vision_layer_factory.py tests/contract/test_non_query_command_reply_contract.py -q`
Expected: FAIL，因为当前正式包路径仍是 `services`，入口导入和契约导入都还没有切到 `core`。

### Task 2: 执行包名迁移并同步代码导入

**Files:**
- Create: `src/core/__init__.py`
- Modify: `src/core/runtime.py`（由 `src/services/core.py` 迁移）
- Modify: `src/core/diagnostics.py`（由 `src/services/diagnostics.py` 迁移）
- Delete: `src/services/__init__.py`
- Modify: `src/vision/master/runtime.py`
- Modify: `src/vision/assistant/runtime.py`
- Modify: `src/command/commands/query_tick.py`
- Modify: `src/command/commands/query_health.py`
- Modify: `src/command/commands/query_imu.py`
- Modify: `src/command/commands/query_enc.py`
- Modify: `src/command/commands/query_motor.py`

- [ ] **Step 1: 创建 core 包导出入口**

```python
"""控制执行内核包."""

from core.runtime import TransportCar
```

- [ ] **Step 2: 迁移 runtime 与 diagnostics 文件**

```bash
mv src/services/core.py src/core/runtime.py
mv src/services/diagnostics.py src/core/diagnostics.py
rm src/services/__init__.py
```

- [ ] **Step 3: 更新运行入口导入**

```python
"""主车视觉运行入口适配层."""


def create_transport_car():
    """创建主车运行链当前使用的共享底盘实例."""

    from core import TransportCar

    return TransportCar()
```

```python
"""辅车视觉运行入口适配层."""


def create_transport_car():
    """创建辅车运行链当前使用的共享底盘实例."""

    from core import TransportCar

    return TransportCar()
```

- [ ] **Step 4: 更新查询处理器导入**

```python
from command.router import router
from core.diagnostics import format_query_response
```

- [ ] **Step 5: 运行聚焦测试并确认通过**

Run: `python3 -m pytest tests/unit/test_runtime_entry_layout.py tests/unit/test_role_vision_layer_factory.py tests/contract/test_non_query_command_reply_contract.py -q`
Expected: PASS

### Task 3: 同步正式文档路径与完整回归

**Files:**
- Modify: `docs/developer/control.md`
- Modify: 任何当前正式文档里仍写 `src/services/core.py` 的位置

- [ ] **Step 1: 把正式文档路径改成 core 包**

```text
src/
  core/
    __init__.py
    runtime.py
    diagnostics.py
```

```markdown
#### [src/core/runtime.py](../../src/core/runtime.py) - 控制执行内核
```

- [ ] **Step 2: 跑完整回归**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS

- [ ] **Step 3: 检查残留旧引用**

Run: `rg "services\.core|services\.diagnostics|src/services/core\.py|src/services/diagnostics\.py" src tests docs/developer`
Expected: 无匹配
