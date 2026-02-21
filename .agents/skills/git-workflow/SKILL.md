---
name: git-workflow
description: Enforce Git Flow branching strategy and Angular commit message conventions for the SmartCar project.
---

# Purpose
规范 Git 分支管理和提交信息格式，通过 Git Flow 工作流和 Angular 提交规范确保版本历史清晰、可追溯，便于协作开发和版本发布。

# When to Use
- 创建新功能分支时
- 提交代码变更时
- 合并分支或发布版本时
- 代码审查前

---

# Branch Strategy (Git Flow)

## Persistent Branches
| 分支 | 说明 | 保护 |
|------|------|------|
| `master` | 生产就绪代码，每次合并都对应一个版本标签 | ✅ 受保护 |
| `dev` | 主开发分支，集成所有已完成的功能 | ✅ 受保护 |

## Temporary Branches
| 前缀 | 格式 | 用途 | 基于 | 合并到 |
|------|------|------|------|--------|
| `feature/` | `feature/<short-desc>` | 新功能开发 | `dev` | `dev` |
| `fix/` | `fix/<short-desc>` | Bug 修复 | `dev` | `dev` |
| `hotfix/` | `hotfix/<short-desc>` | 紧急生产修复 | `master` | `master` + `dev` |
| `release/` | `release/<version>` | 发布准备 | `dev` | `master` + `dev` |
| `chore/` | `chore/<short-desc>` | 工具、配置调整 | `dev` | `dev` |

## Branch Naming Rules
- 使用小写字母和连字符，不使用下划线
- 描述应简短有意义（2-4 个单词）
- 英文命名

**Examples:**
```bash
feature/position-mode        # ✅ 新增位置控制模式
feature/rear-wheel-only      # ✅ 后轮单轮模式
fix/encoder-spike-filter     # ✅ 修复编码器滤波
fix/yaw-drift-calibration    # ✅ 修复航向角漂移
hotfix/motor-driver-crash    # ✅ 紧急修复电机驱动崩溃
release/v2.1.0               # ✅ 发布版本
chore/update-stubs           # ✅ 更新类型提示桩
```

---

# Commit Message Convention (Angular Style)

## Format
```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

## Types
| Type | 说明 | 示例场景 |
|------|------|---------|
| `feat` | 新功能 | 添加位置控制模式、新增查询接口 |
| `fix` | Bug 修复 | 修复编码器溢出、修复航向角漂移 |
| `refactor` | 代码重构（不影响功能） | 提取辅助函数、重组模块结构 |
| `perf` | 性能优化 | 减少控制周期耗时、优化滤波计算 |
| `docs` | 文档更新 | 更新 README、添加注释 |
| `chore` | 构建/工具/配置变更 | 更新 stubs、修改 pyrightconfig |
| `test` | 测试相关 | 添加验证脚本、更新测试用例 |
| `style` | 代码风格（不影响逻辑） | 格式化、重命名变量 |
| `revert` | 回滚提交 | 撤销上一次提交 |

## Scopes（项目模块）
| Scope | 说明 |
|-------|------|
| `control` | `control/` 控制算法层 |
| `hardware` | `hardware/` 硬件驱动层 |
| `filters` | `filters/` 滤波算法层 |
| `services` | `services/` 业务逻辑层 |
| `storage` | `storage/` 持久化层 |
| `config` | `config/` 参数配置 |
| `utils` | `utils/` 工具函数 |
| `protocol` | 串口通信协议相关 |
| `pid` | PID 控制器相关 |
| `kinematics` | 运动学/里程计相关 |
| `imu` | IMU 姿态解算相关 |
| `deps` | 依赖/stubs 相关 |

> Scope 可以省略，仅在有明确模块归属时使用。

## Subject Rules
- **英文**，动词开头（现在时态），首字母小写
- 不加句号
- 不超过 72 个字符
- 简洁描述"做了什么"

**Good examples:**
```
feat(services): add position control mode with motion lock
fix(filters): correct spike filter window boundary overflow
refactor(control): extract PID math into separate module
perf(filters): replace list copy with circular buffer in dual-window filter
docs: update README with communication protocol details
chore(deps): update smartcar stubs to v2.3
```

**Bad examples:**
```
feat: 添加位置控制                    ❌ 不能使用中文
fix: Fixed the bug.                  ❌ 过去时态 + 句号
update encoder                       ❌ 缺少 type
feat: add new feature for position control mode to support both absolute and relative movement  ❌ 太长
```

## Body（可选）
- 解释"为什么"这样做，而不是"做了什么"（代码本身已经说明做了什么）
- 每行不超过 72 个字符
- 与 subject 之间空一行

## Footer（可选）
- 关联 issue：`Closes #123` 或 `Refs #456`
- 破坏性变更：`BREAKING CHANGE: <description>`

