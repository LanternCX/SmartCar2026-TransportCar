---
title: Embedded TDD Integration Design (Zero-Intrusion)
date: 2026-03-06
status: approved
scope: add-only (no existing source code modifications)
---

# Context

The project already follows superpowers workflows, including TDD guidance. The missing part is project-local integration so day-to-day development naturally executes TDD inside this repository.

Constraint: do not modify existing production source files under `config/`, `control/`, `filters/`, `hardware/`, `services/`, `storage/`, and `utils/`.

# Goal

Embed practical TDD into the repository by adding:

1. executable host-side tests,
2. layered test structure (unit, contract, HIL docs),
3. CI gates for automated regression,
4. project-local TDD workflow documentation and skill.

# Design Decisions

## 1) Zero-intrusion test strategy

- Add tests only; keep current runtime code untouched.
- Start from pure-logic modules for reliable host execution:
  - `control/pid_math.py`
  - `control/kinematics.py`
  - `control/pid_controller.py`
  - `filters/*.py`
  - `services/commander.py`
  - `services/command_router.py`
  - `storage/pid_store.py`
  - `storage/param_manager.py`
  - `utils/quaternion.py`

## 2) Layered verification model

- `tests/unit/`: deterministic logic tests.
- `tests/contract/`: command handler behavior against fake context/UART.
- `tests/hil/`: hardware-in-loop execution checklist and scenarios (manual for now).

## 3) CI gate design

- Add GitHub workflow to run `unit + contract` on pull requests and pushes.
- Run same checks on tag pushes so release flow inherits baseline quality.
- Keep CI minimal and stable first; HIL remains manual in this phase.

## 4) Agent workflow embedding

- Add project-level TDD skill describing how superpowers TDD maps to this repository.
- Add documentation page under `docs/developer/` as a shared checklist for human and agent.

# Non-Goals

- No production source refactor.
- No hardware abstraction rewrite.
- No mandatory full HIL automation in this phase.

# Risks and Mitigation

- Risk: tests become brittle due dynamic command registration side effects.
  - Mitigation: test command handlers directly for contracts; keep router tests isolated.
- Risk: developers bypass TDD sequence.
  - Mitigation: add explicit red/green evidence checklist in docs and skill.

# Acceptance Criteria

- Repository contains runnable pytest suite with unit and contract layers.
- CI executes these tests on PR/push/tag.
- Existing runtime source code remains unchanged.
- TDD workflow is documented and referenced in project skills.
