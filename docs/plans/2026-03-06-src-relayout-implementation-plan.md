# Src Relayout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将业务代码与根目录脚本彻底迁移到 `src/` 结构并保持现有运行行为与测试可用性。

**Architecture:** 采用“先测试约束布局,后目录迁移,再配置适配”的三段式重构流程。业务模块保持原有导入语义（`from control...`）,通过 `tests/conftest.py` 与 `pyrightconfig.json` 对 `src` 做路径注入。启动入口使用 `src/boot.py` 并转发到 `src/script/*`。

**Tech Stack:** Python 3.10+, pytest, pyright, mpy-cli

---

### Task 1: 布局约束测试（RED）

**Files:**
- Create: `tests/unit/test_source_layout.py`

**Step 1: Write the failing test**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_dirs_moved_under_src() -> None:
    for name in ("config", "control", "filters", "hardware", "services", "storage", "utils"):
        assert (ROOT / "src" / name).is_dir()
        assert not (ROOT / name).exists()


def test_root_scripts_archived_under_src() -> None:
    assert (ROOT / "src" / "boot.py").is_file()
    for name in ("calibrate_gyro.py", "pid_identify.py", "remote_control.py", "test.py", "yaw_sender.py"):
        assert (ROOT / "src" / "script" / name).is_file()
        assert not (ROOT / name).exists()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_source_layout.py -q`
Expected: FAIL（当前文件仍在根目录）

### Task 2: 迁移业务目录与脚本（GREEN）

**Files:**
- Move: `config/` -> `src/config/`
- Move: `control/` -> `src/control/`
- Move: `filters/` -> `src/filters/`
- Move: `hardware/` -> `src/hardware/`
- Move: `services/` -> `src/services/`
- Move: `storage/` -> `src/storage/`
- Move: `utils/` -> `src/utils/`
- Move: `boot.py` -> `src/boot.py`
- Move: `calibrate_gyro.py` -> `src/script/calibrate_gyro.py`
- Move: `pid_identify.py` -> `src/script/pid_identify.py`
- Move: `remote_control.py` -> `src/script/remote_control.py`
- Move: `test.py` -> `src/script/test.py`
- Move: `yaw_sender.py` -> `src/script/yaw_sender.py`

**Step 1: 修改 `src/boot.py` 的脚本执行路径**

```python
execfile("script/pid_identify.py")
execfile("script/remote_control.py")
```

**Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_source_layout.py -q`
Expected: PASS

### Task 3: 配置与工具链适配

**Files:**
- Modify: `.mpy-cli.toml`
- Modify: `.mpyignore`
- Modify: `tests/conftest.py`
- Modify: `pyrightconfig.json`

**Step 1: 更新配置**

```toml
source_dir = 'src'
```

```python
# tests/conftest.py
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
```

**Step 2: 验证单元与契约测试**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS

### Task 4: 文档路径同步与回归检查（REFACTOR）

**Files:**
- Modify: `Readme.md`
- Modify: `tests/hil/scenarios/basic_motion.md`

**Step 1: 更新关键路径描述**

- 目录树改为 `src/...`。
- 启动/校准/辨识脚本改为 `src/boot.py` 与 `src/script/*.py`。

**Step 2: 运行类型检查**

Run: `python3 -m pyright`
Expected: 不新增错误

### Task 5: 最终验证

**Files:**
- Verify only

**Step 1: 运行完整主机侧测试**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: 全绿

**Step 2: 检查目录结构**

Run: `python3 -m pytest tests/unit/test_source_layout.py -q`
Expected: PASS
