# TDD with Device Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为当前仓库创建一个 `tdd-with-device` 流程 skill，把主机测试、设备安全 smoke、设备实时观测和 HIL 留证串成统一的设备化 TDD 工作流。

**Architecture:** 采用新增聚合 skill 的方式，不重写已有 `tdd-integration`、`mpy-cli`、`hardware-integration`，而是在新 skill 中定义 stage 1 / 2 / 3 的门禁、回退规则和交付物，并通过 baseline / post-skill 场景测试验证它是否真正改变 agent 行为。

**Tech Stack:** Markdown skill docs, docs/plans, repo-local `.agents/skills`, subagent scenario testing

---

### Task 1: 记录 baseline 行为

**Files:**
- Create: `docs/plans/2026-03-07-tdd-with-device-design.md`
- Create: `docs/plans/2026-03-07-tdd-with-device-implementation-plan.md`

**Step 1: 运行 baseline 场景测试**

- 用子代理在“没有 `tdd-with-device` skill”的假设下回答硬件耦合改动的完整流程。

**Step 2: 记录 baseline 结论**

- 明确写出 agent 会做什么、不会稳定做什么，尤其是 `stage2` 缺口。

**Step 3: Commit**

```bash
git add docs/plans/2026-03-07-tdd-with-device-design.md docs/plans/2026-03-07-tdd-with-device-implementation-plan.md
git commit -m "docs: add tdd with device design"
```

### Task 2: 先写 skill 触发验证（RED）

**Files:**
- Create: `.agents/skills/tdd-with-device/SKILL.md`

**Step 1: 写出失败标准**

- 列出没有该 skill 时 agent 典型遗漏：跳过 `stage2`、没有失败回退规则、没有通过标准。

**Step 2: 用这些失败标准约束 skill 内容**

- 确保 skill 不是泛泛谈 TDD，而是针对这些缺口。

**Step 3: Commit**

```bash
git add .agents/skills/tdd-with-device/SKILL.md
git commit -m "feat: add tdd with device workflow skill"
```

### Task 3: 更新 skill 索引与仓库入口

**Files:**
- Modify: `AGENTS.md`

**Step 1: 在 skill 索引中加入新 skill**

- 说明其定位：将 `stage1 host tests -> stage2 device smoke -> stage3 device observe -> HIL evidence` 串成统一工作流。

**Step 2: 补充新功能开发顺序或问题诊断入口中的引用**

- 让后续 agent 更容易从仓库说明里发现该 skill。

**Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs: index tdd with device skill"
```

### Task 4: 做 post-skill 场景验证（GREEN）

**Files:**
- Modify: `docs/plans/2026-03-07-tdd-with-device-design.md`

**Step 1: 再跑一次同类场景测试**

- 让子代理在新 skill 存在的情况下回答同类问题。

**Step 2: 验证 skill 是否被触发且流程变完整**

- 检查是否明确包含 `stage1 -> stage2 -> stage3` 和失败回退规则。

**Step 3: 记录结果并 Commit**

```bash
git add docs/plans/2026-03-07-tdd-with-device-design.md
git commit -m "test: verify tdd with device skill behavior"
```

### Task 5: 最终验证与整理（REFACTOR）

**Files:**
- Modify: `.agents/skills/tdd-with-device/SKILL.md` (if wording refinement needed)

**Step 1: 自检 frontmatter 与关键词覆盖**

- `name` 只用字母/数字/连字符
- `description` 只描述何时使用，不描述 workflow 细节

**Step 2: 检查内容结构是否清晰**

- 必须覆盖：Overview、When to Use、Three-Stage Flow、Gate Rules、Failure Classification、Deliverables、Red Flags

**Step 3: Commit**

```bash
git add .agents/skills/tdd-with-device/SKILL.md
git commit -m "refactor: tighten tdd with device skill wording"
```
