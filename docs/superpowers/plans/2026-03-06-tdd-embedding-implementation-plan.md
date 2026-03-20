# TDD Embedding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Embed practical TDD into the repository without modifying existing production source code.

**Architecture:** Add a layered test system (`unit`, `contract`, `hil`) and a minimal CI gate that executes host-runnable layers. Keep runtime behavior untouched by validating existing modules via characterization and contract tests only.

**Tech Stack:** Python 3.11, pytest, GitHub Actions.

---

### Task 1: Add pytest baseline and test layout docs

**Files:**
- Create: `pytest.ini`
- Create: `tests/README.md`
- Create: `tests/conftest.py`

**Step 1: Write the failing test**

Attempt running pytest before config/docs exist.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q`
Expected: no project tests discovered or unstable discovery behavior.

**Step 3: Write minimal implementation**

Add deterministic pytest discovery config and layer conventions.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest --collect-only -q`
Expected: project test tree is discovered from `tests/`.

### Task 2: Add unit tests for pure logic modules

**Files:**
- Create: `tests/unit/control/test_pid_math.py`
- Create: `tests/unit/control/test_kinematics.py`
- Create: `tests/unit/control/test_pid_controller.py`
- Create: `tests/unit/filters/test_lowpass_filter.py`
- Create: `tests/unit/filters/test_spike_filter.py`
- Create: `tests/unit/filters/test_diff_limit_filter.py`
- Create: `tests/unit/services/test_commander.py`
- Create: `tests/unit/services/test_command_router.py`
- Create: `tests/unit/storage/test_pid_store.py`
- Create: `tests/unit/storage/test_param_manager.py`
- Create: `tests/unit/utils/test_quaternion.py`

**Step 1: Write the failing test**

Create tests for existing behavior, then run single file groups to confirm at least one red failure while refining expectations.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit -q`
Expected: initial failures while correcting assertions or setup.

**Step 3: Write minimal implementation**

Adjust tests only (no source modifications) until they represent real current behavior.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit -q`
Expected: all unit tests pass.

### Task 3: Add contract tests for command handlers

**Files:**
- Create: `tests/fakes/fake_context.py`
- Create: `tests/contract/services/commands/test_motion_commands.py`
- Create: `tests/contract/services/commands/test_reset_query_commands.py`

**Step 1: Write the failing test**

Define expected command side-effects using fake context/UART and run contracts first.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract -q`
Expected: setup/import failures before fake context and assertions are complete.

**Step 3: Write minimal implementation**

Finish fake context and contract tests to match current command behavior.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract -q`
Expected: all contract tests pass.

### Task 4: Add HIL checklist and project TDD docs/skill

**Files:**
- Create: `tests/hil/README.md`
- Create: `tests/hil/scenarios/basic_motion.md`
- Create: `docs/developer/tdd-workflow.md`
- Create: `.agents/skills/tdd-integration/SKILL.md`
- Modify: `.agents/skills/README.md`

**Step 1: Write the failing test**

Search for project-level TDD guidance files.

**Step 2: Run test to verify it fails**

Run: `rg "TDD|red-green-refactor" docs .agents/skills`
Expected: no dedicated project TDD integration guide yet.

**Step 3: Write minimal implementation**

Add docs and skill that map superpowers TDD to this repository layers and commands.

**Step 4: Run test to verify it passes**

Run: `rg "TDD|red-green-refactor|unit|contract|HIL" docs .agents/skills`
Expected: dedicated guidance present.

### Task 5: Add CI gate for TDD layers

**Files:**
- Create: `.github/workflows/tdd.yml`

**Step 1: Write the failing test**

Check for workflow file before creation.

**Step 2: Run test to verify it fails**

Run: `ls .github/workflows`
Expected: directory/file missing.

**Step 3: Write minimal implementation**

Create GitHub Actions workflow that installs pytest and runs `tests/unit` + `tests/contract` on PR/push/tag.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: local suite passes and workflow syntax is valid.

### Task 6: Final verification

**Files:**
- Verify only

**Step 1: Run full host-verifiable test suite**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: all pass.

**Step 2: Confirm runtime sources unchanged**

Run: `git status --short`
Expected: only added docs/tests/ci/skill files; no modifications under runtime source directories.

**Step 3: Report evidence**

Capture key command outputs and summarize TDD embedding status.
