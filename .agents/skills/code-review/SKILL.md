---
name: code-review
description: Repository-local code review gates; use only when the user explicitly asks for review, code review, audit, or an equivalent review action.
---

# Code Review

## 概览

这是仓库本地收口评审入口。
评审以满足任务、保持最小改动、对完赛目标有正贡献作为通过条件。

## 何时使用

- 用户主动要求 review、code review、audit 或等价审核动作时
- 用户要求用 subagent 复核当前改动时

## 边界

- 完成功能、修复或提交前不默认触发 review
- 用户只要求实现、修改、提交或说明时, 不主动追加 review 流程
- subagent 不承担开发实现任务, 只承担审核、复核和独立检查

## 核心问题

- 当前功能能否满足要求？
- 当前实现是否满足最小改动？
- 当前改动是否对完成赛题有正贡献？

以上任一问题不能明确回答“是”，默认不得通过。

## 路由规则

- 收口评审门禁 -> `references/review-gates.md`
- AI 内存自检 -> `references/ai-memory-review.md`

## 总则

- review 不把功能面扩大作为默认加分项
- review 不把抽象层增加作为默认加分项
- 如果有更小、更省内存、更直接的实现，应优先推荐它
