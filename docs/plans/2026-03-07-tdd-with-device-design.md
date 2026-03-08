# TDD with Device 设计文档

## 背景

当前仓库已经具备三类相关能力，但还缺一条统一流程把它们强制串起来：

- `tdd-integration`：规定主机侧 `unit/contract/HIL` 的分层 TDD
- `mpy-cli`：规定如何把代码安全同步到 MicroPython 设备
- `hardware-integration`：规定硬件与实时系统联调的边界和风险

在最近一次 Stage 2 / Stage 3 调试实践中，已经暴露出一个明显空缺：

1. agent 能自然想到 `stage1`（本地 `pytest`）
2. agent 也较容易想到 `stage3`（真实硬件观察/HIL）
3. 但 agent **不会稳定地**把 `stage2`（只连接 mpy，不运行真实硬件的安全 smoke）作为强制门禁

因此需要一个新的仓库内流程 skill，把本项目的完整设备化 TDD 路径沉淀为：

`stage1 host tests -> stage2 device smoke -> stage3 device observe -> HIL evidence`

## 目标

1. 为本仓库提供一个统一 skill，指导 agent 在涉及设备路径的开发中使用完整的三阶段 TDD。
2. 把 `stage2` 明确提升为强制阶段，而不是可有可无的临时联调步骤。
3. 明确每个阶段的进入条件、退出条件、失败分类与留证要求。
4. 让 skill 复用已有 `tdd-integration`、`mpy-cli`、`hardware-integration`，避免重复维护命令细节。
5. 让后续 agent 在面对硬件耦合改动时，更稳定地给出一致流程。

## 非目标

- 不替代现有 `tdd-integration`、`mpy-cli`、`hardware-integration` 的细节说明。
- 不把所有设备命令硬编码进 skill 主体。
- 不把 Stage 3 变成默认 CI 强制门禁。
- 不新增第二套与仓库结构割裂的测试目录或命名体系。

## 方案比较

### 方案 A：新增聚合 skill（采纳）

- 新增 `.agents/skills/tdd-with-device/SKILL.md`
- skill 只做流程编排与门禁定义，显式要求调用现有技能

优点：

- 责任清晰，直接对应本次沉淀出来的开发流程
- 可以独立演进，不污染 `tdd-integration`
- 更容易通过 skill 触发条件把 agent 引导到正确流程

缺点：

- 仓库内 skill 数量增加一个

### 方案 B：扩展 `tdd-integration`

- 直接把 stage 2 / stage 3 设备化流程并进现有 `tdd-integration`

优点：

- skill 数量少

缺点：

- 主机侧 TDD 与设备化 TDD 混在一起，体积会明显增大
- 未来若 Stage 2/3 演化更快，会让该 skill 变得难维护

### 方案 C：只写开发文档，不写 skill

- 把流程写到 `docs/developer/` 或 `tests/README.md`

优点：

- 改动最小

缺点：

- agent 不容易自动触发该流程
- 无法达到“让 agent 拥有能力”的目标

## 采纳设计

### 1) skill 定位

`tdd-with-device` 是一个 **流程 skill**，不是命令参考手册。

它解决的问题是：

- 在什么情况下，硬件耦合改动必须使用三阶段 TDD
- 每个阶段的目标是什么
- 每个阶段通过/失败后下一步是什么
- 何时允许进入下一阶段，何时必须回退

它不重复以下内容：

- `tdd-integration` 的层映射细节
- `mpy-cli` 的命令说明与注意事项
- `hardware-integration` 的实时性规则和常见故障模式

这些内容通过 `REQUIRED SUB-SKILL` 或显式引用来复用。

### 2) 三阶段模型

#### `stage1`：主机侧 TDD

目标：

- 用 `tests/unit` / `tests/contract` 锁定主机可验证行为
- 必须经历 RED -> GREEN -> REFACTOR

进入条件：

- 任何功能、修复、重构，只要最终要影响设备行为，必须先从这里开始

退出条件：

