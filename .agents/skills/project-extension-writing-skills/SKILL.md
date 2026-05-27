---
name: project-extension-writing-skills
description: Repository-local extension of superpowers:writing-skills; use only after the upstream writing-skills workflow applies and repository-specific skill structure, routing, or cleanup rules are needed.
---

# Project Extension Writing Skills

## Overview

这是对 superpowers `writing-skills` 的仓库本地扩展。
本 Skill 负责 Skill 编写、结构调整与清理检查；主入口只保留用途、边界和路由。

## When to Use

- 新建仓库本地 Skill
- 重构已有 Skill 结构
- 为 Skill 设计 `references/`、`assets/` 和引用页布局
- 清理重复、过时或历史性 Skill 表述

## Local Rules

- 扩展 superpowers 的本地 Skill 使用 `project-extension-` 前缀
- 主 `SKILL.md` 默认只做路由与边界说明，详细方法论保留在 Skill 私有 `references/`
- 规则按渐进式路径引入：主入口短、reference 少、触发条件清晰
- references 数量优先压缩到最少，场景没有明确差异时合并
- 文档只描述当前事实，不写迁移解释、版本对比或历史变更说明
- 本仓库优先使用 Harness 的 `Tool Wrapper` 与 `Reviewer` 结构，必要时再组合其他模式

## References

- 编写规则与模式选择 -> `references/writing-rules.md`
- 结构清理检查 -> `references/restructuring-checklist.md`
