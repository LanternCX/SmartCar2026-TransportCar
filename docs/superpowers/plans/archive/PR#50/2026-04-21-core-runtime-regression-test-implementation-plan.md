# core 运行时回归与行为测试补强实施计划

> 状态: Archive
> 归档原因: 被“core 测试目录整理与系统补强”实施计划替代。
> **给 Agent 工作者:** 必须使用 `superpowers:subagent-driven-development` 按任务逐项实现, 步骤统一使用复选框 `- [ ]` 维护执行状态。
> 当前约束以 `docs/superpowers/specs/archive/PR#50/2026-04-21-core-runtime-regression-test-design.md`、`docs/developer/strategy.md`、`docs/developer/tasks.md` 与 `tests/README.md` 为准。

**目标:** 为 `src/core/runtime.py` 与 `src/core/diagnostics.py` 建立一套按主题分文件组织的回归测试和行为测试, 让后续修改 `core` 时可以直接用 TDD 守住公共能力与高风险边界。

**架构:** 不重构生产代码主结构, 优先新增专门的 `core` 测试文件和测试辅助模块。测试按公共行为、UART 输入与路由、控制流、高风险内部规则、安全边界、诊断格式化六个主题拆开, 减少不同关注点混在一个大测试文件里。

**技术栈:** Python、pytest、`src/core/runtime.py`、`src/core/diagnostics.py`、现有 `tests/unit` 与 `tests/contract`

---

## 文件范围与职责

- 新增: `tests/unit/core_runtime_test_support.py`
  - 集中放 `core` 测试公用的桩对象、模块导入辅助和最小上下文构造。

- 新增: `tests/unit/test_core_diagnostics.py`
  - 覆盖 `diagnostics.py` 的字符串清理与行格式化行为。

- 新增: `tests/unit/test_core_runtime_public_api.py`
  - 覆盖 `TransportCar` 的公共对外行为与快照接口。

- 新增: `tests/unit/test_core_runtime_uart_flow.py`
  - 覆盖 `_handle_uart_line()`、`_process_uart()`、查询通道路由与缓冲行为。

- 新增: `tests/unit/test_core_runtime_control_flow.py`
  - 覆盖 `_compute_omega_cmd()`、`_compute_planar_targets()`、`_inverse_kinematics()`、`_apply_target_speeds()`。

- 新增: `tests/unit/test_core_runtime_safety.py`
  - 覆盖 `stop()`、`step()` 急停路径、`_check_unlock()`、overrun 统计与安全回收行为。

- 视情况微调: `tests/contract/test_non_query_command_reply_contract.py`
  - 只在必须共享已有导入桩时做最小整理, 不把本轮主目标继续塞回该文件。

## Task 1: 建立 core 测试辅助与文件骨架

**Files:**
- 新增: `tests/unit/core_runtime_test_support.py`
- 新增: `tests/unit/test_core_diagnostics.py`
- 新增: `tests/unit/test_core_runtime_public_api.py`
- 新增: `tests/unit/test_core_runtime_uart_flow.py`
- 新增: `tests/unit/test_core_runtime_control_flow.py`
- 新增: `tests/unit/test_core_runtime_safety.py`

- [ ] 先把 `core` 测试公用桩和导入辅助抽到单独支持文件, 避免每个测试文件各自复制一套运行时假环境。
- [ ] 为五个主题测试文件建好最小骨架和中文测试命名风格。
- [ ] 确认每个测试文件只负责一个主题, 不交叉塞行为。

## Task 2: 补 diagnostics 与公共行为测试

**Files:**
- 新增: `tests/unit/test_core_diagnostics.py`
- 新增: `tests/unit/test_core_runtime_public_api.py`

- [ ] 为 `_sanitize_text()`、`format_snapshot_value()`、`format_query_response()`、`format_observe_line()` 补纯行为测试。
- [ ] 为 `step()`、`stop()`、`get_query_uart()` 与各类 `build_*_snapshot()` 补公共行为测试。
- [ ] 公共行为测试只锁对外结果, 不锁日志和内部临时状态。
- [ ] 跑定向测试, 确认文件骨架和公共行为覆盖都成立。

## Task 3: 补 UART 输入与路由测试

**Files:**
- 新增: `tests/unit/test_core_runtime_uart_flow.py`

- [ ] 补查询与普通命令分流测试。
- [ ] 补多行输入、缓冲残留和空行处理测试。
- [ ] 补读串口异常后的最小错误回写测试。
- [ ] 明确只测 `core` 的输入编排, 不重复测试路由器自己的命令语义。

## Task 4: 补控制流与高风险内部规则测试

**Files:**
- 新增: `tests/unit/test_core_runtime_control_flow.py`

- [ ] 补 `_compute_omega_cmd()` 在角度模式、角速度模式、保持模式下的关键行为。
- [ ] 补 `_compute_planar_targets()` 在位置模式与速度模式之间的切换行为。
- [ ] 补 `_inverse_kinematics()` 的超限缩放行为。
- [ ] 补 `_apply_target_speeds()` 在全向模式、后轮模式、未启用轮清零下的关键行为。
- [ ] 这组测试允许对关键结果保留较强断言, 但不跟踪实现步骤。

## Task 5: 补安全边界测试

**Files:**
- 新增: `tests/unit/test_core_runtime_safety.py`

- [ ] 补 `step()` 急停开关触发停止的测试。
- [ ] 补 `stop()` 对 ticker、电机和停机提示的安全回收测试。
- [ ] 补 `_check_unlock()` 在锁定完成后解锁、回收后轮模式和清零输出的测试。
- [ ] 补 `_handle_tick()` 的计数、dt 统计和 overrun 累积测试。
- [ ] 补诊断模式空硬件下仍能维持最小运行事实的测试。

## Task 6: 收口与全量验证

**Files:**
- 修改: 如上测试文件

- [ ] 运行新增 `core` 测试文件集合。
- [ ] 运行现有 `tests/unit` 全量, 确认没有与旧测试职责冲突。
- [ ] 复查新增测试是否出现类名字符串、完整事件序列、工厂调用次数、默认桩值精确绑定等过度约束。
- [ ] 若需要, 对测试文件名、测试名和注释做最小整理, 让失败后更容易快速定位到主题。
