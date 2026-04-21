# 2026-04-21 core 测试目录整理与系统补强设计

> 状态: Archive
> 当前约束以 `docs/developer/strategy.md`、`docs/developer/tasks.md`、`tests/README.md` 与 `tests/AGENTS.md` 为准。

## 背景

当前车端仓库测试存在两个并行问题:

1. `core` 相关测试不成体系。
2. `core` 相关测试散落在不同文件里, 目录结构也不够清晰。

从现状看:

1. `src/core/` 当前只有 `runtime.py` 与 `diagnostics.py`。
2. 但 `core` 层承接了底盘公共运行时的核心职责: 周期控制、串口输入、命令落地、姿态控制、目标分配、安全回收、诊断输出。
3. 现在真正直接覆盖 `core` 的测试并不多, 而且有一部分混在 `tests/contract/test_non_query_command_reply_contract.py` 这种职责并不匹配的文件里。
4. 现有测试整体以仓库根下的扁平文件为主, 对 `core` 这样的大模块来说, 后续继续扩充会越来越乱。

用户这轮要求已经收紧为:

1. 视觉仓库先不动。
2. 当前先把 `core` 补好。
3. 不只是补几条测试, 还要把 `core` 测试目录整理好。
4. 希望“系统补一套回归测试 + 行为测试”, 而不是继续零散补点。

## 目标

1. 把 `core` 相关测试集中整理到独立目录 `tests/unit/core/`。
2. 把现有散落的 `core` 测试搬迁到新目录并按主题重组。
3. 在迁移过程中补齐 `core` 公共行为、输入与路由、高风险内部规则、安全边界、诊断输出这五类缺口。
4. 让后续修改 `src/core/` 时可以直接在 `tests/unit/core/` 里做 TDD, 不需要再到处找散落测试。

## 非目标

1. 不整理非 `core` 测试目录。
2. 不整理 Vision 仓库测试。
3. 不顺手重构 `src/core/` 生产代码结构。
4. 不追求覆盖率数字。
5. 不把 `command` 层已独立覆盖的语义全部搬到 `core` 再测一遍。

## 方案比较

### 方案一: `tests/unit/core/` 独立分层, 推荐

做法:

1. 新建 `tests/unit/core/` 目录作为 `core` 测试专区。
2. 把现有散落的 `core` 测试迁到这里。
3. 再按主题拆成独立测试文件和一个测试辅助文件。

优点:

1. 目录职责最清晰。
2. 后续继续补 `core` 测试时最不容易重新散掉。
3. 公用桩和导入辅助可以自然收口在同一目录内。

### 方案二: 保持扁平, 只重命名文件

做法:

1. 不新建子目录, 只在 `tests/unit/` 根下增加更多 `test_core_*` 文件。

问题:

1. 解决不了当前“测试太乱”的主问题。
2. 后续 `core` 测试继续扩张后, 仍会和其他主题平铺混在一起。

本轮不采用。

### 方案三: 只抽公共辅助, 不搬现有测试

做法:

1. 只新增 `support` 一类文件, 旧测试位置先不动。

问题:

1. 这只能降低复制代码, 不能真正完成目录整理。
2. 用户明确希望“好好分一下”, 这一方案不够。

本轮不采用。

## 推荐方案

本轮采用方案一。

一句话概括:

把 `core` 测试整理成 `tests/unit/core/` 专区, 先迁移现有散落测试, 再围绕 `runtime.py` 与 `diagnostics.py` 按主题补齐一套系统的回归测试与行为测试。

## 设计细节

### 1. 新目录结构

本轮整理后的 `core` 测试目录固定为:

1. `tests/unit/core/runtime_support.py`
   - 公用桩、模块导入辅助、最小运行时上下文。

2. `tests/unit/core/test_diagnostics.py`
   - `diagnostics.py` 纯格式化行为。

3. `tests/unit/core/test_runtime_public_api.py`
   - `TransportCar` 对外公共行为与快照接口。

4. `tests/unit/core/test_runtime_uart_flow.py`
   - `_handle_uart_line()`、`_process_uart()`、查询输出通道、缓冲与错误回写。

5. `tests/unit/core/test_runtime_control_flow.py`
   - `_compute_omega_cmd()`、`_compute_planar_targets()`、`_inverse_kinematics()`、`_apply_target_speeds()`。

6. `tests/unit/core/test_runtime_safety.py`
   - `step()` 急停、`stop()` 回收、`_check_unlock()`、周期超时统计、诊断模式安全边界。

### 2. 迁移原则

现有散落测试只迁移真正属于 `core` 的部分:

1. 目前混在 `tests/contract/test_non_query_command_reply_contract.py` 里的 `TransportCar` 运行时行为测试要迁出。
2. `command` 层自己的协议与路由语义测试继续留在原文件, 不并入 `core` 目录。
3. 迁移时优先保持测试关注点不变, 只调整归属位置与公共桩复用方式。

### 3. 补齐原则

迁移之后, 再补这五类缺口:

1. 公共行为
   - `step()`、`stop()`、默认查询通道、各类快照。

2. 输入与路由
   - 查询/命令分流、多行输入、残留缓冲、错误回写。

3. 高风险内部规则
   - 角度模式/角速度模式/保持模式切换。
   - 位置模式/速度模式切换。
   - 逆运动学超限缩放。
   - `rear_only_mode` 下目标分配。

4. 安全边界
   - 急停、停车、解锁回收、未启用轮清零、控制周期 overrun 统计。

5. 诊断输出
   - 文本清理、查询回包格式、观测行格式。

### 4. 测试风格约束

本轮新增与迁移后的测试统一遵守:

1. 优先断言外部行为。
2. 少量高风险内部规则允许保留强断言。
3. 不锁日志顺序。
4. 不锁完整事件序列。
5. 不锁工厂调用次数。
6. 不依赖默认桩值的偶然细节。

### 5. 与现有测试体系的关系

整理完成后, 测试职责边界应变成:

1. `tests/unit/core/` 负责 `src/core/` 本身的运行时行为与诊断行为。
2. `tests/unit/test_non_query_command_reply.py`、`tests/unit/test_optional_lock_commands.py` 继续守命令层语义。
3. 角色层与入口层测试继续留在原位置, 不混入 `core` 目录。

### 6. 完成标准

当以下条件同时满足时, 本轮算完成:

1. `tests/unit/core/` 目录建立完成。
2. 散落的 `core` 测试已经迁入新目录。
3. `runtime.py` 与 `diagnostics.py` 的关键回归测试和行为测试已经按主题补齐。
4. 新旧测试职责边界清楚, 失败后能快速看出问题落在哪一层。
5. 相关主机侧测试通过。
