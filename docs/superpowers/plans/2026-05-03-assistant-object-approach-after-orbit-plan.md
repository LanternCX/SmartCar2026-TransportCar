# 主车绕行后辅车找同目标实施计划

> 执行状态: Archive  
> 创建日期: 2026-05-03  
> 面向执行者: 使用 Subagent-Driven 方式按任务执行；每个任务完成后 review, 再进入下一任务。  
> REQUIRED SUB-SKILL: 执行本计划时使用 `superpowers:subagent-driven-development`。

**目标:** 主车绕行完成后可靠通知辅车进入找物体阶段, 辅车识别并靠近与主车相同的目标物体, 找到后停止并回报主车。

**架构:** 主车仍维护全局状态机和协同编排。辅车新增 `ASSISTANT_APPROACH_OBJECT` 子状态, RT1021 负责接收主车同步、转发本地视觉任务、使用辅车视觉速度并回报结果；辅车 OpenART 负责在 follow 与 object approach 视觉任务之间切换。

**技术栈:** RT1021 + MicroPython、OpenART MicroPython、主机侧 Python 3.8+、pytest、现有 `src/` 与 `../SmartCar2026-Vision/` 双仓库结构。

---

## 文件结构

### 主仓库修改

- `src/vision/master/state_machine.py`  
  在绕行完成时产生辅车找物体同步请求, 保持主车正式状态编号不变。

- `src/vision/master/forward_runtime.py`  
  发送辅车找物体同步包, 处理 ACK, 接收辅车找到目标回报, 更新诊断。

- `src/vision/assistant/state_machine.py`  
  新增辅车找物体子状态、目标编号和状态接受规则。

- `src/vision/assistant/follow_runtime.py`  
  增加找物体子状态下的速度输入规则、本地视觉任务同步、视觉事件处理和 UART8 结果回报。

- `src/vision/assistant/diagnostics.py`  
  增加子目标、本地视觉同步和找物体完成诊断字段。

- `src/protocol/uart8_packet.py`  
  删除共享层主辅业务包入口。

- `src/vision/master/uart8_packet.py`  
  新建主车侧 UART8 包边界, 只维护主车发送辅车同步、接收 ACK 和接收辅车结果回报所需字段。

- `src/vision/assistant/uart8_packet.py`  
  新建辅车侧 UART8 包边界, 只维护辅车接收主车同步、发送 ACK 和发送结果回报所需字段。

- `src/protocol/packet.py`  
  保留通用短包工具和本车视觉链路解析能力, 不承载主辅业务职责。

- `src/config/params.py`  
  增加辅车找物体视觉配置编号和本地视觉同步重发间隔参数。

- `docs/developer/protocol.md`、`docs/developer/state.md`、`docs/developer/control.md`、`docs/developer/vision.md`  
  只列入后续文档确认清单, 不在本轮实现流程中修改。

### 视觉仓库修改

- `../SmartCar2026-Vision/assistant/main.py`  
  增加本地同步包解析、ACK、视觉任务切换、红色目标物体搜索速度、可靠 `TARGET_FOUND` 事件。

- `../SmartCar2026-Vision/README.md`  
  只列入后续文档确认清单, 不在本轮实现流程中修改。

### 主仓库测试

- `tests/unit/vision/test_master_state_machine.py`
- `tests/unit/vision/test_assistant_state_machine.py`
- `tests/unit/runtime/test_master_forward_runtime.py`
- `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- `tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py`
- `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`

### 视觉仓库测试

- `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`
- `../SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- 新增 `../SmartCar2026-Vision/tests/unit/test_assistant_object_approach.py`

---

## Task 1: 拆分 UART8 角色包边界并固定状态编号

**目标:** 删除共享层 `uart8_packet.py` 的主辅业务职责, 由主车和辅车分别维护自己的 UART8 包边界, 同时明确辅车找物体状态和目标编号。

**Files:**
- Delete: `src/protocol/uart8_packet.py`
- Create: `src/vision/master/uart8_packet.py`
- Create: `src/vision/assistant/uart8_packet.py`
- Modify: `src/vision/assistant/state_machine.py`
- Modify: `src/protocol/packet.py`
- Modify: `tests/unit/vision/test_assistant_state_machine.py`
- Modify: `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`

**步骤:**

