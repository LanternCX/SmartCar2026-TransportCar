---
title: Skill Consolidation and Rewrite Design
date: 2026-03-05
status: approved
scope: .agents/skills only
---

# Context

The project skill set in `.agents/skills` needs two aligned changes:

1. Merge `architecture-guardian` content into `code-standards`.
2. Rewrite project skills using the structure and quality bar from superpowers `writing-skills`.

The user confirmed:

- Rewrite scope is only `.agents/skills`.
- `architecture-guardian` should be fully removed after merge.
- Git guidance must explicitly use project `git-workflow` and must not use superpowers git workflow.

# Goals

- Keep a single authoritative architecture+code standard skill (`code-standards`).
- Keep all project skills easier to discover and maintain.
- Eliminate stale references to removed skills.
- Enforce project-local Git policy consistently across all project skills.

# Approaches

## Approach A: Duplicate Git and architecture rules in every skill

- Pros: each skill is self-contained.
- Cons: high duplication and drift risk.

## Approach B (selected): Single-source authority with explicit cross-references

- Pros: lower maintenance, reduced contradictions, clear ownership per skill.
- Cons: readers may need one extra hop to `git-workflow`.

## Approach C: Add a new global policy skill

- Pros: central policy file.
- Cons: adds extra indirection and scope creep.

# Selected Design

## Skill set changes

- Merge `architecture-guardian/SKILL.md` into `code-standards/SKILL.md`:
  - layered architecture responsibilities,
  - dependency rules,
  - anti-patterns and refactor triggers,
  - command handler registration guidance.
- Delete `.agents/skills/architecture-guardian/`.

## Rewrite strategy (writing-skills aligned)

For each skill in `.agents/skills`:

- Keep valid frontmatter (`name`, `description`) and improve description trigger clarity.
- Use a consistent section shape: purpose, when to use, concrete rules/checklists, deliverables.
- Remove repetitive content where a canonical reference exists.
- Keep language and examples aligned with current project conventions.

## Git policy hard rule

Add explicit rule in relevant skills:

- Project Git rules are defined only in `.agents/skills/git-workflow/SKILL.md`.
- Do not use superpowers built-in git workflow as project policy.

## Reference updates

- Update `.agents/skills/README.md` to remove `architecture-guardian` and `skill-manager` references.
- Update `Readme.md` skill links to point architecture guidance to `code-standards`.

# Data Flow and Dependencies

- `code-standards` becomes the single architecture and coding quality entry point.
- `git-workflow` remains the single Git process entry point.
- Other skills reference these canonical sources to avoid duplicated policy text.

# Error Handling and Risk Control

- Risk: breaking links after skill deletion.
  - Mitigation: repository-wide reference search for `architecture-guardian` and `skill-manager`.
- Risk: inconsistent Git wording across rewritten skills.
  - Mitigation: verify required wording appears in all rewritten skill docs.

# Verification Plan

- Confirm no remaining references to `architecture-guardian` in repository docs.
- Confirm no remaining references to `skill-manager`.
- Confirm all project skill docs include/align with the project Git-policy statement.
- Review skill inventory in `.agents/skills/README.md` for consistency.

# Out of Scope

- Rewriting superpowers skills under `~/.config/opencode/skills`.
- Changing branching or commit conventions beyond project `git-workflow`.
