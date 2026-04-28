---
name: using-git-worktrees
description: Use when work on this repository would otherwise trigger the superpowers using-git-worktrees flow, especially when starting feature work, asking for isolation, or preparing branch changes without a separate worktree.
---

# Skill: using-git-worktrees

## Overview

本仓库的隔离开发、分支准备和提交前流程统一路由到项目本地 `git-workflow`。
本 Skill 只处理 worktree 触发场景的重定向，不定义额外 Git 规范。

## Redirect Rule

- 不创建新的 git worktree
- 不切到仓库外的隔离目录
- 立即改用 `.agents/skills/git-workflow/SKILL.md`
- 分支、提交、合并、发布规则全部以 `git-workflow` 为准
- 用户明确要求在当前分支工作时，保持当前分支，不额外创建 feature/fix worktree

## Quick Reference

- 用户说“新开任务 / 隔离开发” -> 留在当前工作树，按 `git-workflow` 判断是否需要分支
- 用户说“直接在当前分支改” -> 遵循当前分支要求，再按 `git-workflow` 处理其余 Git 约束
- 需要分支规范、提交信息、合并或发布规则 -> 转到 `git-workflow`

## Common Mistakes

- 命中 `using-git-worktrees` 后创建 worktree
- 把 worktree 隔离当成强制前置步骤
- 用户已指定当前分支工作时仍额外创建 `feature/*` worktree
