# 主车回库黄线与色标跟随实现计划

执行状态: Archive

> 给 Agent 工作者: 使用 `superpowers:subagent-driven-development` 按任务逐项实现。每个任务完成后由主线程 review diff、运行对应验证命令, 再进入下一个任务。

## 目标

按 `docs/superpowers/specs/2026-05-30-return-garage-marker-design.md` 完成“全部物体推完后主车循黄线回库、发现绿色色标后切换色标跟随、到位后进入完成态并同步辅车”的闭环。

## 架构边界

主车全局状态机仍由 `src/vision/master/state_machine.py` 维护。主车运行时只通过现有 `src/protocol/` 通信服务收发 hook 同步、可靠事件、辅车同步和速度前馈, 不直接读写 UART, 不在高频速度包中夹带业务状态。

主车 OpenART 只通过 `context_id/state/target/arg` hook 同步切换视觉上下文, 只通过 ACK 确认同步包, 只通过可靠事件回报“发现回库色标”和“回库完成”。黄线跟随与色标跟随必须是两个明确配置, 由主车重新下发 hook 完成切换。

## 文件结构

- 修改: `src/config/vision.py`  
  增加主车回库黄线配置编号、主车回库色标配置编号、总物体数量配置。
- 修改: `src/config/motion.py`  
  增加主车回库固定后退速度、固定左移速度等车端运动参数。
- 修改: `src/vision/master/state_machine.py`  
  增加回库后退、回库平移、回库色标、完成态、任务计数、回库事件消费和辅车完成同步请求。
- 修改: `src/vision/master/forward_runtime.py`  
  接入回库 hook、回库速度输出、完成停车和辅车完成同步。
- 修改: `src/vision/assistant/state_machine.py`  
  增加辅车回库跟随态和完成态接受规则。
- 修改: `src/vision/assistant/follow_runtime.py`  
  处理辅车回库跟随同步和完成同步; 回库跟随保持普通跟随行为, 完成同步清空输入并保持停止。
- 修改: `tests/unit/vision/test_master_state_machine.py`  
  覆盖主车状态机回库分支和完成态。
- 修改: `tests/unit/vision/test_assistant_state_machine.py`  
  覆盖辅车回库跟随态和完成态接受规则。
- 修改: `tests/unit/runtime/test_transport_runtime_surface.py` 或新增同目录回库测试文件  
  覆盖主车运行时回库 hook、速度前馈、完成同步和停止行为。
- 修改: `../SmartCar2026-Vision/master/main.py`  
  增加回库黄线跟随、黄线段色标发现、回库色标跟随和完成事件。
- 修改: `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`  
  覆盖回库 hook、黄线算法、色标事件和完成事件。
- 修改: `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`  
  覆盖新增事件与配置的协议契约。
## 任务拆分

### 任务 1: 主车状态机回库分支

**负责人:** 子代理任务 1

**修改范围:**

- `src/config/vision.py`
- `src/vision/master/state_machine.py`
- `tests/unit/vision/test_master_state_machine.py`

**任务目标:**

- 在 `ClearObject` 完整完成点累加已推物体数量。
- 未达到总物体数量时保持下一轮搜索。
- 达到总物体数量时进入 `RETURN_GARAGE_RETREAT`, 创建回库黄线 hook 请求, 并产生辅车回库跟随同步请求。
- 黄线 Y 对正后进入 `RETURN_GARAGE_LINE`。
- 收到“发现回库色标”事件后进入 `RETURN_GARAGE_MARKER`, 并创建回库色标 hook 请求。
- 收到“回库完成”事件后进入 `FINISHED`, 并产生辅车完成同步请求。

**通信约束:**

- 回库状态切换只消费当前 hook 上下文的可靠事件。
- 不读取或依赖高频速度包中的任何状态字段。
- 旧上下文事件不能改变状态。

**完成判据:**

- 主车纯状态机测试覆盖未达总数、达到总数、后退到黄线对正、黄线到色标、色标到完成、旧上下文忽略。
- 主车纯状态机测试覆盖进入回库时先同步辅车回库跟随, 最终完成时再同步辅车完成。
- 原有搜索、绕行、搬运和 `ClearObject` 测试不回退。

