# Remove Debug Breakpoint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the old `TransportCar.debug()` breakpoint-wait mechanism completely while keeping visual transition logging intact.

**Architecture:** Delete the runtime breakpoint API, helper state, and associated tests instead of leaving compatibility stubs. Keep the visual debug event flow, but make it a pure logging path with no pause/resume semantics.

**Tech Stack:** Python, pytest unit tests, SmartCar services layer.

---

### Task 1: Remove runtime breakpoint behavior from TransportCar

**Files:**
- Modify: `src/services/transport_car.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`
- Delete: `tests/unit/services/test_transport_car_debug_breakpoint.py`

**Step 1: Write the failing test**

Adjust `tests/unit/services/test_transport_car_vision_integration.py` so the visual debug tests only assert log emission and explicitly assert the breakpoint API is gone:

```python
def test_transport_car_has_no_debug_breakpoint_api() -> None:
    car = build_transport_car()

    assert hasattr(car, "debug") is False
```

Keep the existing visual log assertion, but remove the part that patches or expects breakpoint entry.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: FAIL because `TransportCar` still exposes `debug()` and related breakpoint paths.

**Step 3: Write minimal implementation**

Delete from `src/services/transport_car.py`:

- `_debug_waiting`
- `_debug_resume_requested`
- `debug()`
- `_clear_motor_outputs_for_debug()`
- `_poll_debug_resume_uart()`
- `_trim_debug_resume_fragment()`
- `_discard_uart_source()`
- any remaining branches that only serve the old breakpoint flow

Delete `tests/unit/services/test_transport_car_debug_breakpoint.py` entirely.

Update the vision integration test file so it no longer references fake breakpoint callbacks and only verifies logger-based visual output.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/transport_car.py tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_debug_breakpoint.py
git commit -m "refactor(services): remove debug breakpoint flow"
```

### Task 2: Remove obsolete design artifact and run regression checks

**Files:**
- Delete: `docs/superpowers/plans/2026-03-09-vision-transition-debug-breakpoint.md`

**Step 1: Write the failing test**

There is no code-path test for deleting the obsolete plan doc. The regression check for this task is that host tests still pass after the deletion and code cleanup.

**Step 2: Run test to verify current focused suite passes before doc cleanup**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_logging.py -q`
Expected: PASS.

**Step 3: Write minimal implementation**

Delete `docs/superpowers/plans/2026-03-09-vision-transition-debug-breakpoint.md`.

**Step 4: Run test to verify no regression**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-03-09-vision-transition-debug-breakpoint.md
git commit -m "docs: drop obsolete debug breakpoint plan"
```

### Task 3: Final verification

**Files:**
- Verify only

**Step 1: Run focused deletion checks**

Run: `python3 -m pytest tests/unit/services/test_transport_car_vision_integration.py tests/unit/services/test_transport_car_logging.py -q`
Expected: PASS.

**Step 2: Run full host suite**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS.

**Step 3: Inspect working tree**

Run: `git status --short`
Expected: only the intended debug-breakpoint removals and existing in-progress logging work remain.

**Step 4: Report evidence**

Summarize:

- removed runtime debug breakpoint API and helper state
- removed obsolete tests and plan doc
- preserved visual transition logging behavior
- host verification evidence and any remaining device-side follow-up
