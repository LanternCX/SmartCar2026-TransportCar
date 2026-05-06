# 最小直行搬运态实施计划

> 执行状态: Review
>
> 归档条件: 对应实现完成并通过验证后, 将本文件标记为 Archive。
>
> 面向执行代理: 使用 `superpowers:subagent-driven-development` 按任务推进。每个任务完成后先回到编排者审核。实施期间不自行提交, 需要提交时先向用户确认提交消息。文档同步任务只在功能验证完成且用户明确要求提交前执行。

**目标:** 实现两车就位后的最小直行搬运态。

**架构:** 主车全局状态机在既有状态机末端增加搬运态, 前半段必须完整跑完后才能进入新增状态。主车负责等待两车就位并同步辅车搬运子状态。主车搬运速度由基础推进速度和本车视觉修正融合形成, 辅车搬运速度由头对头换算后的主车前馈和本车视觉修正融合形成。

**技术栈:** MicroPython 兼容 Python 代码、串口短包协议、主机侧 pytest。

---

## 文件结构

计划修改:

- `src/config/params.py`: 增加搬运态速度和视觉配置参数。
- `src/vision/master/state_machine.py`: 增加主车搬运态、`ALIGNED` 事件处理和辅车搬运同步输出。
- `src/vision/master/forward_runtime.py`: 增加主车搬运态速度融合、`ALIGNED` 事件消费和搬运前馈转发。
- `src/vision/assistant/state_machine.py`: 增加辅车搬运子状态。
- `src/vision/assistant/follow_runtime.py`: 增加辅车搬运子状态进入、就位回报和头对头前馈融合。
- `tests/unit/vision/test_master_state_machine.py`: 覆盖主车搬运态进入条件。
- `tests/unit/vision/test_assistant_state_machine.py`: 覆盖辅车搬运子状态接受规则。
- `tests/unit/runtime/test_master_forward_runtime.py`: 覆盖主车运行时搬运态链路。
- `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`: 覆盖辅车运行时搬运态链路。
- `../SmartCar2026-Vision/master/main.py`: 增加主车搬运入口 hook 配置和 `ALIGNED` 回报。
- `../SmartCar2026-Vision/assistant/main.py`: 增加辅车搬运入口配置和 `ALIGNED` 回报。
- `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`: 覆盖主车视觉搬运入口事件。
- `../SmartCar2026-Vision/tests/unit/test_assistant_object_approach.py`: 覆盖辅车视觉搬运入口事件。
最终文档任务修改:

- `docs/developer/state.md`: 同步状态编号、事件语义和状态流。
- `docs/developer/protocol.md`: 同步 `s/r/v` 包在搬运态中的语义。
- `docs/developer/control.md`: 同步搬运态控制链路。
- `docs/developer/vision.md`: 同步搬运态视觉职责。

不计划修改:

- 硬件驱动层。
- `TransportCar` 控制执行内核。
- 视觉仓库图像识别算法。
- 启动入口和角色识别入口。

## 任务 1: 主车状态机搬运态

**文件:**

- 修改: `src/vision/master/state_machine.py`
- 修改: `tests/unit/vision/test_master_state_machine.py`

步骤:

- [ ] 添加主车搬运态常量和 `ALIGNED` 事件常量。
- [ ] 写主车状态机测试: 主车绕行完成后, 只收到本车 `ALIGNED` 时保持二次对正状态。
- [ ] 写主车状态机测试: 主车绕行完成后, 只收到辅车 `ALIGNED` 时保持二次对正状态。
- [ ] 写主车状态机测试: 主车在首次找物体、等待辅车 idle 或主车绕行期间忽略 `ALIGNED`。
- [ ] 写主车状态机测试: 辅车找物体和辅车绕行尚未完成时忽略 `ALIGNED`。
- [ ] 写主车状态机测试: 主车和辅车都 `ALIGNED` 后进入搬运态。
- [ ] 写主车状态机测试: 进入搬运态时只发出一次辅车搬运同步请求。
- [ ] 运行主车状态机测试, 确认新增测试先失败。
- [ ] 实现主车状态机最小变更。
- [ ] 运行主车状态机测试, 确认通过。

验证命令: `python3 -m pytest tests/unit/vision/test_master_state_machine.py -q`

## 任务 2: OpenART 视觉搬运入口事件

**文件:**

- 修改: `../SmartCar2026-Vision/master/main.py`
- 修改: `../SmartCar2026-Vision/assistant/main.py`
- 修改: `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`
- 修改: `../SmartCar2026-Vision/tests/unit/test_assistant_object_approach.py`

