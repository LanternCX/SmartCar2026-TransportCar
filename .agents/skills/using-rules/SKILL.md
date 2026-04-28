---
name: using-rules
description: Use when implementing or refactoring code in this repository and needing to check project rules, constraints, or domain knowledge.
---

# Using Rules

## Overview

这是当前仓库规则与知识的统一入口。
本 Skill 只承接实现前与实现中的规则查询, 把执行规则压缩为 5 组固定入口。
其中正式串口通信协议正文统一维护在 `docs/developer/protocol.md`, 主入口继续通过硬件与协议页做路由。

## When to Use

- 开始实现或重构仓库代码前
- 不确定当前改动需要遵守哪些项目规则时
- 触及硬件、视觉、控制、内存或协议语义时

## Routing Rules

- 项目方向、任务优先级、控制主线与视觉口径 -> `references/developer-docs.md`
- 实现阶段通用约束、目录边界、TDD、内存装配门禁 -> `references/implementation-rules.md`
- 注释风格、文档字符串规范与注释示例 -> `references/comment-rules.md`
- 硬件事实、串口链路、视觉协议、坐标与联调语义 -> `references/hardware-and-protocol.md`（正式协议正文继续路由到 `docs/developer/protocol.md`）
- 比赛目标、双车协同、控制层级、调参与诊断顺序 -> `references/strategy-and-control.md`
- `docs/superpowers/specs/` 与 `docs/superpowers/plans/` 的归档、搬运与目录整理 -> `references/superpowers-doc-archive.md`

## First Check

- 若任务涉及项目方向、阶段目标、控制主线或视觉主线, 先查看 `references/developer-docs.md`
- 其中默认优先阅读 `docs/developer/strategy.md` 与 `docs/developer/tasks.md`

## Mandatory Gates

- 任何未在仓库正文明确给出的硬件事实, 必须先问用户, 禁止猜测
- 若改动触及 `TransportCar`、运行时 owner 或装配阶段, 必须先看实现阶段内存门禁与资产分类
- 若改动不能对完赛做出正贡献, 默认不应继续扩大实现

## Boundary

- `using-rules` 只用于写代码前和写代码过程中查询规则, 包含实现前置检查、设备路径判断与联调约束
- 最终收口评审改用 `project-extension-requesting-code-review`
