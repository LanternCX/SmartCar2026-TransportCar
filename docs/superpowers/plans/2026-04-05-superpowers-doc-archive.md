# Superpowers 文档按 PR 归档 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `docs/superpowers/specs/` 与 `docs/superpowers/plans/` 建立“根目录保留当前文档, 已收口文档进入 `archive/PR#<id>/`”的归档结构, 降低当前工作区噪音并保留按 PR 回看历史的能力。

**Architecture:** 不重做整套知识库, 只在 `specs/` 与 `plans/` 下各增加一层 `archive/PR#<id>/`。执行时先建目录和划分规则, 再挑选归属明确的一批历史文档做首轮迁移, 最后复查根目录是否只剩当前仍在推进的文档。

**Tech Stack:** Markdown, 仓库现有 `docs/superpowers/` 文档结构, `rg`, `git diff`。

---

### Task 1: 建立归档目录骨架与执行边界

**Files:**
- Create: `docs/superpowers/specs/archive/`
- Create: `docs/superpowers/plans/archive/`
- Modify: `docs/superpowers/specs/2026-04-05-superpowers-doc-archive-design.md`
- Modify: `docs/superpowers/plans/2026-04-05-superpowers-doc-archive.md`

- [ ] Step 1: 对照设计文档, 确认本轮只做 `specs/` 与 `plans/` 两个根目录的归档整理, 不额外引入 `now/active/current` 等工作区目录
- [ ] Step 2: 检查当前仓库是否已经存在同名归档层或冲突命名, 若有冲突先收口命名规则再继续迁移
- [ ] Step 3: 建立 `docs/superpowers/specs/archive/` 与 `docs/superpowers/plans/archive/` 目录骨架
- [ ] Step 4: 为后续执行明确最小边界: 根目录表示当前工作区, `archive/PR#<id>/` 表示已收口批次

### Task 2: 盘点当前文档并划分迁移批次

**Files:**
- Verify: `docs/superpowers/specs/*.md`
- Verify: `docs/superpowers/plans/*.md`
- Create: `docs/superpowers/plans/2026-04-05-superpowers-doc-archive-inventory.md`

- [ ] Step 1: 盘点 `specs/` 与 `plans/` 根目录现有文档, 按“当前保留 / 可归档 / 待判断”三类整理清单
- [ ] Step 2: 为“可归档”文档补充对应 PR 编号, 保证每份文档都有明确落点
- [ ] Step 3: 对跨多个 PR 但仍在演进的主题标记为“当前保留”或“待判断”, 不为追求整齐强行拆分
- [ ] Step 4: 对 PR 归属不清的文档一律保留在根目录并标记为“待判断”, 禁止为了推进速度猜测落点
- [ ] Step 5: 将清单写入 `2026-04-05-superpowers-doc-archive-inventory.md`, 作为首轮迁移的执行依据

### Task 3: 完成首批已收口文档迁移

**Files:**
- Modify: `docs/superpowers/specs/archive/PR#<id>/...`
- Modify: `docs/superpowers/plans/archive/PR#<id>/...`
- Modify: `docs/superpowers/specs/*.md`
- Modify: `docs/superpowers/plans/*.md`

- [ ] Step 1: 先只迁移归属明确、收口明确、不会影响当前使用的一批文档
- [ ] Step 2: 在 `specs/archive/PR#<id>/` 与 `plans/archive/PR#<id>/` 下分别放置对应批次文档, 保持两类目录边界对称
- [ ] Step 3: 每迁移一批后复查根目录, 确认当前仍在推进的文档没有被误收进历史目录
- [ ] Step 4: 若发现某份文档一旦迁移就会影响当前 review 或继续追加, 立即撤回到“待判断”而不是硬迁移
- [ ] Step 5: 对跨多个 PR 但最终归到最后收口 PR 的文档, 在执行记录里注明原因, 避免后续误以为早期 PR 缺文档是遗漏

### Task 4: 修正必要引用并复查目录可用性

**Files:**
- Modify: `docs/superpowers/**/*.md`
- Verify: `docs/superpowers/specs/`
- Verify: `docs/superpowers/plans/`

- [ ] Step 1: 搜索文档内对已迁移文件的直接路径引用, 找出因搬运导致失效或易误导的引用
- [ ] Step 2: 只修正必要且明确的引用, 不借机重写无关历史文档
- [ ] Step 3: 复查 `specs/` 与 `plans/` 根目录, 确认它们现在只表达“当前工作区”而不是“历史堆积区”
- [ ] Step 4: 抽样从一个当前文档和一个已归档 PR 文档分别回看, 确认查找路径符合预期

### Task 5: 收口规则并准备后续维护

**Files:**
- Modify: `docs/superpowers/specs/2026-04-05-superpowers-doc-archive-design.md`
- Modify: `docs/superpowers/plans/2026-04-05-superpowers-doc-archive.md`
- Modify: `docs/superpowers/plans/2026-04-05-superpowers-doc-archive-inventory.md`

- [ ] Step 1: 根据首轮迁移结果, 确认“什么留根目录、什么进 `archive/PR#<id>/`、什么继续待判断”三条规则是否足够稳定
- [ ] Step 2: 若发现规则仍有歧义, 只补最小必要说明, 不扩张为新的多层分类体系
- [ ] Step 3: 记录仍不适合立即归档的主题与原因, 作为后续单独处理的输入
- [ ] Step 4: 最后复核本轮是否真正实现了“当前区更干净, 历史区可回看”这个目标, 再进入人工 review
