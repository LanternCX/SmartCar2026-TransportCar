# Remote Spec To Markdown Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将第21届智能车竞赛（蚂蚁搬家组）远端网页题面转为仓库内可检索 Markdown，并沉淀为可复用技能。

**Architecture:** 采用“抓取 -> 清洗 -> 结构化 -> REQ 编号 -> 追溯记录”的文档流水线。输出 `spec.md`、`qa.md`、`sources.md`、`README.md`，并新增 skill 作为流程模板。

**Tech Stack:** OpenCode `webfetch/read/apply_patch/task`，Markdown。

---

### Task 1: 采集与正文提取

**Files:**
- Create: `docs/problem_statement/sources.md`

**Step 1: Write the failing test**

先抓取网页并检查是否包含明显页面噪声。

**Step 2: Run test to verify it fails**

Run: 目视检查抓取结果。
Expected: 原始内容混有评论/推荐/打赏等噪声。

**Step 3: Write minimal implementation**

记录来源 URL，定义清洗边界与追溯字段。

**Step 4: Run test to verify it passes**

Run: 检查 `sources.md`。
Expected: 三个来源 URL 与清洗策略已记录。

### Task 2: 生成主规则文档

**Files:**
- Create: `docs/problem_statement/spec.md`

**Step 1: Write the failing test**

先定义 REQ 索引结构，再填充正文。

**Step 2: Run test to verify it fails**

Run: 检查 `spec.md` 是否存在并包含 `REQ-`。
Expected: 初始不存在或缺失 REQ。

**Step 3: Write minimal implementation**

写入总则摘录、蚂蚁搬家细则、图片链接和 `REQ-GEN/REQ-ANT/REQ-QA`。

**Step 4: Run test to verify it passes**

Run: 检查 `spec.md`。
Expected: 章节结构完整，`REQ-*` 可引用。

### Task 3: 生成问答文档

**Files:**
- Create: `docs/problem_statement/qa.md`

**Step 1: Write the failing test**

先按月份建立空结构。

**Step 2: Run test to verify it fails**

Run: 检查 `qa.md`。
Expected: 问答条目为空或结构不完整。

**Step 3: Write minimal implementation**

填充 2 月与 3 月关键问答，保留规则边界澄清。

**Step 4: Run test to verify it passes**

Run: 检查 `qa.md`。
Expected: 按月份分组，条目可检索。

### Task 4: 新增技能文档

**Files:**
- Create: `.agents/skills/remote-spec-to-markdown/SKILL.md`

**Step 1: Write the failing test**

检查技能目录中不存在该技能。

**Step 2: Run test to verify it fails**

Run: 目录检查。
Expected: `remote-spec-to-markdown` 不存在。

**Step 3: Write minimal implementation**

新增技能，包含输入、输出、清洗规则、验证清单。

**Step 4: Run test to verify it passes**

Run: 打开技能文件检查 frontmatter。
Expected: 包含 `name` 与 `description` 且描述触发条件明确。

### Task 5: 最终核验

**Files:**
- Verify only

**Step 1: 文档存在性检查**

Run: 列出 `docs/problem_statement/`。
Expected: `spec.md`、`qa.md`、`sources.md`、`README.md` 均存在。

**Step 2: 可引用性检查**

Run: 搜索 `REQ-`。
Expected: `spec.md` 含多条 REQ 编号。

**Step 3: 噪声检查**

Run: 搜索 `打赏`、`上一篇`、`热门文章` 等关键词。
Expected: 主文档无明显页面壳层噪声。
