# 绕行前辅车 Idle 同步实施计划

> 执行状态: Archive
> 创建日期: 2026-05-03  
> 面向执行者: 使用 Subagent-Driven 方式按任务执行；每个任务完成后 review, 再进入下一任务。  
> REQUIRED SUB-SKILL: 执行本计划时使用 `superpowers:subagent-driven-development`。

**目标:** 主车从寻找物体进入绕行前, 可靠同步辅车进入 idle, 并在确认后再开始绕行。

**架构:** 主车和辅车分别在 `vision/` 层维护状态机。`protocol` 层只负责短包解析和格式化, 不拥有状态、目标或事件常量；主车全局状态机不新增正式等待状态, 将等待辅车 idle ACK 作为 `SEARCH_OBJECT -> ORBITING` 跳转内部过程；辅车维护最小子状态机, 子状态只由主车 `UART8` 同步包驱动。

**技术栈:** RT1021 + MicroPython、主机侧 Python 3.8+、pytest、现有 `src/` 单根目录结构。

---

## 文件结构

### 删除

- `src/protocol/state.py`  
  删除业务状态常量模块；协议层只保留短包解析和格式化。

### 新建

- `src/vision/assistant/state_machine.py`  
  维护辅车子状态常量和最小辅车状态机。

### 修改

- `src/vision/master/state_machine.py`  
  维护主车全局状态、主车目标、主车视觉事件常量和主车状态机。

- `src/config/params.py`  
  删除 `MASTER_DISABLE_UART8_OUTPUT` 参数。

- `src/vision/master/forward_runtime.py`  
  装配辅车 idle 同步请求、可靠重发、ACK 处理、等待期间主车停止和诊断输出。

- `src/vision/assistant/follow_runtime.py`  
  增加辅车子状态处理；idle 时清空两路速度缓存, 写入零速度目标, 并阻止速度包重新生效。

- `src/vision/assistant/diagnostics.py`  
  在辅车诊断快照中暴露当前子状态。

- `docs/developer/protocol.md`、`docs/developer/state.md`、`docs/developer/control.md`、`docs/developer/vision.md`  
  同步主辅状态所有权、UART8 辅车子状态语义和绕行前 idle 流程。

### 测试