## Full Example
```
feat(services): add sync query interface for motion lock state

Add ?lock query command that returns current motion lock status.
This enables the caller to implement synchronous control by polling
before sending new relative-position commands, avoiding command
accumulation caused by repeated dispatch.

Closes #12
```

---

# Workflow Procedures

## 1. Start a New Feature
```bash
# 从 dev 切出功能分支
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name

# 开发...
git add <files>
git commit -m "feat(scope): add something useful"

# 完成后合并回 dev
git checkout dev
git pull origin dev
git merge --no-ff feature/your-feature-name
git push origin dev

# 删除本地功能分支
git branch -d feature/your-feature-name
```

> `--no-ff` 保留合并历史，避免 fast-forward 使分支结构消失。

## 2. Fix a Bug
```bash
git checkout dev
git pull origin dev
git checkout -b fix/short-description

# 修复...
git commit -m "fix(scope): resolve specific bug"

git checkout dev
git merge --no-ff fix/short-description
git push origin dev
git branch -d fix/short-description
```

## 3. Hotfix on Production
```bash
# 从 master 切出紧急修复分支
git checkout master
git pull origin master
git checkout -b hotfix/critical-issue

# 修复...
git commit -m "fix(scope): patch critical production issue"

# 合并到 master 并打 tag
git checkout master
git merge --no-ff hotfix/critical-issue
git tag -a v<X.Y.Z+1> -m "hotfix: <description>"
git push origin master --tags

# 同步到 dev
git checkout dev
git merge --no-ff hotfix/critical-issue
git push origin dev

git branch -d hotfix/critical-issue
```

## 4. Release a Version
```bash
# 从 dev 创建发布分支
git checkout dev
git checkout -b release/vX.Y.Z

# 最终测试、版本号更新、文档确认
git commit -m "chore: bump version to X.Y.Z"

# 合并到 master 并打 tag
git checkout master
git merge --no-ff release/vX.Y.Z
git tag -a vX.Y.Z -m "release: vX.Y.Z"
git push origin master --tags

# 同步到 dev
git checkout dev
git merge --no-ff release/vX.Y.Z
git push origin dev

git branch -d release/vX.Y.Z
```

---

# Version Tagging

遵循语义化版本（Semantic Versioning）：`vMAJOR.MINOR.PATCH`

| 版本段 | 何时递增 | 示例 |
|-------|---------|------|
| MAJOR | 不向后兼容的协议/接口变更 | 重构通信协议格式 |
| MINOR | 向后兼容的新功能 | 新增控制模式或查询接口 |
| PATCH | 向后兼容的 Bug 修复 | 修复滤波器越界 |

```bash
# 创建带注释的标签（推荐）
git tag -a v1.2.0 -m "feat: add rear-wheel-only mode and sync lock query"

# 推送标签
git push origin --tags
```

---

# Commit Checklist
- [ ] Commit message 使用英文
- [ ] 遵循 `<type>(<scope>): <subject>` 格式
- [ ] Subject 动词开头，现在时态，首字母小写，无句号
- [ ] 单次提交只做一件事
- [ ] 提交前已检查代码符合 `code-standards` 规范
- [ ] 不提交调试代码（临时 `print`、硬编码参数等）
- [ ] 不提交编译产物或设备特定配置文件
- [ ] 敏感信息（密钥、设备路径）不进入版本库

# .gitignore Reminders
以下内容不应提交：
```
__pycache__/
*.pyc
.venv/
/flash/            # 设备存储（ident_params.txt、gyro_offset.txt 等）
config.json        # 含本地路径或密钥的本地配置
.DS_Store
```

---

# Deliverables
- 符合 Git Flow 的分支结构
- 所有提交信息遵循 Angular 规范（英文）
- 发布版本有对应语义化标签
- 提交前通过 `code-standards` 检查清单
