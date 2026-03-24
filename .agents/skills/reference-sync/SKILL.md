---
name: reference-sync
description: Use when repository reference documents need to be imported, refreshed, cleaned, or traced back to external sources.
---

# 参考同步

## 概览

这是当前仓库参考文档的维护入口。
它不维护各 Skill 的正式正文，而是负责登记来源、正式落点和后续维护动作。

## 适用场景

- 远端规则网页需要导入仓库时
- GitHub、官方文档或外部资料发生变化时
- 需要补来源追溯、清洗策略或更新记录时
- 需要核对某份正式正文的来源登记与维护清单时

## 路由规则

- 想确认同步步骤、清洗流程与维护边界 -> `references/sync-rules.md`
- 想确认来源记录、追溯要求与质量检查 -> `references/source-and-quality.md`
- 想查看文档来源、正式落点与触发条件 -> `references/source-registry.md`
- 想查看持续维护对象与检查项 -> `references/maintenance-checklist.md`
- 模板资产 -> `assets/import-template.md`, `assets/source-record-template.md`

## 仓库规则

- 原 `remote-spec-to-markdown` 的远端规则抓取与清洗职责已并入这里
- `reference-sync` 只维护来源登记与维护清单, 不复制或承接各 Skill 的正式正文
- 更新正式正文时, 必须同步检查 `references/source-registry.md` 与 `references/maintenance-checklist.md`