- 对应主机测试全绿
- 失败测试证据存在
- 没有明显未覆盖的设备协议/状态机入口

#### `stage2`：设备安全 smoke

目标：

- 验证设备可连接、文件可同步、模块可导入、关键查询或探针可运行
- 明确禁止进入真实硬件动作或高负载控制循环

进入条件：

- `stage1` 已通过
- 变更已经能在主机侧证明行为正确

退出条件：

- `mpy-cli` 连通正常
- 设备 smoke 输出通过
- 未触发真实 IMU/电机/编码器初始化或其他高风险动作

#### `stage3`：设备实时观测

目标：

- 在真实硬件运行下验证状态快照、实时性与故障归因

进入条件：

- `stage2` 已通过
- 已有可复现的观测探针或查询入口

退出条件：

- 关键状态可读
- 5ms 控制周期没有明显破坏
- 失败可归因到 `connect/deploy/probe/observe` 类别

### 3) 回退规则

- `stage1` 失败：继续主机侧 RED/GREEN，不进入设备阶段
- `stage2` 失败：修设备兼容或部署问题，必要时补主机侧回归；不得直接跳到 `stage3`
- `stage3` 失败：先判断是设备观测基建问题还是控制逻辑问题，再决定回退到 `stage2` 还是 `stage1`

### 4) skill 主体结构

推荐结构：

1. YAML frontmatter
2. Overview
3. Required Background
4. When to Use
5. Three-Stage Flow
6. Gate Rules
7. Failure Classification
8. Deliverables
9. Red Flags
10. Quick Reference

其中 `When to Use` 和 `Three-Stage Flow` 适合各放一个小 flowchart，强调：

- 何时必须进入该 skill
- stage1 / 2 / 3 之间的门禁关系

### 5) 与现有技能的关系

- `tdd-with-device` 负责流程总控
- `tdd-integration` 负责主机测试层映射
- `mpy-cli` 负责设备文件同步与执行
- `hardware-integration` 负责实时性与硬件联调边界
- `verification-before-completion` 负责最终验证声明前的证据要求

### 6) 测试策略

按 `writing-skills` 的要求，skill 创建也走 TDD：

#### baseline（RED）

在没有新 skill 时，用子代理跑场景，记录默认行为：

- agent 会自然做 `stage1`
- agent 会较自然做 `stage3`
- agent 不会稳定把 `stage2` 当成强制门禁

#### skill（GREEN）

写出 `tdd-with-device`，显式封住这些缺口：

- 强制 `stage1 -> stage2 -> stage3`
- 明确禁止跳过 `stage2`
- 明确 `stage2` 的通过条件和失败回退

#### 验证（REFACTOR）

再次用子代理跑同类场景，验证：

- agent 会触发新 skill
- agent 会把 `stage2` 作为强制步骤
- agent 会在 `stage2` 失败时回退，而不是直接闯进 `stage3`

## 验收标准

1. 仓库新增 `.agents/skills/tdd-with-device/SKILL.md`
2. `AGENTS.md` 中的 skill 索引被更新
3. 新增设计文档与实施计划
4. baseline / post-skill 场景测试都有记录
5. skill 内容明确约束 `stage1 -> stage2 -> stage3` 的门禁顺序

## Skill TDD 验证记录

### baseline（无新 skill）

- agent 会自然使用 `tdd-integration`、`test-driven-development`、`hardware-integration`
- agent 能较稳定给出 `stage1` 与 `stage3`
- agent **不会稳定地**把 `stage2` 作为强制门禁
- 缺少 `stage2` 的失败回退规则、通过标准和证据要求

### post-skill（加入 `tdd-with-device` 后）

- agent 明确给出 `stage1 -> stage2 -> stage3`
- agent 明确把 `stage2` 视为强制门禁
- agent 在 `stage2` 失败时会回退,而不是直接进入 `stage3`
- 在当前会话的子代理验证里,显式回报 `tdd-with-device` 名称并不稳定,但阶段门禁行为已按 skill 目标收敛
