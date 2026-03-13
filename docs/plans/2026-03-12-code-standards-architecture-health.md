# code-standards 架构健康规范升级 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将架构健康, 反深耦合, 反过度设计和状态单一所有权规则纳入 `code-standards` skill, 让 future agent 在编码和 review 时更稳定地守住仓库长期可维护性。

**Architecture:** 先用基线压力场景记录当前 skill 的约束缺口, 再以最小增量更新 `SKILL.md` 与 `README.md`, 最后用同一组场景复测升级后的规则是否足够明确。文案保持短规则 + checklist 形式, 避免把 skill 写成冗长教程。

**Tech Stack:** Markdown, repo-local skill docs, subagent pressure scenarios, architecture review heuristics.

---

### Task 1: 记录当前 skill 的基线压力场景

**Files:**
- Modify: `docs/plans/2026-03-12-code-standards-architecture-health-design.md`

**Step 1: Write the failing test**

将以下 4 个场景写入设计文档, 作为当前 skill 的失败基线：

- God object 继续膨胀但分层表面正确
- command handler 直接改宿主私有字段
- 为未来扩展过早引入事件总线或通用框架
- import-time 自动注册且静默吞错

**Step 2: Run test to verify it fails**

Validation: 使用同一组压力场景审视当前 `.agents/skills/code-standards/SKILL.md`, 预期结果是当前规则无法对以上问题给出足够硬的 review 约束。

**Step 3: Write minimal implementation**

把基线缺口, 失败原因和“为什么 review 会放过问题”补进设计文档。

**Step 4: Verify baseline is documented**

Expected: 设计文档中明确记录 4 个失败场景和当前规则缺口。

**Step 5: Commit**

```bash
git add docs/plans/2026-03-12-code-standards-architecture-health-design.md
git commit -m "docs(skill): record code-standards architecture review gaps"
```

### Task 2: 升级 `SKILL.md` 的架构健康规则

**Files:**
- Modify: `.agents/skills/code-standards/SKILL.md`

**Step 1: Write the failing test**

先列出当前 `SKILL.md` 缺失的硬规则：

```text
- 状态单一所有权
- 禁止私有字段协议
- 反过度设计
- 副作用注册必须可观测
- review 输出必须指出架构健康问题
```

**Step 2: Run test to verify it fails**

Validation: 对照当前 `SKILL.md`, 预期上述规则不存在或表达不够明确。

**Step 3: Write minimal implementation**

在 `SKILL.md` 中新增：

- 架构健康原则
- 反深耦合规则
- 反过度设计规则
- 更具体的 review checklist
- 更明确的 review 输出要求

**Step 4: Run test to verify it passes**

Validation: 用相同 4 个压力场景复测, 预期升级后的 `SKILL.md` 能明确指出问题, 不再只停留在“目录没错”。

**Step 5: Commit**

```bash
git add .agents/skills/code-standards/SKILL.md
git commit -m "docs(skill): strengthen architecture health rules"
```

### Task 3: 同步 `README.md` 并保持执行入口一致

**Files:**
- Modify: `.agents/skills/code-standards/README.md`

**Step 1: Write the failing test**

检查 `README.md` 中是否仍缺少以下内容：

- 不过度设计
- 避免深耦合
- 显式边界和状态单一所有权
- review 时必须指出架构健康问题

**Step 2: Run test to verify it fails**

Validation: 当前 `README.md` 预期仍偏向一般风格规则, 对上述架构健康约束不够明确。

**Step 3: Write minimal implementation**

同步更新 `README.md`, 但保持内容精炼, 与 `SKILL.md` 的核心规范一致。

**Step 4: Run test to verify it passes**

Validation: `README.md` 与 `SKILL.md` 的架构健康原则一致, 不出现互相冲突的旧规则。

**Step 5: Commit**

```bash
git add .agents/skills/code-standards/README.md
git commit -m "docs(skill): sync code-standards readme with architecture rules"
```

### Task 4: 最终复测与结果说明

**Files:**
- Verify only

**Step 1: Re-run pressure scenarios**

Validation: 对升级后的 skill 重新跑 4 个架构压力场景。

Expected: future agent 能明确指出 God object, 私有字段协议, 过度抽象和静默吞错问题。

**Step 2: Inspect word choice and searchability**

Validation: 检查 frontmatter `description` 是否仍只描述触发条件, 不偷写流程摘要。

Expected: 关键词覆盖 architecture boundaries, maintainability, overdesign, coupling, review 等触发语义。

**Step 3: Report evidence**

总结：基线缺口, 规则升级点, 复测结论和后续维护建议。