- `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`
- `tests/unit/protocol/test_packet.py`
- `tests/unit/vision/test_master_state_machine.py`
- `tests/unit/vision/test_assistant_state_machine.py`
- `tests/unit/runtime/test_master_forward_runtime.py`
- `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- `tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py`

---

## Task 1: 将状态语义迁出 protocol 层

**目标:** `protocol` 层只保留短包解析和格式化；主车全局状态、辅车子状态、目标和事件常量由 `vision/` 层维护。

**Files:**
- Delete: `src/protocol/state.py`
- Modify: `src/vision/master/state_machine.py`
- Create: `src/vision/assistant/state_machine.py`
- Modify: `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`
- Modify: `tests/unit/protocol/test_packet.py`
- Modify: `tests/unit/vision/test_master_state_machine.py`
- Create: `tests/unit/vision/test_assistant_state_machine.py`

**步骤:**

- [ ] 修改失败测试: 主车状态机测试改为从 `vision.master.state_machine` 导入 `STATE_IDLE`、`STATE_SEARCH_OBJECT`、`STATE_ORBITING`、`STATE_STOP`、`TARGET_OBJECT`、`EVENT_TARGET_FOUND`。
- [ ] 增加失败测试: 辅车状态机测试从 `vision.assistant.state_machine` 导入 `ASSISTANT_STATE_IDLE = 0`、`ASSISTANT_STATE_FOLLOW = 1`、`ASSISTANT_TARGET_NONE = 0`。
- [ ] 修改契约测试: 协议契约只断言短包线格式解析和格式化, 不从 `protocol.state` 导入业务常量。
- [ ] 修改协议单元测试: `s,<seq>,<state>,<target>,<arg>` 仍按 UART8 辅车同步包解析。
- [ ] 运行 `python3 -m pytest tests/contract/serial_protocol/test_serial_packet_protocol_contract.py tests/unit/protocol/test_packet.py tests/unit/vision/test_master_state_machine.py tests/unit/vision/test_assistant_state_machine.py -q`, 确认新增测试先失败。
- [ ] 将主车全局状态、主车目标和主车视觉事件常量放入 `src/vision/master/state_machine.py`。
- [ ] 新建 `src/vision/assistant/state_machine.py`, 维护辅车子状态常量和最小状态机。
- [ ] 删除 `src/protocol/state.py`, 并更新所有运行时代码和测试导入路径。
- [ ] 运行同一测试命令, 确认通过。

**Review 检查:**

- `src/protocol/state.py` 已删除。
- `src/protocol/` 没有业务状态、目标或事件常量。
- 协议层没有引入业务状态机对象。
- UART8 同步包仍是短文本格式。
- 没有新增并行字段或双轨格式。

---

## Task 2: 主车状态机增加绕行前 idle 等待过程

**目标:** 主车收到 `TARGET_FOUND` 后先请求辅车 idle, ACK 到达后再进入 `ORBITING`。

**Files:**
- Modify: `src/vision/master/state_machine.py`
- Modify: `tests/unit/vision/test_master_state_machine.py`

**步骤:**

- [ ] 增加失败测试: 匹配 `TARGET_FOUND` 后状态机不直接进入 `ORBITING`, 而是产生辅车 idle 请求。
- [ ] 增加失败测试: 产生 idle 请求后, 重复目标事件不会重复产生新的 idle 请求。
- [ ] 增加失败测试: 调用“辅车 idle 已确认”的状态机入口后, 才进入 `ORBITING` 并产生绕行动作。
- [ ] 增加失败测试: 上下文不匹配或事件类型不匹配时, 不产生 idle 请求。
- [ ] 运行 `python3 -m pytest tests/unit/vision/test_master_state_machine.py -q`, 确认新增测试先失败。
- [ ] 修改主车状态机, 增加内部等待标记、idle 请求输出和 ACK 完成入口。
- [ ] 保持主车状态、目标和事件常量由 `vision.master.state_machine` 导出。
- [ ] 保持正式状态编号不变, 不增加 `WAIT_ASSISTANT_IDLE`。
- [ ] 运行同一测试命令, 确认通过。

**Review 检查:**

- 状态跳转判断仍在主车状态机内。
- runtime 不替状态机决定是否进入 `ORBITING`。
- 等待过程不是正式协议状态。

---

## Task 3: 主车运行时装配 UART8 idle 同步

**目标:** 主车运行时把状态机 idle 请求转换为 UART8 可靠同步包, 并在 ACK 前停止本车运动。

**Files:**
- Modify: `src/vision/master/forward_runtime.py`
- Modify: `src/config/params.py`
- Modify: `tests/unit/runtime/test_master_forward_runtime.py`

**步骤:**

- [ ] 增加失败测试: 目标命中后主车向 UART8 发送 `ASSISTANT_IDLE` 同步包。
- [ ] 增加失败测试: idle ACK 到达前不调用 rear only 绕行动作。
- [ ] 增加失败测试: idle ACK 到达后才调用一次 rear only 绕行动作。
- [ ] 增加失败测试: 等待 idle ACK 期间不应用新的 UART6 搜索速度, 并保持本车零速度目标。
- [ ] 增加失败测试: 未收到 ACK 时按可靠重发间隔重复发送同一 idle 同步包。
- [ ] 增加失败测试: 删除 `MASTER_DISABLE_UART8_OUTPUT` 后, 主车 UART8 输出不再被该参数全局屏蔽。
- [ ] 运行 `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`, 确认新增测试先失败。
- [ ] 删除 `src/config/params.py` 中的 `MASTER_DISABLE_UART8_OUTPUT`。
- [ ] 删除主车运行时中的 UART8 全局关闭分支。
- [ ] 在主车运行时消费状态机 idle 请求, 创建待确认 UART8 同步包。
- [ ] 在主车运行时处理 UART8 ACK, 匹配待确认 idle 同步后通知状态机。
- [ ] 在等待 ACK 期间清除主车视觉搜索速度缓存并写入零速度目标。
- [ ] 更新 UART3 诊断行, 暴露是否等待辅车 idle ACK。
- [ ] 运行同一测试命令, 确认通过。

**Review 检查:**

- `UART8` 状态同步不携带主车视觉 `context_id`。
- ACK 只确认可靠包处理, 不被解释成辅车业务状态主动回报。
- 主车绕行动作不会重复触发。

---

## Task 4: 辅车子状态机与 idle 行为

**目标:** 辅车收到 idle 同步后停止线速度, 清空两路速度缓存, 并保持 idle 状态。

**Files:**
- Modify: `src/vision/assistant/follow_runtime.py`
- Modify: `src/vision/assistant/diagnostics.py`
- Modify: `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- Modify: `tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py`

