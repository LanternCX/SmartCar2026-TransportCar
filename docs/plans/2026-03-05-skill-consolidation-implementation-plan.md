# Skill Consolidation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge architecture guidance into `code-standards`, rewrite all project skills in `.agents/skills`, and enforce project-local Git policy.

**Architecture:** `code-standards` becomes the single authority for code + architecture constraints, while `git-workflow` remains the single authority for Git process rules. Other skills are rewritten to be focused and to reference canonical policy owners instead of duplicating policy text.

**Tech Stack:** Markdown documentation in project-local skill system (`.agents/skills/*/SKILL.md`).

---

### Task 1: Build merged `code-standards`

**Files:**
- Modify: `.agents/skills/code-standards/SKILL.md`

**Step 1: Write the failing test**

Define expected checks:
- file includes architecture layers and dependency rules previously in `architecture-guardian`
- file includes explicit rule: use project `git-workflow`; do not use superpowers git workflow as project policy

**Step 2: Run test to verify it fails**

Run: `rg "Do not use superpowers|Forbidden Dependencies|Architecture Layers" .agents/skills/code-standards/SKILL.md`
Expected: missing at least one required phrase/section.

**Step 3: Write minimal implementation**

Rewrite `code-standards` to include merged architecture sections and explicit Git policy rule.

**Step 4: Run test to verify it passes**

Run: `rg "Do not use superpowers|Forbidden Dependencies|Architecture Layers" .agents/skills/code-standards/SKILL.md`
Expected: all required markers found.

### Task 2: Rewrite remaining project skills

**Files:**
- Modify: `.agents/skills/control-system/SKILL.md`
- Modify: `.agents/skills/hardware-integration/SKILL.md`
- Modify: `.agents/skills/git-workflow/SKILL.md`

**Step 1: Write the failing test**

Define expected checks:
- each skill has clear trigger-based description
- each skill has practical, concise structure aligned with writing-skills guidance
- non-git skills include pointer to project `git-workflow`

**Step 2: Run test to verify it fails**

Run: `rg "Use when|git-workflow|superpowers" .agents/skills/{control-system,hardware-integration,git-workflow}/SKILL.md`
Expected: wording gaps in at least one file.

**Step 3: Write minimal implementation**

Rewrite each skill with normalized structure and explicit project Git policy wording.

**Step 4: Run test to verify it passes**

Run: `rg "Use when|git-workflow|superpowers" .agents/skills/{control-system,hardware-integration,git-workflow}/SKILL.md`
Expected: all required markers present.

### Task 3: Remove old skill and fix references

**Files:**
- Delete: `.agents/skills/architecture-guardian/SKILL.md`
- Delete: `.agents/skills/architecture-guardian/` (if empty)
- Modify: `.agents/skills/README.md`
- Modify: `Readme.md`

**Step 1: Write the failing test**

Define expected checks:
- no repository references to `architecture-guardian`
- no repository references to non-existent `skill-manager`

**Step 2: Run test to verify it fails**

Run: `rg "architecture-guardian|skill-manager" .agents/skills/README.md Readme.md`
Expected: matches exist before edits.

**Step 3: Write minimal implementation**

Update docs to point architecture guidance to `code-standards` and remove stale skill-manager mentions.

**Step 4: Run test to verify it passes**

Run: `rg "architecture-guardian|skill-manager" .agents/skills/README.md Readme.md`
Expected: no matches.

### Task 4: Final validation

**Files:**
- Verify only (no code changes expected)

**Step 1: Write the failing test**

Define expected checks:
- all remaining skills exist and are readable
- project Git policy wording appears consistently

**Step 2: Run test to verify it fails**

Run baseline checks before final polish.

**Step 3: Write minimal implementation**

Fix any wording or reference drift from Task 1-3.

**Step 4: Run test to verify it passes**

Run:
- `ls .agents/skills`
- `rg "superpowers.*git workflow|project.*git-workflow|git-flow|conventional" .agents/skills -g "**/SKILL.md"`
- `rg "architecture-guardian|skill-manager" .agents/skills Readme.md`

Expected:
- no deleted-skill references;
- consistent Git policy statements;
- final skill inventory coherent.
