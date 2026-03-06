# Test Layers

This repository uses a layered TDD validation model without changing production runtime code.

- `tests/unit/`: pure logic and deterministic module tests
- `tests/contract/`: behavior contracts with fake context/UART
- `tests/hil/`: board-level manual scenarios and acceptance criteria

## Local Commands

```bash
python3 -m pytest tests/unit -q
python3 -m pytest tests/contract -q
python3 -m pytest tests/unit tests/contract -q
```

## TDD Loop in This Repository

1. Write a failing unit/contract test first.
2. Verify the test fails for the expected reason.
3. Implement minimal change (for new features/fixes).
4. Re-run tests to green.
5. Refactor while keeping tests green.

For hardware-coupled behavior, keep `unit/contract` as fast regression layers and record board evidence in `tests/hil/`.
