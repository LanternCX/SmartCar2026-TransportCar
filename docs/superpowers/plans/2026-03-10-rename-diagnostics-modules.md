# Rename Diagnostics Modules Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename the diagnostics package modules from `log_*` names to shorter package-local names without changing behavior.

**Architecture:** Keep the diagnostics package structure and all public classes/functions unchanged, and only rename the files plus import paths. Use TDD by first switching test imports to the new names so collection fails until the files are renamed.

**Tech Stack:** Python, pytest unit tests, pytest contract tests.

---

### Task 1: Rename diagnostics modules and update imports

**Files:**
- Rename: `src/diagnostics/log_manager.py` -> `src/diagnostics/manager.py`
- Rename: `src/diagnostics/log_format.py` -> `src/diagnostics/format.py`
- Rename: `src/diagnostics/log_sink.py` -> `src/diagnostics/sink.py`
- Modify: `src/services/transport_car.py`
- Modify: `src/services/commands/cmd_log_profile.py`
- Modify: `src/services/commands/cmd_log_level.py`
- Modify: `src/services/commands/cmd_log_filter.py`
- Modify: `src/services/commands/cmd_log_modules.py`
- Modify: `src/services/commands/cmd_log_color.py`
- Modify: `src/services/commands/cmd_log_reset.py`
- Modify: `src/services/commands/query_log.py`
- Modify: `tests/fakes/fake_context.py`
- Modify: `tests/unit/services/test_logging.py`
- Modify: `tests/unit/services/test_transport_car_logging.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`

**Step 1: Write the failing test**

Change existing test imports to the target module names, for example:

```python
from diagnostics.sink import RingBufferSink
from diagnostics.manager import LogManager
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_logging.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py tests/contract/services/commands/test_log_commands.py -q`
Expected: FAIL during collection with `ModuleNotFoundError` because `diagnostics.manager` / `diagnostics.sink` do not exist yet.

**Step 3: Write minimal implementation**

Rename the three diagnostics files and update all imports to:

```python
from diagnostics.manager import ...
from diagnostics.format import ...
from diagnostics.sink import ...
```

Do not change class names, function names, or runtime behavior.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_logging.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py tests/contract/services/commands/test_log_commands.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/diagnostics src/services/transport_car.py src/services/commands tests/fakes/fake_context.py tests/unit/services/test_logging.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py
git commit -m "refactor(services): rename diagnostics modules"
```

### Task 2: Final verification

**Files:**
- Verify only

**Step 1: Run focused suite**

Run: `python3 -m pytest tests/unit/services/test_logging.py tests/unit/services/test_command_router.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py tests/contract/services/commands/test_log_commands.py -q`
Expected: PASS.

**Step 2: Run full host suite**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS.

**Step 3: Inspect worktree**

Run: `git status --short`
Expected: renamed diagnostics files and import updates only, plus existing in-progress work.

**Step 4: Report evidence**

Summarize the rename, updated import paths, and verification results.
