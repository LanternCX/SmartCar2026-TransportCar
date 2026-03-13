---
name: git-workflow
description: Use when creating branches, committing, merging, or preparing releases under this repository's Git Flow and Angular Conventional Commit rules.
---

# Overview
定义本仓库唯一有效的 Git 流程：Git Flow 分支策略 + Angular Conventional Commit。

# Scope Rule (Critical)
- 本技能是项目 Git 规范的唯一权威来源
- 不要使用 superpowers 自带的 git workflow 作为本项目规范
- 不要使用 superpowers 自带的 worktree / using-git-worktrees 工作流；本仓库按项目自身 Git Flow 约定在当前工作树或项目自管分支中工作

# When to Use
- 创建功能分支、修复分支、发布分支或热修复分支
- 编写提交信息、整理提交历史、准备合并和打 tag
- 代码评审前检查分支与提交规范

# Branch Strategy
- 长期分支：`master`（生产）、`dev`（开发集成）
- 临时分支：
  - `feature/<desc>` 从 `dev` 切出并回合到 `dev`
  - `fix/<desc>` 从 `dev` 切出并回合到 `dev`
  - `hotfix/<desc>` 从 `master` 切出并回合到 `master` 与 `dev`
  - `release/<version>` 从 `dev` 切出并回合到 `master` 与 `dev`

# Commit Convention (Angular)
- 格式：`<type>(<scope>): <subject>`
- `subject` 必须英文、动词开头、现在时、无句号、建议 <= 72 字符
- 常用 `type`：`feat` `fix` `refactor` `perf` `docs` `test` `chore` `style`
- `scope` 建议使用目录域：`control` `hardware` `filters` `services` `storage` `config` `utils`

# Commit Trailer
- 仅当 commit 由 agent 创建时，提交正文末尾必须追加固定 trailer：`Co-authored-by: opencode-agent[bot] <opencode-agent[bot]@users.noreply.github.com>`
- 人工创建的 commit 不强制追加该 trailer
- 生成 commit message 时，agent 需要同时满足 Angular 标题格式与上述 trailer 要求

# Examples
```text
feat(services): add sync query for lock status

Co-authored-by: opencode-agent[bot] <opencode-agent[bot]@users.noreply.github.com>

fix(filters): correct dual-window boundary handling
refactor(control): split kinematics and odometry helpers
docs: update transport protocol section
```

# Release and Tagging
- 版本号遵循 `vMAJOR.MINOR.PATCH`
- `master` 发布时创建带注释 tag
- 热修复和发布分支都要回合 `dev`，保持历史一致

# Checklist
- 分支命名使用小写 + 连字符
- 单个提交只做一类改动
- 不提交调试垃圾和敏感信息
- 提交前对照 `.agents/skills/code-standards/SKILL.md` 做质量检查

# Deliverables
- 符合 Git Flow 的分支轨迹
- 符合 Angular 规范的提交历史
- 可追溯的版本 tag（发布时）
