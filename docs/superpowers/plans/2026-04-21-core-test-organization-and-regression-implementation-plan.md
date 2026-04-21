# core 测试目录整理与系统补强实施计划

> 状态: Archive
> **给 Agent 工作者:** 必须使用 `superpowers:subagent-driven-development` 按任务逐项实现, 步骤统一使用复选框 `- [ ]` 维护执行状态。
> 当前约束以 `docs/superpowers/specs/2026-04-21-core-test-organization-and-regression-design.md`、`docs/developer/strategy.md`、`docs/developer/tasks.md` 与 `tests/README.md` 为准。

**目标:** 把 `core` 测试整理成 `tests/unit/core/` 独立目录, 并在迁移现有散落测试的同时补齐 `src/core/runtime.py` 与 `src/core/diagnostics.py` 的系统回归测试和行为测试。

**架构:** 这轮先动测试目录, 不动生产代码主结构。先建立 `tests/unit/core/` 及其公用支持文件, 再迁移现有散落的 `core` 测试, 最后按公共行为、UART 输入与路由、控制流、安全边界、诊断输出五个主题补齐缺口, 让后续 `core` 开发能在一个清晰目录下直接做 TDD。

**Tech Stack:** Python、pytest、`src/core/runtime.py`、`src/core/diagnostics.py`、现有 `tests/unit` 与 `tests/contract`

---

## 文件范围与职责

- 新增: `tests/unit/core/runtime_support.py`
  - 放 `core` 测试公用桩、模块导入辅助和上下文构造。

- 新增: `tests/unit/core/test_diagnostics.py`
  - 覆盖 `diagnostics.py` 的纯格式化行为。

- 新增: `tests/unit/core/test_runtime_public_api.py`
  - 覆盖 `TransportCar` 的对外行为与快照接口。

- 新增: `tests/unit/core/test_runtime_uart_flow.py`
  - 覆盖 `_handle_uart_line()`、`_process_uart()`、缓冲与查询通道。

- 新增: `tests/unit/core/test_runtime_control_flow.py`
  - 覆盖姿态、位置/速度、逆运动学和目标分配主线。

- 新增: `tests/unit/core/test_runtime_safety.py`
  - 覆盖急停、停车、解锁、安全回收和 overrun 统计。

- 修改或删除: `tests/contract/test_non_query_command_reply_contract.py`
  - 迁出其中真正属于 `core` 行为的测试, 留下协议契约测试本身。

## Task 1: 建立 `tests/unit/core/` 骨架

**Files:**
- 新增: `tests/unit/core/runtime_support.py`
- 新增: `tests/unit/core/test_diagnostics.py`
- 新增: `tests/unit/core/test_runtime_public_api.py`
- 新增: `tests/unit/core/test_runtime_uart_flow.py`
- 新增: `tests/unit/core/test_runtime_control_flow.py`
- 新增: `tests/unit/core/test_runtime_safety.py`

- [x] 建立 `tests/unit/core/` 目录与主题文件骨架。
- [x] 把公用桩和导入辅助统一收口到 `runtime_support.py`。
- [x] 确认后续 `core` 测试不再继续散落到 `tests/unit/` 根目录。

## Task 2: 迁移现有散落的 core 测试

**Files:**
- 修改: `tests/contract/test_non_query_command_reply_contract.py`
- 新增: `tests/unit/core/test_runtime_public_api.py`
- 新增: `tests/unit/core/test_runtime_uart_flow.py`
- 新增: `tests/unit/core/test_runtime_safety.py`

- [x] 识别当前散落测试里真正属于 `core` 的部分。
- [x] 把 `TransportCar` 运行时行为测试迁入新目录对应主题文件。
- [x] 保留 `contract` 文件里仍然属于协议契约的测试, 不把命令层语义一起搬走。
- [x] 迁移后运行受影响文件测试, 确认行为不变。

## Task 3: 补 diagnostics 与公共行为缺口

**Files:**
- 新增: `tests/unit/core/test_diagnostics.py`
- 新增: `tests/unit/core/test_runtime_public_api.py`

- [x] 为 `diagnostics.py` 的文本清理和输出格式补独立测试。
- [x] 为 `step()`、`stop()`、默认查询通道和各类快照补公共行为测试。
- [x] 只锁对外行为, 不把日志与内部变量名写进断言。

## Task 4: 补 UART 输入与路由缺口

**Files:**
- 新增: `tests/unit/core/test_runtime_uart_flow.py`

- [x] 补查询/命令分流测试。
- [x] 补多行输入、残留缓冲、空行与无换行残留处理测试。
- [x] 补 UART 读异常后的错误回写和错误记录测试。
- [x] 保持与 `command` 层的职责边界, 不重复测试命令语义本身。

## Task 5: 补控制流与安全边界缺口

**Files:**
- 新增: `tests/unit/core/test_runtime_control_flow.py`
- 新增: `tests/unit/core/test_runtime_safety.py`

- [x] 补 `_compute_omega_cmd()` 三种模式下的关键行为。
- [x] 补 `_compute_planar_targets()` 在位置模式和速度模式之间的切换。
- [x] 补 `_inverse_kinematics()` 超限缩放与 `_apply_target_speeds()` 的目标分配。
- [x] 补急停、停车、解锁回收、未启用轮清零、控制周期 overrun 统计、诊断模式安全边界。

## Task 6: 收口与全量验证

**Files:**
- 修改: 如上测试文件

- [x] 运行 `tests/unit/core/` 定向测试集合。
- [x] 运行现有 `tests/unit` 全量, 确认迁移后没有职责冲突或漏测。
- [x] 复查新增测试是否重新出现过度约束。
- [x] 完成后将本轮 spec / plan 标记为 `Archive`。
