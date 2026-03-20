---
title: 远端题面抓取与 Markdown 落库设计
date: 2026-03-06
status: approved
scope: docs-and-skill
---

# 背景

蚂蚁搬家组题面来自远端网页（总则、细则、Q&A），直接网页阅读包含大量站点噪声，不利于 Agent 稳定检索与规则引用。

# 目标

1. 将远端题面转换为仓库内 Markdown。
2. 保留正文图片链接与关键图注。
3. 提供可追溯来源与可引用的 REQ 编号。
4. 沉淀为可复用技能，便于后续批量执行。

# 设计决策

## 1) 文档产物

- `docs/problem_statement/spec.md`：总则摘录 + 蚂蚁搬家细则 + REQ。
- `docs/problem_statement/qa.md`：问答澄清（按月份）。
- `docs/problem_statement/sources.md`：来源链接与清洗边界。
- `docs/problem_statement/README.md`：使用说明。

## 2) 清洗策略

- 保留正文章节、规则条款、数值约束、图片与图注。
- 删除评论、推荐、打赏、侧栏、广告等页面壳层信息。
- 过滤 UI 图标，优先保留正文图链接。

## 3) 引用策略

- 通用规则编号：`REQ-GEN-*`。
- 细则规则编号：`REQ-ANT-*`。
- 问答澄清编号：`REQ-QA-*`。

## 4) 技能沉淀

新增 `.agents/skills/remote-spec-to-markdown/SKILL.md`，定义输入、输出、清洗规则和验收清单。

# 非目标

- 不做离线图片下载与本地化。
- 不自动解析所有外链文档（仅处理本次指定 3 个 URL）。

# 验收标准

- 题面文档可在仓库内直接读取。
- 关键规则可通过 REQ 编号引用。
- 来源与清洗策略可追溯。
- 无明显页面噪声残留。
