---
name: project-extension-requesting-code-review
description: Repository-local extension of superpowers:requesting-code-review; use only after the upstream requesting-code-review workflow applies and repository-specific completion gates or memory checks are needed.
---

# Project Extension Requesting Code Review

## 概览

这是对 superpowers `requesting-code-review` 的仓库本地扩展。
review 以满足任务、保持最小改动、对完赛目标有正贡献作为通过条件。
主 Skill 只做收口路由：先判断当前改动是否值得保留，再按主题查看具体门禁。

## 何时使用

- 完成一个功能或修复后
- 准备结束当前改动前
- 需要判断当前实现是否值得继续保留时

## 最高优先级问题

- 当前功能能否满足要求？
- 当前实现是否满足最小改动？
- 当前改动是否对完成赛题有正贡献？

以上任一问题不能明确回答“是”，默认不得通过。

## 路由规则

- 收口评审门禁 -> `references/review-gates.md`
- AI 内存自检 -> `references/ai-memory-review.md`

## 默认执行方式

- AI 默认先核对 `docs/developer/strategy.md` 与当前任务上下文，判断是否满足要求、保持最小改动并对完赛有正贡献
- AI 默认执行内存量化检查，不把 memory 评估转交给用户人工处理
- 具体收口门禁、设备路径交付要求和板端结果留证要求只写在引用页

## 总则

- review 不把功能面扩大作为默认加分项
- review 不把抽象层增加作为默认加分项
- 如果有更小、更省内存、更直接的实现，应优先推荐它

## 边界

- 主入口不承载实现细节、开发过程要求或设备路径细则
- 具体门禁固定写在 `references/review-gates.md`
- 内存自检固定写在 `references/ai-memory-review.md`
