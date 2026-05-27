---
name: git-workflow
description: Use when creating branches, committing, merging, or preparing releases under this repository's Git Flow and Angular Conventional Commit rules.
---

# Overview

定义本仓库 Git 流程：Git Flow 分支策略 + Angular Conventional Commit。

# Scope Rule

- 本技能是项目 Git 规范的权威来源
- 本技能只处理分支、提交、合并与发布规则

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

- 默认不追加任何 `Co-authored-by` 尾注
- 只有用户明确要求时，才允许追加 `Co-authored-by`
- 若允许追加，co-author 必须是真人，不得使用 agent、bot 或系统账号
- 生成提交信息时，优先保持纯净的 Angular 标题，不要自行补尾注

# Examples

```text
feat(services): add sync query for lock status
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
- 提交前先查 `.agents/skills/using-rules/SKILL.md`，收口前再用 `.agents/skills/project-extension-requesting-code-review/SKILL.md` 自检

# Deliverables

- 符合 Git Flow 的分支轨迹
- 符合 Angular 规范的提交历史
- 可追溯的版本 tag（发布时）
