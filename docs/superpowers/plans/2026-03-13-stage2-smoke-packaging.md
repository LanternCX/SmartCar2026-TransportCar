# Stage 2 Smoke 打包改造 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 Stage 2 smoke 从 `src/services/` 根目录散文件改为 `src/services/stage2_smoke/` 子包, 同时保持 `services.stage2_smoke` 公共入口和板端行为不变。

**Architecture:** 以 `src/services/stage2_smoke/__init__.py` 作为稳定公共导出面, 将现有入口编排放入 `entry.py`, 将 lite/full helper 分别放入 `lite.py` 和 `full.py`。先用失败测试锁定新的包路径和 probe 导入约束, 再迁移实现并执行 host + Stage 2 验证。

**Tech Stack:** Python, pytest, MicroPython 包导入, mpy-cli Stage 2 smoke。

---

### Task 1: 锁定 Stage 2 包路径与 probe 导入契约

**Files:**
- Modify: `tests/unit/services/test_transport_car_diag_mode.py`

**Step 1: Write the failing test**

将测试期望改为新的包结构:

```python
def test_stage2_smoke_probe_launcher_avoids_from_import_for_board_compat() -> None:
    ...
    assert "from services.stage2_smoke import main" not in text
    assert '"services.stage2_smoke"' in text
    assert "services.stage2_smoke.lite" not in text


def test_stage2_smoke_runtime_entry_stays_compact_for_device_import() -> None:
    runtime_module = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "services"
        / "stage2_smoke"
        / "entry.py"
    )
    assert runtime_module.stat().st_size <= 10000
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py -k stage2_smoke -q`
Expected: FAIL, 因为当前 probe 仍导入旧的深层实现路径, 运行时入口文件也还在旧路径。

**Step 3: Write minimal implementation**

暂不改行为, 只准备后续重构所需的新测试断言。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py -k stage2_smoke -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/services/test_transport_car_diag_mode.py
git commit -m "test(services): lock stage2 smoke package layout"
```

### Task 2: 将 Stage 2 入口, lite helper 和 full helper 迁入子包

**Files:**
- Create: `src/services/stage2_smoke/__init__.py`
- Create: `src/services/stage2_smoke/entry.py`
- Create: `src/services/stage2_smoke/lite.py`
- Create: `src/services/stage2_smoke/full.py`
- Delete: `src/services/stage2_smoke.py`
- Delete: `src/services/stage2_smoke_lite.py`
- Delete: `src/services/stage2_smoke_full.py`
- Modify: `tools/stage2_smoke_probe.py`

**Step 1: Write the failing test**

沿用 Task 1 的失败测试, 再加一条公共入口不变的断言:

```python
import services.stage2_smoke as stage2_smoke_module


def test_stage2_smoke_module_keeps_public_entrypoints() -> None:
    assert hasattr(stage2_smoke_module, "collect_stage2_summary")
    assert hasattr(stage2_smoke_module, "_collect_lite_transport_summary")
    assert hasattr(stage2_smoke_module, "_collect_full_transport_summary")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py -k stage2_smoke -q`
Expected: FAIL, 因为新包尚未创建, probe 与路径断言仍不匹配。

**Step 3: Write minimal implementation**

按下面方式迁移:

```python
# src/services/stage2_smoke/__init__.py
from services.stage2_smoke.entry import (
    TOKENS,
    _CaptureUart,
    _LiteContext,
    _check_transport_source,
    _clear_modules,
    _collect_full_transport_summary,
    _collect_lite_transport_summary,
    collect_stage2_summary,
    main,
)
```

同时把旧 `stage2_smoke.py` 的内容迁到 `entry.py`, 包级 `__init__.py` 仅做受控导出, probe 切到稳定公共入口 `services.stage2_smoke`, 内部 helper 仍留在 `lite.py` / `full.py`。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py -k stage2_smoke -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/stage2_smoke tools/stage2_smoke_probe.py tests/unit/services/test_transport_car_diag_mode.py
git commit -m "refactor(services): package stage2 smoke helpers"
```

### Task 3: 验证执行器与 probe 输出解析未回归

**Files:**
- Modify: `tests/unit/tools/test_run_stage2_smoke.py`

**Step 1: Write the failing test**

若需要, 补一条针对 preview / dict summary 的解析回归测试, 但不要改动输出协议。

```python
def test_parse_probe_output_accepts_summary_dict_after_preview_lines() -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/tools/test_run_stage2_smoke.py -q`
Expected: 若解析逻辑被包路径重构意外破坏则 FAIL, 否则保持现有通过。

**Step 3: Write minimal implementation**

只修复因包路径迁移导致的 probe / runner 断言差异, 不扩展新行为。

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/tools/test_run_stage2_smoke.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/tools/test_run_stage2_smoke.py tools/run_stage2_smoke.py
git commit -m "test(services): preserve stage2 smoke runner behavior"
```

### Task 4: 做最小 host + device 验证

**Files:**
- Verify only

**Step 1: Run targeted host tests**

Run: `python3 -m pytest tests/unit/services/test_transport_car_diag_mode.py tests/unit/tools/test_run_stage2_smoke.py -q`
Expected: PASS.

**Step 2: Run Stage 2 device smoke**

Run: `python3 tools/run_stage2_smoke.py --port /dev/cu.usbmodem1101`
Expected: `status=ok`, `queries count=9 missing=none`, `smoke mode=lite` 或 `mode=full`。

**Step 3: Inspect worktree**

Run: `git status --short`
Expected: 仅包含本次 Stage 2 打包相关修改。

**Step 4: Commit**

```bash
git add src/services/stage2_smoke tools/stage2_smoke_probe.py tests/unit/services/test_transport_car_diag_mode.py tests/unit/tools/test_run_stage2_smoke.py
git commit -m "refactor(services): package stage2 smoke runtime"
```
