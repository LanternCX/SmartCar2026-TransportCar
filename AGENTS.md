# AGENTS.md

本文件是本仓库给代码代理（agent）使用的统一执行规范。
若与其他说明冲突，优先遵循用户在当前会话中的明确指令。

## 1. 项目快照

- 平台：RT1021 + MicroPython。
- 主要语言：Python。
- 运行时代码目录：
  - `src/config/`
  - `src/control/`
  - `src/filters/`
  - `src/hardware/`
  - `src/services/`
  - `src/storage/`
  - `src/utils/`
- 测试目录：
  - `tests/unit/`
  - `tests/contract/`
  - `tests/hil/`
- CI 工作流：`.github/workflows/tdd.yml`。

## 2. 环境准备

本地建议 Python 3.10+（CI 使用 3.11）。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install pytest
```

可选类型检查工具：

```bash
python3 -m pip install pyright
```

## 3. 构建 / 检查 / 测试命令

### 3.1 构建与部署

- 本仓库无传统主机构建步骤。
- 烧录部署使用 `mpy-cli`（或 Thonny）。

```bash
mpy-cli plan
mpy-cli deploy
```

### 3.2 类型检查

- 类型检查配置见 `pyrightconfig.json`。

```bash
python3 -m pyright
```

### 3.3 测试命令（重点）

运行主机可执行测试全集：

```bash
python3 -m pytest tests/unit tests/contract -q
```

仅跑 unit：

```bash
python3 -m pytest tests/unit -q
```

仅跑 contract：

```bash
python3 -m pytest tests/contract -q
```

按 marker 跑：

```bash
python3 -m pytest -m unit -q
python3 -m pytest -m contract -q
```

跑单文件：

```bash
python3 -m pytest tests/unit/services/test_commander.py -q
```

跑单用例（TDD 最常用）：

```bash
python3 -m pytest tests/unit/services/test_commander.py::test_tokenize_bare_reset -q
```

按关键字过滤：

```bash
python3 -m pytest tests/unit -k tokenize -q
```

仅收集测试：

```bash
python3 -m pytest --collect-only -q
```

## 4. TDD 工作流（强制）

本仓库开发必须遵循 RED -> GREEN -> REFACTOR：

1. RED：先写失败测试。
2. 确认失败原因与预期一致。
3. GREEN：写最小实现使测试通过。
4. 重新运行测试确认全绿。
5. REFACTOR：在全绿前提下重构。

分层映射规则：

- 纯逻辑改动（`src/control/`、`src/filters/`、解析器/路由/存储/工具）优先写 `tests/unit/`。
- 命令行为改动（`src/services/commands/`）优先写 `tests/contract/`。
- 强硬件耦合改动（`src/hardware/`、`src/services/transport_car.py`）至少补 HIL 证据到 `tests/hil/`，并尽量补主机侧回归。

## 5. 代码风格规范

### 5.1 注释与文档字符串

- 本项目代码注释与文档字符串使用中文。
- 函数/类/模块应有简洁文档字符串。
- 仅对非显然逻辑加注释，避免噪声注释。

### 5.2 导入规范

- 导入顺序：标准库 -> 平台/第三方 -> 本地模块。
- 删除未使用导入。
- 避免循环依赖，尤其跨层循环依赖。

### 5.3 格式与结构

- 遵循邻近文件既有风格。
- 禁止对无关文件做大规模格式化。
- 函数保持单一职责，重复逻辑按需提取。

### 5.4 类型与命名

- 尽量显式类型标注，避免滥用 `Any`。
- 命名约定：
  - 文件/函数/变量：`snake_case`
  - 类：`PascalCase`
  - 常量：`UPPER_SNAKE_CASE`
  - 私有成员：前导 `_`

### 5.5 错误处理

- 优先捕获具体异常。
- 不允许静默吞错。
- 错误路径保留足够上下文，便于定位。

### 5.6 配置与实时性

- 可调参数集中在 `src/config/params.py`。
- 避免在运行逻辑中硬编码魔法数字。
- 控制周期目标为 5ms。
- 时序关键路径避免阻塞。
- 中断回调尽量只置位标志，重计算放主循环。

## 6. 架构边界（必须遵守）

- `src/hardware/`：硬件访问与驱动抽象。
- `src/control/`：控制算法（PID/运动学/里程计等）。
- `src/filters/`：信号滤波。
- `src/services/`：编排层与命令流。
- `src/storage/`：持久化。
- `src/config/`：集中配置与常量。
- `src/utils/`：通用工具。

依赖方向：下层不得反向依赖上层。

## 7. 命令系统约定

- 新命令放在 `src/services/commands/cmd_*.py`，使用 `@router.command(...)`。
- 新查询放在 `src/services/commands/query_*.py`，使用 `@router.query(...)`。
- 注册由 `src/services/commands/__init__.py` 自动发现完成。
- 跨命令后处理统一放在 `TransportCar._finalize_route(...)`。

## 8. Git 工作流约定

- 本仓库使用项目内 Git Flow + Angular Commit 规范。
- 禁止用 superpowers 自带 git workflow 覆盖本仓库规范。

分支模型：

- 长期分支：`master`、`dev`
- 临时分支：`feature/*`、`fix/*`、`hotfix/*`、`release/*`

提交信息格式：

```text
<type>(<scope>): <subject>
```

常用 type：`feat`、`fix`、`refactor`、`perf`、`docs`、`test`、`chore`、`style`。

## 9. CI 期望

- CI 在 PR / push / tag 上运行 `tests/unit` + `tests/contract`。
- 合并前必须保证两层测试通过。

## 10. 文档语言规范（强制）

- 本项目所有文档默认使用中文。
- 包括但不限于：`Readme.md`、`docs/` 下文档、`tests/hil/` 场景说明、计划文档、代理规则文档。
- 非经用户明确要求，不新增英文版或双语版。

## 11. 项目技能索引（已合并自 `.agents/skills/README.md`）

### 11.1 核心技能

原 `tdd-integration`、`tdd-with-device`、`hardware-integration` 已合并为 `embedded-development`，遇到相关任务不再分别选择旧 skill。

1. `code-standards`
   - 代码规范与架构边界统一入口
   - 分层职责、依赖规则、评审与重构触发条件

2. `control-system`
   - 控制算法开发、调参与故障定位
   - PID、运动学、里程计、模式切换联调

3. `embedded-development`
   - 主机侧分层 TDD、设备门禁、硬件集成与实时性统一入口
   - 覆盖 `unit/contract/HIL` 选层、`stage1 -> stage2 -> stage3 -> HIL` 与 5ms 约束

4. `git-workflow`
   - 项目 Git Flow + Angular Conventional Commit
   - 项目 Git 规范唯一来源

5. `mpy-cli`
   - 统一 MicroPython 端部署与文件运维命令
   - 覆盖 init/config/plan/deploy/upload/run/delete/tree 流程

### 11.2 新功能开发顺序

1. 先看 `git-workflow` 创建分支。
   - 若命中 superpowers 的 `using-git-worktrees`，一律改走项目内同名覆盖 skill，并重定向到 `git-workflow`；默认不创建 git worktree，按当前工作树执行。
2. 按 `code-standards` 放置模块并实现。
3. 涉及控制逻辑查 `control-system`。
4. 涉及行为改动、测试选层、外设/驱动、设备路径或 HIL 验证时，统一执行 `embedded-development`。
5. 涉及设备同步/烧录时优先查 `mpy-cli`。
6. 提交前回到 `git-workflow` 校验提交格式。

### 11.3 问题诊断入口

1. 控制不稳定：优先 `control-system`。
2. 外设异常、时序抖动、host / smoke / observe / HIL 路径判断：优先 `embedded-development`。
3. 架构耦合或风格问题：回到 `code-standards`。
4. 部署或串口同步问题：优先 `mpy-cli`。

## 12. Cursor / Copilot 规则状态

已检查路径：

- `.cursor/rules/`
- `.cursorrules`
- `.github/copilot-instructions.md`

当前仓库未发现上述 Cursor/Copilot 规则文件。