**步骤:**

- [ ] 增加失败测试: 辅车默认子状态为 `ASSISTANT_FOLLOW`, 现有速度融合行为保持。
- [ ] 增加失败测试: 收到 `ASSISTANT_IDLE` 同步后记录子状态、清空 UART8 与 UART6 速度缓存、写入零速度目标并 ACK。
- [ ] 增加失败测试: idle 后继续收到 UART8 或 UART6 速度包不会更新速度缓存, 也不会写入非零底盘速度。
- [ ] 增加失败测试: 重复 idle 同步只重复 ACK, 不重复应用状态副作用。
- [ ] 增加失败测试: 较早同步包只 ACK, 不回退当前子状态。
- [ ] 增加失败测试: UART6 仍不处理状态同步包。
- [ ] 增加失败测试: 诊断快照暴露辅车当前子状态。
- [ ] 运行 `python3 -m pytest tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py -q`, 确认新增测试先失败。
- [ ] 在辅车运行时增加当前子状态字段和状态应用入口。
- [ ] 在处理 UART8 同步包时, 只接受 `vision.assistant.state_machine` 定义的辅车子状态语义。
- [ ] 实现 idle 应用: 清空两路速度缓存, 写入 `vx=0`、`vy=0`、`omega=0` 的速度目标, 不写入 `angle`。
- [ ] 在 idle 状态下继续读取但忽略速度短包对角色层速度缓存和底盘输出的影响。
- [ ] 更新诊断快照字段。
- [ ] 运行同一测试命令, 确认通过。

**Review 检查:**

- 没有新增底盘角度保持接口。
- 辅车不会根据速度包或视觉包自行离开 idle。
- 角色层没有直接操作底盘内部角度字段。

---

## Task 5: 更新开发文档

**目标:** 让正式文档与代码语义一致, 避免把辅车子状态误读成主车全局状态。

**Files:**
- Modify: `docs/developer/protocol.md`
- Modify: `docs/developer/state.md`
- Modify: `docs/developer/control.md`
- Modify: `docs/developer/vision.md`

**步骤:**

- [ ] 更新 `protocol.md`: 说明协议层只定义短包字段, 不拥有业务状态机或状态常量。
- [ ] 更新 `protocol.md`: 说明 UART8 同步包的 `state` 在辅车链路中表示辅车子状态。
- [ ] 更新 `state.md`: 说明主车全局状态和辅车子状态由 `vision/` 层维护。
- [ ] 更新 `state.md`: 说明主车全局状态不新增等待状态, 等待辅车 idle ACK 是跳转内部过程。
- [ ] 更新 `state.md`: 增加辅车子状态编号表和状态所有权说明。
- [ ] 更新 `control.md`: 说明主车等待 idle ACK 时停止本车运动, ACK 后再绕行。
- [ ] 更新 `vision.md`: 说明辅车 idle 时停止线速度、清空两路速度缓存、不新增角度接口。
- [ ] 自检文档只写当前事实, 不使用历史性口吻。

**Review 检查:**

- 文档没有描述旧入口或双协议格式。
- 文档没有把协议层写成状态机 owner 或常量 owner。
- 文档没有引入未确认的新硬件事实。

---

## Task 6: 联合验证与收口 Review

**目标:** 确认主辅状态同步、现有通信协议和运行时回归全部通过。

**Files:**
- Review only: implementation and docs changed in Task 1-5

**步骤:**

- [ ] 运行 `python3 -m pytest tests/unit tests/contract -q`。
- [ ] 若失败, 按失败测试定位到对应任务修复, 不扩大任务范围。
- [ ] 检查 `src/protocol/state.py` 不再存在。
- [ ] 检查 `src/config/params.py` 中不再存在 `MASTER_DISABLE_UART8_OUTPUT`。
- [ ] 检查代码注释和文档字符串为中文 Doxygen 风格。
- [ ] 检查没有新增硬件串口号、引脚或接线假设。
- [ ] 检查主车全局状态编号未新增等待状态。
- [ ] 检查辅车 idle 后没有恢复 follow 的实现。
- [ ] 将验证结果和未完成的板端确认项汇报给用户。
- [ ] 不执行 git commit；如需要提交, 先向用户确认 commit message。

**最小验证命令:**

- `python3 -m pytest tests/unit/vision/test_master_state_machine.py -q`
- `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`
- `python3 -m pytest tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py -q`
- `python3 -m pytest tests/unit tests/contract -q`
