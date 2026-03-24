---
name: project-extension-writing-skills
description: Use when creating new skills, editing existing skills, or verifying skills work before deployment
---

# Project Extension Writing Skills

## Overview

这是对 superpowers `writing-skills` 的仓库本地扩展。
在当前仓库写 Skill 时, 先遵循 superpowers 通用方法, 再遵循这里的 Agent 私有方法论。
这里承接 Skill 编写与迁移规范, 不再把相关正文暴露为用户主 review 正文。

## When to Use

- 新建仓库本地 Skill
- 重构已有 Skill 结构
- 为 Skill 设计 `references/`、`assets/` 和引用页布局

## Local Rules

- 扩展 superpowers 的本地 Skill 使用 `project-extension-` 前缀
- 主 `SKILL.md` 默认只做路由与边界说明, 详细方法论保留在 Skill 私有 `references/`
- Skill 编写方法论由 Agent 自行使用, 不再作为用户主 review 正文
- references 数量优先压缩到最少, 以最短决策路径降低选择成本
- 当前仓库优先使用 Harness 的 `Tool Wrapper` 与 `Reviewer` 结构, 必要时再组合其他模式

## References

- 编写规则与模式选择 -> `references/writing-rules.md`
- 迁移检查清单 -> `references/migration-checklist.md`