- [ ] 增加失败测试: 辅车状态机导出 `ASSISTANT_STATE_APPROACH_OBJECT = 2`。
- [ ] 增加失败测试: 辅车状态机导出 `ASSISTANT_TARGET_OBJECT = 1`。
- [ ] 增加失败测试: `ASSISTANT_APPROACH_OBJECT` 只接受 `ASSISTANT_TARGET_OBJECT`。
- [ ] 增加失败测试: 代码不再从 `protocol.uart8_packet` 导入主辅业务包解析。
- [ ] 增加失败测试: 主车侧 `vision.master.uart8_packet` 可解析 `a,<seq>` 和辅车 `r,<seq>,<event>,<value>`。
- [ ] 增加失败测试: 辅车侧 `vision.assistant.uart8_packet` 可解析 `s,<seq>,<state>,<target>,<arg>`。
- [ ] 增加失败测试: `s,<seq>,<state>,<target>,<arg>` 可用于辅车本地视觉任务同步解析。
- [ ] 增加失败测试: `r,<seq>,<event>,<value>` 可用于辅车找到目标回报解析。
- [ ] 运行对应测试, 确认新增测试先失败。
- [ ] 修改辅车状态机常量和状态接受规则。
- [ ] 新建主车侧 UART8 包边界, 只包含主车需要接收和发送的字段。
- [ ] 新建辅车侧 UART8 包边界, 只包含辅车需要接收和发送的字段。
- [ ] 删除 `src/protocol/uart8_packet.py`, 并更新所有导入。
- [ ] 补齐协议解析边界, 不新增冗余字段。
- [ ] 运行对应测试, 确认通过。

**Review 检查:**

- 未新增主车全局状态编号。
- 共享协议层不再拥有主辅 UART8 业务包入口。
- 主车和辅车的 UART8 解析入口按角色分开维护。
- 协议层只解析通用字段, 不拥有业务状态机。
- 没有引入兼容双格式说明。

---

## Task 2: 主车绕行完成后发送找物体同步

**目标:** 主车在 `ORBITING` 完成后生成并可靠发送辅车找物体同步请求。

**Files:**
- Modify: `src/vision/master/state_machine.py`
- Modify: `src/vision/master/forward_runtime.py`
- Modify: `src/config/params.py`
- Modify: `tests/unit/vision/test_master_state_machine.py`
- Modify: `tests/unit/runtime/test_master_forward_runtime.py`

**步骤:**

- [ ] 增加失败测试: 主车绕行完成后回到 `IDLE`, 同时产生一次辅车找物体请求。
- [ ] 增加失败测试: 主车绕行未完成时不产生找物体请求。
- [ ] 增加失败测试: 主车发送 `ASSISTANT_APPROACH_OBJECT`、`ASSISTANT_TARGET_OBJECT` 和配置参数。
- [ ] 增加失败测试: ACK 到达前重复发送同一个同步包。
- [ ] 增加失败测试: ACK 到达后清除待确认同步包。
- [ ] 增加失败测试: 主车收到辅车 `TARGET_FOUND` 回报后回复 ACK 并记录结果。
- [ ] 运行对应测试, 确认新增测试先失败。
- [ ] 修改主车状态机, 在绕行完成时产生一次性辅车找物体请求。
- [ ] 修改主车运行时, 复用 UART8 可靠同步发送与 ACK 处理。
- [ ] 修改主车运行时, 接收并确认辅车 `TARGET_FOUND` 回报。
- [ ] 增加主车诊断字段, 暴露待确认找物体同步与辅车找到结果。
- [ ] 运行对应测试, 确认通过。

**Review 检查:**

- 找物体同步不会在每个 `IDLE` 周期重复产生。
- ACK 不被解释为辅车已经找到目标。
- 主车不在本任务中进入搬运态。

---

## Task 3: 辅车 RT1021 增加找物体子状态执行

**目标:** 辅车收到找物体同步后切换输入规则, 转发本地视觉任务, 使用辅车视觉速度并在找到后停止和回报。

