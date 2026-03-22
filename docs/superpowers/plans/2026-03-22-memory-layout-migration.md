# Memory Layout Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate durable records from `docs/superpowers/memory/` into a `docs/superpowers/memory/` layout without leaving compatibility paths behind.

**Architecture:** Replace the progress-root structure with memory-type directories that contain discovery metadata, an index, an entry template, and month-bucketed entries. Update all repository references so future docs and skills point only at the new memory layout.

**Tech Stack:** Markdown, Python 3, repository-local docs under `docs/superpowers/`

---

### Task 1: Define the New Memory Layout

**Files:**
- Create: `docs/superpowers/memory/milestone/MEMORY.md`
- Create: `docs/superpowers/memory/milestone/INDEX.md`
- Create: `docs/superpowers/memory/milestone/ENTRY.md`
- Create: `docs/superpowers/memory/debug/MEMORY.md`
- Create: `docs/superpowers/memory/debug/INDEX.md`
- Create: `docs/superpowers/memory/debug/ENTRY.md`
- Create: `docs/superpowers/memory/refactor/MEMORY.md`
- Create: `docs/superpowers/memory/refactor/INDEX.md`
- Create: `docs/superpowers/memory/refactor/ENTRY.md`

- [ ] Define one memory type per existing category
- [ ] Convert the old category guidance into record-facing metadata
- [ ] Preserve the existing entry schema as the repository entry template

### Task 2: Move Historical Entries

**Files:**
- Modify: `docs/superpowers/memory/*/entries/2026-03/*.md`
- Delete: `docs/superpowers/memory/**`

- [ ] Move all historical entry files under the new memory root
- [ ] Keep per-type numbering and file contents consistent after the move
- [ ] Remove the old progress tree completely

### Task 3: Rewrite Repository References

**Files:**
- Modify: `docs/superpowers/plans/*.md`
- Modify: `docs/superpowers/specs/*.md`

- [ ] Replace `docs/superpowers/memory/` references with `docs/superpowers/memory/`
- [ ] Replace `docs/superpowers/memory/` references with `docs/superpowers/memory/`
- [ ] Remove wording that implies progress is still the canonical durable-record location

### Task 4: Verify the Migration

**Files:**
- Verify only

- [ ] Confirm `docs/superpowers/memory/` no longer exists
- [ ] Confirm old `docs/superpowers/memory/` references no longer exist in repository docs
- [ ] Confirm `docs/superpowers/memory/` contains metadata, index, template, and entries for all three types
