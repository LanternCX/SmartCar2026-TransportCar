# refactor

## Type
refactor

## Use When
Use this type when you need precedent for structural cleanup, owner-boundary changes, package reshaping, or maintainability-first architecture work.

## Avoid When
Avoid this type when the main value is a new feature milestone or a debug closure with a single failure path.

## Record When
Use this type for larger complete structural improvements that substantially improve code organization, boundaries, or maintainability without centering on new user-facing behavior.

## Avoid Recording When
Do not record feature-led delivery or bugfix-led debugging closures in this type.

## Entry Template
Use `docs/superpowers/memory/refactor/ENTRY.md`.

## Notes
- Record only closed refactoring units whose structural value is worth revisiting.
- Prefer refactor when the main value is clearer boundaries, lower complexity, or safer future change.