**Files:**
- Modify: `src/vision/assistant/follow_runtime.py`
- Modify: `src/vision/assistant/diagnostics.py`
- Modify: `src/config/params.py`
- Modify: `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- Modify: `tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py`

**步骤:**

- [ ] 增加失败测试: 收到 `ASSISTANT_APPROACH_OBJECT` 后清空两路速度缓存并写入零速度目标。
- [ ] 增加失败测试: 收到 `ASSISTANT_APPROACH_OBJECT` 后向本车 `UART6` 可靠发送视觉任务同步。
- [ ] 增加失败测试: 本地视觉 ACK 前不应用切换前缓存的 `UART6` 速度。
- [ ] 增加失败测试: 找物体状态中忽略 `UART8` 速度前馈。
- [ ] 增加失败测试: 找物体状态中 `UART6` 速度直接形成辅车线速度。
- [ ] 增加失败测试: 收到本地视觉 `TARGET_FOUND` 后 ACK、停止线速度并锁定完成标记。
- [ ] 增加失败测试: 辅车把本地 `TARGET_FOUND` 通过 `UART8` 可靠回报给主车。
- [ ] 增加失败测试: 找到目标后不自行切回 `FOLLOW` 或 `IDLE`。
- [ ] 增加失败测试: 诊断快照暴露子目标、本地视觉同步状态和找物体完成状态。
- [ ] 运行对应测试, 确认新增测试先失败。
- [ ] 修改辅车运行时, 增加本地视觉同步待确认对象和重发逻辑。
- [ ] 修改辅车运行时, 在找物体状态中改变速度输入融合规则。
- [ ] 修改辅车运行时, 处理本地视觉可靠事件并回报主车。
- [ ] 修改诊断构建函数, 增加必要字段。
- [ ] 运行对应测试, 确认通过。

**Review 检查:**

- 未修改共享底盘执行内核。
- 找物体阶段没有使用 `UART8` 前馈推动辅车。
- `UART6` 不引入角速度输入。
- 本地视觉事件只停止运动和回报, 不直接改正式子状态。

---

## Task 4: 辅车 OpenART 增加视觉任务切换与找物体输出

**目标:** 辅车视觉支持从跟随主车标记切换到识别红色目标物体, 并在稳定找到后可靠回报。

**Files:**
- Modify: `../SmartCar2026-Vision/assistant/main.py`
- Modify: `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`
- Modify: `../SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- Create: `../SmartCar2026-Vision/tests/unit/test_assistant_object_approach.py`

**步骤:**

- [ ] 增加失败测试: 解析 `s,<seq>,<state>,<target>,<arg>` 并回复 `a,<seq>`。
- [ ] 增加失败测试: 重复同步包重复 ACK, 不重复清空可靠事件状态。
- [ ] 增加失败测试: `ASSISTANT_FOLLOW` 使用当前主车橙色色标跟随算法。
- [ ] 增加失败测试: `ASSISTANT_APPROACH_OBJECT` 使用红色目标物体候选。
- [ ] 增加失败测试: 红色目标物体阈值与主车 OpenART 红色目标阈值一致。
- [ ] 增加失败测试: 辅车橙色跟随阈值保持不变。
- [ ] 增加失败测试: 找物体任务使用目标中心横向误差和底边纵向误差生成速度。
- [ ] 增加失败测试: 找物体任务的速度帧仍为 `v,<vx>,<vy>`。
- [ ] 增加失败测试: 目标稳定满足面积和误差窗口后创建一次 `TARGET_FOUND` 事件。
- [ ] 增加失败测试: 可靠事件未确认前按间隔重发, 匹配 ACK 后停止。
- [ ] 运行视觉仓库对应测试, 确认新增测试先失败。
- [ ] 修改 `assistant/main.py`, 增加本地同步解析和视觉任务状态。
- [ ] 提取或复用候选选择、误差计算和速度格式化能力。
- [ ] 增加找物体控制参数和可靠事件参数。
- [ ] 保持数据流速度包不附加阶段、序号或元信息。
- [ ] 运行视觉仓库对应测试, 确认通过。

**Review 检查:**

- 视觉仓库不复制主仓库规则文档。
- OpenART 端不维护主车全局状态机。
- 可靠事件不会每帧创建新序号。

---

## Task 5: 代码侧联合联通检查

**目标:** 在不修改正式文档的前提下, 检查主车、辅车 RT1021 与辅车 OpenART 的代码侧协议链路能够闭合。

**Files:**
- Review only: Task 1-4 touched source and test files

**步骤:**