### 任务 2: 主车运行时接入回库 hook 和完成同步

**负责人:** 子代理任务 2

**修改范围:**

- `src/config/motion.py`
- `src/vision/master/forward_runtime.py`
- `tests/unit/runtime/test_transport_runtime_surface.py` 或同目录新增回库测试文件

**任务目标:**

- 消费任务 1 的回库 hook 请求, 通过现有 `TOPIC_MASTER_VISION_HOOK_SYNC` 下发给主车 OpenART。
- `RETURN_GARAGE_RETREAT` 中写入固定后退速度, 直到黄线 Y 对正。
- `RETURN_GARAGE_LINE` 中将固定左移速度与视觉纵向速度组合写入主车底盘。
- `RETURN_GARAGE_LINE` 中黄线只控制前后方向, 左右方向不跟随黄线。
- `RETURN_GARAGE_MARKER` 中直接消费主车 OpenART 色标跟随速度。
- 回库阶段继续向辅车发送速度前馈。
- 进入回库时通过现有 `TOPIC_ASSISTANT_STATE_SYNC` 下发辅车回库跟随同步。
- `FINISHED` 中写入零速度, 停止消费本车视觉速度, 并通过现有 `TOPIC_ASSISTANT_STATE_SYNC` 下发辅车完成同步。

**通信约束:**

- hook 下发、ACK 激活、事件暂存和事件消费复用现有主车运行时机制。
- 不新增 UART 直接读写。
- 不新增第二套 ACK、重发、去重或发送互斥逻辑。
- 完成同步复用现有主辅状态同步 topic。

**完成判据:**

- 运行时测试证明回库 hook 通过现有 TCP 同步发送。
- 运行时测试证明回库后退状态在黄线对正前只写入固定后退速度。
- 运行时测试证明回库平移状态只用黄线速度控制前后方向, 左右方向使用固定左移速度。
- 运行时测试证明可靠事件到达后才发生回库状态切换。
- 运行时测试证明完成态会停止主车并同步辅车。
- 运行时测试证明辅车回库跟随同步不改变普通跟随速度融合行为。
- 回库阶段前馈仍按现有 UDP 速度前馈链路发给辅车。

### 任务 3: 辅车回库跟随态和完成态接入

**负责人:** 子代理任务 3

**修改范围:**

- `src/vision/assistant/state_machine.py`
- `src/vision/assistant/follow_runtime.py`
- `tests/unit/vision/test_assistant_state_machine.py`
- `tests/unit/runtime/test_transport_runtime_surface.py` 或同目录辅车运行时测试文件

**任务目标:**

- 辅车状态机接受主车回库跟随同步和完成同步。
- 辅车回库跟随态用于区分普通搜索跟随和回库跟随。
- 辅车回库跟随态的运动行为与普通跟随态一致。
- 辅车运行时收到完成同步后清空本地视觉速度和主车前馈速度。
- 辅车写入零速度并保持停止。
- 辅车不自行切回跟随。

**通信约束:**

- 回库跟随态和完成态只由主车 `ASSISTANT_STATE_SYNC` 驱动。
- 回库跟随态不得引入新的速度融合规则。
- 辅车本地视觉事件和速度包不能触发完成态。

**完成判据:**

- 辅车状态机测试覆盖回库跟随同步、完成同步接受与未知状态拒绝。
- 辅车运行时测试覆盖回库跟随态继续按普通跟随方式融合速度。
- 辅车运行时测试覆盖完成同步后零速度和输入清空。
- 原有跟随、找物体、绕行、搬运和 `ClearObject` 测试不回退。

### 任务 4: 主车 OpenART 回库黄线配置

**负责人:** 子代理任务 4

**修改范围:**

- `../SmartCar2026-Vision/master/main.py`
- `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`

**任务目标:**