步骤:

- [ ] 添加主车视觉 `ALIGNED` 事件常量和搬运入口 hook 配置编号。
- [ ] 添加辅车视觉 `ALIGNED` 事件常量和搬运入口配置编号。
- [ ] 写主车视觉测试: 搜索 hook 配置稳定满足条件时继续回报 `TARGET_FOUND`。
- [ ] 写主车视觉测试: 搬运入口 hook 配置稳定满足条件时回报 `ALIGNED`。
- [ ] 写主车视觉测试: 搬运入口 hook 配置继续输出 `v,<vx>,<vy>` 视觉速度。
- [ ] 写辅车视觉测试: 初次找物体配置稳定满足条件时继续回报 `TARGET_FOUND`。
- [ ] 写辅车视觉测试: 搬运入口配置稳定满足条件时回报 `ALIGNED`。
- [ ] 写辅车视觉测试: 搬运入口配置继续输出 `v,<vx>,<vy>` 视觉速度。
- [ ] 运行视觉仓库相关测试, 确认新增测试先失败。
- [ ] 实现视觉仓库最小变更。
- [ ] 运行视觉仓库相关测试, 确认通过。

验证命令: `cd ../SmartCar2026-Vision && python3 -m pytest tests/unit/test_master_hook_protocol.py tests/unit/test_assistant_object_approach.py -q`

## 任务 3: 主车运行时搬运速度链路

**文件:**

- 修改: `src/config/params.py`
- 修改: `src/vision/master/forward_runtime.py`
- 修改: `tests/unit/runtime/test_master_forward_runtime.py`

步骤:

- [ ] 添加 `TRANSPORT_FORWARD_SPEED`、`MASTER_TRANSPORT_HOOK_CONFIG_ID` 和 `ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID` 参数。
- [ ] 写运行时测试: 主车收到本车 `ALIGNED` 与辅车 `ALIGNED` 后同步辅车搬运子状态。
- [ ] 写运行时测试: 既有前半段未跑完时, 主车收到 `ALIGNED` 不同步辅车搬运子状态。
- [ ] 写运行时测试: 主车搬运态无视觉修正时写入主车正向基础速度。
- [ ] 写运行时测试: 主车搬运态叠加本车 `UART6` 视觉速度修正。
- [ ] 写运行时测试: 主车搬运态转发融合后的底盘速度到 `UART8`。
- [ ] 写运行时测试: 主车搬运态忽略新的 `UART3` 遥控速度输入。
- [ ] 运行主车运行时测试, 确认新增测试先失败。
- [ ] 实现主车运行时最小变更。
- [ ] 运行主车运行时测试, 确认通过。

验证命令: `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`

## 任务 4: 辅车状态机搬运子状态

**文件:**

- 修改: `src/vision/assistant/state_machine.py`
- 修改: `tests/unit/vision/test_assistant_state_machine.py`

步骤:

- [ ] 添加辅车搬运子状态常量。
- [ ] 写辅车状态机测试: 搬运子状态必须使用物体目标。
- [ ] 写辅车状态机测试: 搬运子状态记录主车下发的参数。
- [ ] 写辅车状态机测试: 非物体目标的搬运子状态同步被拒绝。
- [ ] 运行辅车状态机测试, 确认新增测试先失败。
- [ ] 实现辅车状态机最小变更。
- [ ] 运行辅车状态机测试, 确认通过。

验证命令: `python3 -m pytest tests/unit/vision/test_assistant_state_machine.py -q`

## 任务 5: 辅车运行时就位回报

**文件:**

- 修改: `src/vision/assistant/follow_runtime.py`
- 修改: `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`

步骤:

- [ ] 写运行时测试: 辅车绕行后回到二次对正阶段时, 本地视觉 `ALIGNED` 触发 `UART8` 就位回报。
- [ ] 写运行时测试: 辅车在找物体首次命中前和绕行期间不把 `ALIGNED` 当作搬运就位回报。
- [ ] 写运行时测试: 辅车二次对正阶段的 `TARGET_FOUND` 不重复触发绕行回报。
- [ ] 写运行时测试: 辅车就位回报在收到主车 ACK 前按可靠包机制重发。
- [ ] 运行辅车运行时测试, 确认新增测试先失败。
- [ ] 实现辅车就位回报最小变更。
- [ ] 运行辅车运行时测试, 确认通过。