- [ ] 检查主车发出的找物体同步字段与辅车状态机常量一致。
- [ ] 检查主车运行时只依赖 `vision.master.uart8_packet`。
- [ ] 检查辅车运行时只依赖 `vision.assistant.uart8_packet`。
- [ ] 检查辅车转发到本地 OpenART 的视觉任务同步字段与视觉仓库解析一致。
- [ ] 检查辅车 OpenART 的 `TARGET_FOUND` 事件字段与辅车 RT1021 解析一致。
- [ ] 检查辅车橙色跟随阈值未被红色目标阈值覆盖。
- [ ] 检查辅车红色目标阈值与主车红色目标阈值一致。
- [ ] 检查辅车 RT1021 回报主车的 `TARGET_FOUND` 事件字段与主车解析一致。
- [ ] 检查 Task 1-6 没有直接修改 `docs/developer/` 或 `../SmartCar2026-Vision/README.md`。

**Review 检查:**

- 代码侧协议字段前后一致。
- 主辅 UART8 包边界不再放在共享协议层。
- 正式文档改动留到 Task 7。
- 没有新增未确认硬件事实。

---

## Task 6: 联合验证与代码收口 Review

**目标:** 确认主仓库和视觉仓库代码行为满足本轮需求, 文档落地修改留到 Task 7。

**Files:**
- Review only: Task 1-5 touched source and test files

**步骤:**

- [ ] 在主仓库运行 `python3 -m pytest tests/unit tests/contract -q`。
- [ ] 在视觉仓库运行 `python3 -m pytest tests/unit tests/contract -q`。
- [ ] 检查主车绕行完成后只产生一次找物体同步请求。
- [ ] 检查辅车找物体状态不会被 `UART8` 速度前馈带动。
- [ ] 检查辅车本地视觉 ACK 前不会使用切换前缓存的视觉速度。
- [ ] 检查辅车找到目标后会停住并回报主车。
- [ ] 检查没有修改底盘执行内核。
- [ ] 检查 `src/protocol/uart8_packet.py` 已删除, 且没有代码继续导入它。
- [ ] 检查没有新增串口号、引脚或接线假设。
- [ ] 检查代码注释使用中文, 且不使用历史性口吻。
- [ ] 检查正式文档与视觉仓库 README 未在 Task 1-6 中修改。
- [ ] 整理板端待确认项。
- [ ] 不执行 git commit；如需要提交, 先向用户确认 commit message。

**最小验证命令:**

- 主仓库: `python3 -m pytest tests/unit/vision/test_master_state_machine.py tests/unit/vision/test_assistant_state_machine.py -q`
- 主仓库: `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py -q`
- 主仓库: `python3 -m pytest tests/unit tests/contract -q`
- 视觉仓库: `cd ../SmartCar2026-Vision && python3 -m pytest tests/unit tests/contract -q`
---

## Task 7: 更新正式开发文档与视觉仓库 README

**执行条件:** 用户单独要求执行文档更新后再开始。

**目标:** 将本轮代码行为同步到正式开发文档和视觉仓库 README。

**Files:**
- Modify: `docs/developer/protocol.md`
- Modify: `docs/developer/state.md`
- Modify: `docs/developer/control.md`
- Modify: `docs/developer/vision.md`
- Modify: `../SmartCar2026-Vision/README.md`

**步骤:**

- [ ] 更新 `docs/developer/protocol.md`: 记录主辅 UART8 包边界按主车/辅车分别维护, 并记录辅车本地 `UART6` 视觉任务同步与辅车找到目标回报。
- [ ] 更新 `docs/developer/state.md`: 记录新增辅车子状态、目标编号和主车绕行完成后的同步语义。
- [ ] 更新 `docs/developer/control.md`: 记录辅车找物体阶段的速度来源和停止规则。
- [ ] 更新 `docs/developer/vision.md`: 记录辅车橙色色标跟随、红色目标物体识别任务切换和找物体算法职责。
- [ ] 更新 `../SmartCar2026-Vision/README.md`: 记录辅车 OpenART 的本地同步、橙色跟随阈值、红色目标阈值、找物体输出和事件回报。
- [ ] 自检文档只描述当前事实, 不使用历史性口吻。

**Review 检查:**

- 文档只写当前行为, 不写行为对比。
- 文档没有新增未确认硬件事实。
- 文档没有把辅车本地视觉任务写成主车全局状态。