- 增加主车回库黄线配置编号。
- 实现中线左右各 5 像素列的黄线上下界均值算法。
- 支持黄线 Y 对正判定。
- 根据黄线 Y 与目标 Y 输出纵向速度。
- 回库黄线配置中同时识别绿色色标。
- 绿色色标稳定出现后回报“发现回库色标”可靠事件。

**通信约束:**

- 视觉配置只由 hook 上下文决定。
- “发现回库色标”只通过可靠事件回报。
- 高频速度包只输出纵向速度语义, 不携带色标发现标志。

**完成判据:**

- 视觉单元测试覆盖黄线中心 Y、无有效黄线、黄线误差速度和色标发现事件。
- 视觉单元测试覆盖黄线 Y 对正判定。
- 原有主车视觉搜索、绕行修正、搬运入口和搬运结束测试不回退。

### 任务 5: 主车 OpenART 回库色标跟随配置

**负责人:** 子代理任务 5

**修改范围:**

- `../SmartCar2026-Vision/master/main.py`
- `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`
- `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`

**任务目标:**

- 增加主车回库色标配置编号。
- 主车回库色标目标先复用辅车跟随主车使用的绿色色标。
- 使用主车侧独立绿色色标阈值、目标 X、目标 Y 和控制参数; 阈值初始取值复用辅车跟随主车色标阈值口径。
- 输出色标跟随 `vx / vy`。
- 色标连续稳定进入目标窗口后回报“回库完成”可靠事件。
- 保证黄线配置和色标配置事件类型不混用。

**通信约束:**

- `RETURN_GARAGE_MARKER` 配置必须由主车重新下发 hook 后生效。
- “回库完成”只通过可靠事件回报。
- 不复用辅车 OpenART 的状态机, 只复用其绿色色标目标口径与初始阈值口径。

**完成判据:**

- 视觉测试覆盖色标速度、稳定完成事件、旧配置不回报完成事件。
- 协议契约测试覆盖新增事件编号和配置组合。

### 任务 6: 双仓回归与计划归档

**负责人:** 当前会话

**修改范围:**

- `docs/superpowers/specs/2026-05-30-return-garage-marker-design.md`
- `docs/superpowers/plans/2026-05-30-return-garage-marker-implementation-plan.md`

**任务目标:**

- 将 spec 与 plan 状态更新为 `Archive`。
- 运行主车仓库与视觉仓库的相关测试。

**验证命令:**

- 主车仓库: `uv run --group test python -m pytest tests/unit/vision tests/unit/runtime -q`
- 视觉仓库: 在 `../SmartCar2026-Vision` 下运行 `uv run --with pytest python -m pytest tests/unit tests/contract -q`

**完成判据:**

- 双仓相关测试通过。
- spec / plan 状态归档。
- 正式文档同步未进入本次默认实现流程。

## 延后文档同步

以下正式文档同步不进入本计划默认执行范围, 由用户后续手动触发:

- `docs/developer/state.md`
- `docs/developer/vision.md`
- `docs/developer/protocol.md`
- `../SmartCar2026-Vision/README.md`

触发后只描述事实和阅读入口, 不复制代码流程。

## 执行顺序

1. 先执行任务 1, 固定主车全局状态和可靠事件语义。
2. 再执行任务 2, 把主车运行时接入现有通信服务。
3. 再执行任务 3, 补齐辅车回库跟随同步和完成同步。
4. 再执行任务 4, 实现主车 OpenART 回库黄线配置。
5. 再执行任务 5, 实现主车 OpenART 回库色标配置。
6. 最后执行任务 6, 做双仓回归和计划归档。

## Review 门禁

- 不允许通过高频速度包传业务阶段或完成标志。
- 不允许绕过 `src/protocol/` 直接读写 UART。
- 不允许新增第二套 ACK、重发或去重机制。
- 不允许把黄线跟随和色标跟随写成同一个隐式混合配置。
- 不允许辅车回库跟随态改变普通跟随的运动行为。
- 不允许辅车本地视觉自行决定完成态。
- 不允许为了回库功能改动现有找物体、绕行、搬运和 `ClearObject` 动作语义。
