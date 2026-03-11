---
name: using-git-worktrees
description: Use when work on this repository would otherwise trigger the superpowers using-git-worktrees flow, especially when starting feature work, asking for isolation, or preparing branch changes without wanting a separate worktree.
---

# Skill: using-git-worktrees

## Overview

本仓库不使用 superpowers 默认的 git worktree 工作流。
当任务命中 `using-git-worktrees` 时，立即重定向到项目本地 `git-workflow`，并在当前工作树内继续。

## Redirect Rule

- 不创建新的 git worktree
- 不切到仓库外的隔离目录
- 立即改用 `.agents/skills/git-workflow/SKILL.md`
- 分支、提交、合并、发布规则全部以 `git-workflow` 为准
- 如果用户明确要求“直接在当前分支提交”，则保持当前分支工作，不额外创建 feature/fix worktree

## Quick Reference

- 用户说“新开任务/隔离开发” -> 先看是否只是想避免污染当前目录；本仓库仍留在当前工作树
- 用户说“直接在当前分支改” -> 直接遵循该要求，不创建 worktree
- 需要分支规范 -> 转到 `git-workflow`
- 需要提交信息 -> 转到 `git-workflow`

## Common Mistakes

- 看到 `using-git-worktrees` 就按 superpowers 默认流程建 worktree：错误，本仓库禁止这条路径
- 把 worktree 隔离当成强制前置步骤：错误，本仓库 Git 规范不要求它
- 用户已指定当前分支提交，仍额外创建 `feature/*` worktree：错误，先满足用户的当前分支要求，再按 `git-workflow` 处理其余 Git 约束
