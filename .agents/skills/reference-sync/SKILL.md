---
name: reference-sync
description: Use when repository reference links, source records, or docs/superpowers spec-plan archives need to be checked or updated.
---

# 参考同步

## 概览

这是仓库参考入口和协作文档归档规则的维护入口。
它只登记来源链接、正式落点和维护动作，不导入或清洗外部正文。

## 适用场景

- 外部资料链接、来源记录或正式落点需要更新时
- 需要核对某份正式正文的来源登记与维护清单时
- `docs/superpowers/specs/` 或 `docs/superpowers/plans/` 需要归档整理时

## 路由规则

- 来源、正式落点与同步触发条件 -> `references/source-registry.md`
- 持续维护对象、检查项与质量复核 -> `references/maintenance-checklist.md`
- `docs/superpowers/specs/` 与 `docs/superpowers/plans/` 归档整理 -> `references/superpowers-doc-archive.md`
- 模板资产 -> `assets/source-record-template.md`

## 仓库规则

- `reference-sync` 只维护来源登记与维护清单，不复制或承接外部正文
- 更新正式正文时，必须同步检查 `references/source-registry.md` 与 `references/maintenance-checklist.md`
- 外部资料可能变化时，先核对来源，再修改本地链接入口或路由页