验证命令: `python3 -m pytest tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py -q`

## 任务 6: 辅车搬运态速度融合

**文件:**

- 修改: `src/vision/assistant/follow_runtime.py`
- 修改: `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`

步骤:

- [ ] 写运行时测试: 辅车收到搬运子状态同步后清空寻找态速度缓存。
- [ ] 写运行时测试: 辅车搬运态接收 `UART8` 前馈后对 `vx` 做镜像。
- [ ] 写运行时测试: 辅车搬运态接收 `UART8` 前馈后对 `vy` 做前后符号转换。
- [ ] 写运行时测试: 辅车搬运态叠加本车 `UART6` 视觉修正。
- [ ] 写运行时测试: 辅车搬运态只有 `UART8` 前馈时仍响应。
- [ ] 写运行时测试: 辅车搬运态只有 `UART6` 视觉修正时仍响应。
- [ ] 写运行时测试: 辅车搬运态两路输入都缺失时不主动生成搬运速度。
- [ ] 写运行时测试: 辅车搬运态不使用 `UART8` 的 `omega`。
- [ ] 写运行时测试: `ASSISTANT_IDLE` 和 `ASSISTANT_ORBIT` 继续屏蔽速度输入。
- [ ] 运行辅车运行时测试, 确认新增测试先失败。
- [ ] 实现辅车搬运态速度融合最小变更。
- [ ] 运行辅车运行时测试, 确认通过。

验证命令: `python3 -m pytest tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py -q`

## 任务 7: 功能全量回归与收口

**文件:**

- 检查: `src/config/params.py`
- 检查: `src/vision/master/state_machine.py`
- 检查: `src/vision/master/forward_runtime.py`
- 检查: `src/vision/assistant/state_machine.py`
- 检查: `src/vision/assistant/follow_runtime.py`
- 检查: `../SmartCar2026-Vision/master/main.py`
- 检查: `../SmartCar2026-Vision/assistant/main.py`

步骤:

- [ ] 运行主机侧单元测试。
- [ ] 运行主机侧契约测试。
- [ ] 检查搬运态没有引入硬件层改动。
- [ ] 检查参数都集中在 `src/config/params.py`。
- [ ] 检查 `UART8` 搬运前馈只使用既有 `v` 包。
- [ ] 检查 `ALIGNED` 只作为可靠事件, 不通过速度包隐式切状态。
- [ ] 检查新增搬运态只挂在既有状态机末端, 不改变前半段运行顺序。
- [ ] 运行视觉仓库相关单元测试。
- [ ] 检查视觉仓库没有重写图像识别算法。
- [ ] 整理需要板端联调确认的观察点: 主车 `vy = 3`、辅车 `vy = -3`、两车视觉修正叠加、方向保持。
- [ ] 向用户汇报功能验证结果和板端待确认项。

验证命令: `python3 -m pytest tests/unit tests/contract -q && cd ../SmartCar2026-Vision && python3 -m pytest tests/unit/test_master_hook_protocol.py tests/unit/test_assistant_object_approach.py -q`

## 任务 8: 提交前文档同步

本任务只在功能验证完成后、用户要求提交前执行, 不放入功能实现执行周期。

**文件:**

- 修改: `docs/developer/state.md`
- 修改: `docs/developer/protocol.md`
- 修改: `docs/developer/control.md`
- 修改: `docs/developer/vision.md`

步骤:

- [ ] 在状态文档中补充主车搬运态、辅车搬运子状态和 `ALIGNED` 搬运入口语义。
- [ ] 在协议文档中补充搬运态对 `s/r/v` 包的使用方式。
- [ ] 在控制文档中补充主车基础推进速度、主车视觉修正、辅车头对头前馈换算和辅车视觉修正。
- [ ] 在视觉文档中补充搬运态两车各自跟随物体的视觉职责。
- [ ] 自查文档只描述当前事实, 没有新增硬件假设。
- [ ] 运行主机侧单元测试和契约测试, 确认文档同步没有伴随功能回退。
- [ ] 向用户汇报文档同步结果, 等待提交消息确认。

验证命令: `python3 -m pytest tests/unit tests/contract -q`

## 自查

- Spec 中每个需求都有对应任务。
- 计划不包含实现代码。
- 计划不包含自行提交步骤。
- 状态、协议、控制和视觉文档都纳入最后一个提交前任务。
- 硬件事实没有新增假设。
- 实现任务按可测试闭环拆分, 可以交给 Subagent Driven Develop 逐任务推进。
