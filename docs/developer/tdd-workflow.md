# TDD Workflow (Project Integration)

This document defines how superpowers TDD is executed in this repository.

## Core Rule

No production code change without a failing test first.

Use the strict loop:

1. RED: add failing test
2. GREEN: implement minimal fix/feature
3. REFACTOR: improve while tests stay green

## Test Layers in This Project

- `tests/unit/`: deterministic host-side tests
- `tests/contract/`: command behavior contracts with fakes
- `tests/hil/`: board-level validation checklist

## Layer Selection

- Pure logic change (`control/`, `filters/`, parser/router/storage/utils): start with `unit`
- Command behavior change (`services/commands/`): add `contract` test first
- Hardware/runtime loop coupling (`hardware/`, `services/transport_car.py`): add `hil` evidence and at least one host-side regression where feasible

## Commands

```bash
python3 -m pytest tests/unit -q
python3 -m pytest tests/contract -q
python3 -m pytest tests/unit tests/contract -q
```

## PR Gate

PRs and pushes must keep `tests/unit` and `tests/contract` green.

## Completion Checklist

- Failing test evidence captured before implementation
- Target layer tests pass locally
- CI test workflow passes
- If hardware-coupled: HIL scenario recorded under `tests/hil/`
