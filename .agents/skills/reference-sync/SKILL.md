---
name: reference-sync
description: Use when repository reference documents need to be imported, refreshed, cleaned, or traced back to external sources.
---

# 参考同步

## Overview

这是当前仓库参考文档的维护入口。
它负责更新 `docs/` 下的唯一正文事实源, 然后由各 Skill 的 `references/` 引用页继续复用这些正文。

## When to Use

- 远端规则网页需要导入仓库时
- GitHub、官方文档或外部资料发生变化时
- 需要补来源追溯、清洗策略或更新记录时

## Routing Rules

- 想确认同步步骤、清洗流程与维护边界 -> `references/sync-rules.md`
- 想确认来源记录、追溯要求与质量检查 -> `references/source-and-quality.md`
- 模板资产 -> `assets/import-template.md`, `assets/source-record-template.md`

## Repository Rule

- 原 `remote-spec-to-markdown` 的远端规则抓取与清洗职责已并入这里
- 文档正文只维护在 `docs/`, 不在 Skill 目录复制第二份
