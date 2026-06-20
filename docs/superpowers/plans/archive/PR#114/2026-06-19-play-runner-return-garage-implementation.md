# Play 播放器与回库 Play 实现计划

> 执行状态: Archive
> 日期: 2026-06-19
> 适用 Spec: `docs/superpowers/specs/archive/PR#114/2026-06-19-play-runner-return-garage-design.md`
> For agentic workers: REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**目标:** 建立 `src/play/` 播放框架, 用主车回库 Play 和辅车回库 Play 接管回库动作, 并把视觉仓库 v2 回库黄线输出收口为 Play 条件输入。

**架构:** Play 框架只负责本车固定动作播放和运动接管。主辅状态机仍负责全局阶段和同步, 运行时负责把本车底盘、视觉事件缓存和 Play 播放器连接起来。视觉仓库 v2 入口只提供黄线判据事件或观测, 回库黄线跟随速度直接下线。

**技术栈:** MicroPython 兼容 Python 代码、OpenART 视觉脚本、现有 `TransportCar` 底盘接口、现有 UART6 本地视觉事件链路、现有 UART8 主辅状态同步链路、`uv run pytest` 主机侧测试。

---

## 文件结构

新增文件:

- `src/play/__init__.py`: 暴露 Play 框架最小入口。
- `src/play/base.py`: 定义 Play 状态、步骤状态、播放结果和 `BasePlay`。
- `src/play/runner.py`: 定义 `PlayRunner`, 对外通过运行时字段 `play.run(...)` 启动, 通过 `play.tick(...)` 推进。
- `src/play/context.py`: 定义 `PlayContext`, 封装底盘动作和黄线条件查询。
- `src/play/steps.py`: 定义位置式步骤、速度式步骤和保持步骤。
- `src/play/conditions.py`: 定义通用只读回调函数辅助结构。
- `src/play/routines/__init__.py`: 具体 Play 流程包入口。
- `src/play/routines/master_return_garage.py`: 定义主车回库 Play 和局部常量。
- `src/play/routines/assistant_return_garage.py`: 定义辅车回库 Play 和局部常量。
- `tests/unit/play/__init__.py`: Play 单元测试包入口。
- `tests/unit/play/test_runner.py`: 播放器占用、拒绝、释放和返回状态测试。
- `tests/unit/play/test_steps.py`: 步骤状态、一次性下发、持续速度和保持态测试。
- `tests/unit/play/test_return_garage_play.py`: 主车和辅车回库 Play 步骤结构测试。

修改文件:

- `src/vision/master/state_machine.py`: 将最终回库阶段收口为 Play 启动状态, 取消旧的回库黄线平移停车跳转。
- `src/vision/master/forward_runtime.py`: 持有 `self.play`, 接入主车 Play 上下文, Play 活跃时跳过普通速度输出。
- `src/vision/assistant/state_machine.py`: 将辅车回库状态语义调整为回库 Play, 不再由本地完成事件进入停车完成态。
- `src/vision/assistant/follow_runtime.py`: 持有 `self.play`, 接入辅车 Play 上下文, Play 活跃时跳过普通速度输出。
- `tests/unit/vision/test_master_state_machine.py`: 更新主车回库状态机测试。
- `tests/unit/vision/test_assistant_state_machine.py`: 更新辅车回库状态机测试。
- `tests/unit/runtime/test_transport_runtime_surface.py`: 更新主辅运行时回库行为测试。
- `../SmartCar2026-Vision/master/main_v2.py`: 主车回库黄线判据保留为 Play 条件输入, 删除回库黄线跟随速度。
- `../SmartCar2026-Vision/assistant/main_v2.py`: 辅车回库黄线判据保留为 Play 条件输入, 删除回库黄线跟随速度。
- `../SmartCar2026-Vision/tests/unit/test_master_main_v2.py`: 更新主车 OpenART 回库黄线判据测试。
- `../SmartCar2026-Vision/tests/unit/test_assistant_main_v2.py`: 更新辅车 OpenART 回库黄线判据测试。
- `../SmartCar2026-Vision/tests/contract/test_main_v2_vision_protocol_contract.py`: 更新主辅回库视觉协议合同测试。
- `src/script/test/return_line_velocity_probe.py`: 删除旧回库黄线速度探针。
- `tests/unit/script/test_return_line_velocity_probe.py`: 删除旧回库黄线速度探针测试。

删除或改写的旧测试口径:

- 主车 `RETURN_GARAGE_RETREAT` 固定后退速度测试改为主车回库 Play 启动与接管测试。
- 主车 `RETURN_GARAGE_LINE` 组合固定左移和黄线速度测试删除黄线跟随断言, 改为 Play 接管测试。
- 辅车 `RETURN_FOLLOW` 组合固定左移和黄线速度测试改为辅车回库 Play 接管测试。
- 主辅回库完成事件进入停车完成态测试改为保持态不停车测试。
- 视觉仓库 v2 回库完成事件作为车端停车终点的测试改为黄线判据事件或观测测试。
- 视觉仓库 v2 回库黄线速度计算、速度发送和车端速度探针测试直接删除。

## Task 1: Play 播放器核心

**Files:**
- Create: `src/play/__init__.py`
- Create: `src/play/base.py`
- Create: `src/play/runner.py`
- Create: `tests/unit/play/__init__.py`
- Create: `tests/unit/play/test_runner.py`

- [ ] **Step 1: 写播放器失败测试**
  在 `tests/unit/play/test_runner.py` 中覆盖: 没有当前 Play 时接受请求; 已有当前 Play 时拒绝后续所有 Play 请求; `tick(ctx)` 推进当前 Play; Play 完成后释放; 保持态继续报告接管; 保持态不释放当前 Play, 后续 `run(...)` 继续被拒绝。

- [ ] **Step 2: 运行失败测试**
  Run: `uv run pytest tests/unit/play/test_runner.py -q`
  Expected: FAIL, 原因为 `src.play` 或 `PlayRunner` 尚未定义。

- [ ] **Step 3: 建立最小 Play 核心**
  在 `src/play/base.py` 中定义 Play 状态、步骤状态、播放结果和 `BasePlay`。在 `src/play/runner.py` 中定义 `run(play_class)` 启动行为和 `tick(ctx)` 推进行为。

- [ ] **Step 4: 验证播放器测试通过**
  Run: `uv run pytest tests/unit/play/test_runner.py -q`
  Expected: PASS。

- [ ] **Step 5: 检查命名边界**
  确认运行时调用侧准备使用字段名 `play`, 对外启动形态为 `play.run(...)`, 推进形态为 `play.tick(...)`, 不暴露播放器内部对象命名。

## Task 2: PlayContext、Step 和 `until` 回调

**Files:**
- Create: `src/play/context.py`
- Create: `src/play/steps.py`
- Create: `src/play/conditions.py`
- Create: `tests/unit/play/test_steps.py`
- Modify: `src/play/__init__.py`

- [ ] **Step 1: 写步骤失败测试**
  在 `tests/unit/play/test_steps.py` 中覆盖: 位置式 Y 步骤只下发一次; 角度步骤只下发一次; 速度式 Y 步骤每拍写固定速度; `until(ctx)` 回调返回真后速度式步骤完成; 保持速度步骤进入保持态并持续接管。

- [ ] **Step 2: 运行失败测试**
  Run: `uv run pytest tests/unit/play/test_steps.py -q`
  Expected: FAIL, 原因为步骤和上下文类尚未定义。

- [ ] **Step 3: 实现受限上下文**
  在 `src/play/context.py` 中定义只暴露位置目标、角度目标、固定速度、底盘完成查询和黄线判据查询的上下文。上下文不提供角色判断, 不暴露完整运行时对象。

- [ ] **Step 4: 实现步骤与回调**
  在 `src/play/steps.py` 中实现位置式步骤、速度式步骤和保持步骤。速度式步骤每拍调用 `until(ctx)` 回调函数判断是否完成。`until` 回调只读上下文, 不产生副作用。

- [ ] **Step 5: 验证步骤测试通过**
  Run: `uv run pytest tests/unit/play/test_steps.py -q`
  Expected: PASS。

## Task 3: 主车和辅车回库 Play

**Files:**
- Create: `src/play/routines/__init__.py`
- Create: `src/play/routines/master_return_garage.py`
- Create: `src/play/routines/assistant_return_garage.py`
- Create: `tests/unit/play/test_return_garage_play.py`
- Modify: `src/play/__init__.py`

- [ ] **Step 1: 写回库 Play 结构失败测试**
  在 `tests/unit/play/test_return_garage_play.py` 中覆盖: 主车步骤顺序为右转、直走等黄线、左转、向前保持; 辅车步骤顺序为固定前进、左转、直走等黄线、左转、向前保持; `AngleStep(+90)` 表示右转, `AngleStep(-90)` 表示左转; 主车和辅车直走速度为 5; 主车和辅车保持速度为 3; 辅车前置固定距离为 30cm 对应的 core 位置单位值; 回库流程参数为 Play 文件局部常量, 不依赖 `config` 模块; 直走步骤使用 `until(ctx)` 回调函数, 不使用固定标志位。

- [ ] **Step 2: 运行失败测试**
  Run: `uv run pytest tests/unit/play/test_return_garage_play.py -q`
  Expected: FAIL, 原因为回库 Play 类尚未定义。

- [ ] **Step 3: 实现主车回库 Play**
  在 `src/play/routines/master_return_garage.py` 中定义 `MasterReturnGaragePlay`。局部常量包含黄线前直走速度 5 和最终保持向前速度 3。步骤序列中直接表达右转 `+90` 和左转 `-90`。

- [ ] **Step 4: 实现辅车回库 Play**
  在 `src/play/routines/assistant_return_garage.py` 中定义 `AssistantReturnGaragePlay`。局部常量包含前置固定距离 30cm 对应的 core 位置单位值、黄线前直走速度 5 和最终保持向前速度 3。步骤序列中直接表达两次左转 `-90`。

- [ ] **Step 5: 验证回库 Play 测试通过**
  Run: `uv run pytest tests/unit/play/test_return_garage_play.py -q`
  Expected: PASS。

## Task 4: 视觉仓库 v2 回库黄线跟随下线

**Files:**
- Modify: `../SmartCar2026-Vision/master/main_v2.py`
- Modify: `../SmartCar2026-Vision/assistant/main_v2.py`
- Modify: `../SmartCar2026-Vision/tests/unit/test_master_main_v2.py`
- Modify: `../SmartCar2026-Vision/tests/unit/test_assistant_main_v2.py`
- Modify: `../SmartCar2026-Vision/tests/contract/test_main_v2_vision_protocol_contract.py`
- Delete: `src/script/test/return_line_velocity_probe.py`
- Delete: `tests/unit/script/test_return_line_velocity_probe.py`

- [ ] **Step 1: 写主车视觉失败测试**
  更新 `../SmartCar2026-Vision/tests/unit/test_master_main_v2.py`: 主车回库黄线只报告 `RETURN_LINE_ALIGNED` 判据; 判据沿用当前主车“后退到黄线”的完成条件; 不再测试回库黄线速度计算; 不再把回库完成事件作为车端停车终点。

- [ ] **Step 2: 写辅车视觉失败测试**
  更新 `../SmartCar2026-Vision/tests/unit/test_assistant_main_v2.py`: 辅车回库黄线只报告 `RETURN_LINE_ALIGNED` 判据; 事件编号为 10; 判据沿用当前主车“后退到黄线”的完成条件; 不再测试回库黄线速度计算; 不再把本地完成事件作为辅车停车终点。

- [ ] **Step 3: 运行视觉失败测试**
  Run: `uv --directory ../SmartCar2026-Vision run pytest tests/unit/test_master_main_v2.py tests/unit/test_assistant_main_v2.py tests/contract/test_main_v2_vision_protocol_contract.py -q`
  Expected: FAIL, 原因为视觉仓库仍保留回库黄线跟随速度或回库完成停车合同。

- [ ] **Step 4: 删除主车回库黄线跟随**
  在 `../SmartCar2026-Vision/master/main_v2.py` 中保留黄线位置识别和 `RETURN_LINE_ALIGNED` 判据事件, 删除回库黄线速度计算、速度发送和回库完成停车主流程。

- [ ] **Step 5: 删除辅车回库黄线跟随**
  在 `../SmartCar2026-Vision/assistant/main_v2.py` 中保留黄线位置识别, 新增或改用 `RETURN_LINE_ALIGNED=10` 作为黄线判据事件, 删除回库黄线速度计算、速度发送和本地完成停车主流程。

- [ ] **Step 6: 清理视觉协议合同**
  更新 `../SmartCar2026-Vision/tests/contract/test_main_v2_vision_protocol_contract.py`: v2 回库视觉合同只保留 `RETURN_LINE_ALIGNED=10` 黄线判据, 主车和辅车均使用该事件语义, 不声明黄线跟随速度或回库完成停车事件。

- [ ] **Step 7: 删除车端速度探针**
  删除车端仓库中的回库黄线速度探针脚本和测试。视觉仓库旧入口 `main.py` 不在本轮修改范围内。

- [ ] **Step 8: 验证视觉测试通过**
  Run: `uv --directory ../SmartCar2026-Vision run pytest tests/unit/test_master_main_v2.py tests/unit/test_assistant_main_v2.py tests/contract/test_main_v2_vision_protocol_contract.py -q`
  Expected: PASS。

- [ ] **Step 9: 检查黄线跟随残留**
  Run: `rg -n "build_return_line_velocity_from_y|RETURN_GARAGE_FINISHED|RETURN_LINE_MAX_VY|RETURN_LINE_KP_Y" ../SmartCar2026-Vision/master/main_v2.py ../SmartCar2026-Vision/assistant/main_v2.py ../SmartCar2026-Vision/tests/unit/test_master_main_v2.py ../SmartCar2026-Vision/tests/unit/test_assistant_main_v2.py ../SmartCar2026-Vision/tests/contract/test_main_v2_vision_protocol_contract.py src/script/test tests/unit/script`
  Expected: v2 入口、v2 测试和车端速度探针中不再出现回库黄线跟随速度和回库完成停车主流程残留。视觉仓库旧入口 `main.py` 的残留不在本轮检查范围内。

## Task 5: 主车状态机回库入口调整

**Files:**
- Modify: `src/vision/master/state_machine.py`
- Modify: `tests/unit/vision/test_master_state_machine.py`

- [ ] **Step 1: 写主车状态机失败测试**
  更新 `tests/unit/vision/test_master_state_machine.py`: 最后一轮清障后退和回身完成后进入主车回库 Play 状态; 发出辅车回库 Play 同步请求; 不再进入旧的回库黄线平移停车状态; 回库完成事件不再使主车进入完成停车。

- [ ] **Step 2: 运行失败测试**
  Run: `uv run pytest tests/unit/vision/test_master_state_machine.py -q`
  Expected: FAIL, 原因为状态机仍使用旧回库后退和平移状态。

- [ ] **Step 3: 调整主车回库状态语义**
  在 `src/vision/master/state_machine.py` 中把最终回库阶段收口为回库 Play 启动状态。保留主车全局任务主线和辅车同步职责, 不把 Play 步骤写入状态机。

- [ ] **Step 4: 移除旧事件跳转口径**
  主车状态机不再通过回库黄线对正事件进入旧黄线平移状态, 不再通过回库完成事件进入停车完成态。黄线事件只留给运行时 Play 条件缓存使用。

- [ ] **Step 5: 验证主车状态机测试通过**
  Run: `uv run pytest tests/unit/vision/test_master_state_machine.py -q`
  Expected: PASS。

## Task 6: 辅车状态机回库入口调整

**Files:**
- Modify: `src/vision/assistant/state_machine.py`
- Modify: `tests/unit/vision/test_assistant_state_machine.py`

- [ ] **Step 1: 写辅车状态机失败测试**
  更新 `tests/unit/vision/test_assistant_state_machine.py`: 辅车接受主车下发的回库 Play 状态; 回库 Play 状态不根据本地回库完成事件进入停车完成态; finished 同步仍可让辅车停车。

- [ ] **Step 2: 运行失败测试**
  Run: `uv run pytest tests/unit/vision/test_assistant_state_machine.py -q`
  Expected: FAIL, 原因为当前 `RETURN_FOLLOW` 仍消费本地完成事件进入 finished。

- [ ] **Step 3: 调整辅车回库状态语义**
  在 `src/vision/assistant/state_machine.py` 中将回库状态语义调整为回库 Play。该状态只表示等待运行时播放辅车回库 Play, 不承载视觉停车逻辑。

- [ ] **Step 4: 保留主车停止同步边界**
  确认 `ASSISTANT_STATE_FINISHED` 仍只由主车同步或明确停止入口触发, 不由回库 Play 的本地视觉事件触发。

- [ ] **Step 5: 验证辅车状态机测试通过**
  Run: `uv run pytest tests/unit/vision/test_assistant_state_machine.py -q`
  Expected: PASS。

## Task 7: 主车运行时接入 Play

**Files:**
- Modify: `src/vision/master/forward_runtime.py`
- Modify: `tests/unit/runtime/test_transport_runtime_surface.py`

- [ ] **Step 1: 写主车运行时失败测试**
  在 `tests/unit/runtime/test_transport_runtime_surface.py` 中新增或改写测试: 主车进入回库 Play 状态时调用 `play.run(MasterReturnGaragePlay)`; 后续每拍通过 `play.tick(ctx)` 推进; Play 活跃时普通速度输出被跳过; UART6 只提供黄线判据; 保持态持续固定向前。

- [ ] **Step 2: 运行相关失败测试**
  Run: `uv run pytest tests/unit/runtime/test_transport_runtime_surface.py -q`
  Expected: FAIL, 原因为主车运行时尚未持有 Play 播放器。

- [ ] **Step 3: 在主车运行时持有播放器**
  在 `MasterForwardRuntime.__init__` 中创建 `self.play`。字段名使用 `play`, 调用侧使用 `self.play.run(...)`。

- [ ] **Step 4: 构造主车 PlayContext**
  在主车运行时中为本拍构造受限上下文, 连接到底盘位置目标、角度目标、固定速度、底盘完成查询和主车黄线判据缓存。

- [ ] **Step 5: 接入主车回库 Play**
  在主车回库 Play 状态进入时调用 `self.play.run(MasterReturnGaragePlay)`。在后续周期调用 `self.play.tick(ctx)` 推进当前 Play。当 tick 返回 active 或 holding 时跳过普通状态速度输出。

- [ ] **Step 6: 只读取黄线判据**
  保留 UART6 事件读取和黄线判据缓存。运行时不消费回库黄线跟随速度, 历史或异常速度包也不得写入底盘。

- [ ] **Step 7: 验证主车运行时测试通过**
  Run: `uv run pytest tests/unit/runtime/test_transport_runtime_surface.py -q`
  Expected: PASS。

## Task 8: 辅车运行时接入 Play

**Files:**
- Modify: `src/vision/assistant/follow_runtime.py`
- Modify: `tests/unit/runtime/test_transport_runtime_surface.py`

- [ ] **Step 1: 写辅车运行时失败测试**
  在 `tests/unit/runtime/test_transport_runtime_surface.py` 中新增或改写测试: 辅车收到回库 Play 同步时调用 `play.run(AssistantReturnGaragePlay)`; 后续每拍通过 `play.tick(ctx)` 推进; Play 活跃时普通跟随速度被跳过; UART6 只提供黄线判据; 保持态持续固定向前。

- [ ] **Step 2: 运行相关失败测试**
  Run: `uv run pytest tests/unit/runtime/test_transport_runtime_surface.py -q`
  Expected: FAIL, 原因为辅车运行时仍使用旧回库跟随速度。

- [ ] **Step 3: 在辅车运行时持有播放器**
  在 `AssistantFollowRuntime.__init__` 中创建 `self.play`。字段名使用 `play`, 调用侧使用 `self.play.run(...)`。

- [ ] **Step 4: 构造辅车 PlayContext**
  在辅车运行时中为本拍构造受限上下文, 连接到底盘位置目标、角度目标、固定速度、底盘完成查询和辅车黄线判据缓存。

- [ ] **Step 5: 接入辅车回库 Play**
  在辅车回库 Play 状态进入时调用 `self.play.run(AssistantReturnGaragePlay)`。在后续周期调用 `self.play.tick(ctx)` 推进当前 Play。当 tick 返回 active 或 holding 时跳过普通跟随和回库速度输出。

- [ ] **Step 6: 只读取黄线判据**
  保留 UART6 事件读取和黄线判据缓存。运行时不消费回库黄线跟随速度, 历史或异常速度包也不得写入底盘, 不得用本地完成事件进入停车完成态。

- [ ] **Step 7: 验证辅车运行时测试通过**
  Run: `uv run pytest tests/unit/runtime/test_transport_runtime_surface.py -q`
  Expected: PASS。

## Task 9: 主辅联动与旧回库口径清理

**Files:**
- Modify: `tests/unit/runtime/test_dual_vehicle_communication_flow.py`
- Modify: `tests/unit/runtime/test_transport_runtime_surface.py`
- Modify: `src/vision/master/forward_runtime.py`
- Modify: `src/vision/assistant/follow_runtime.py`
- Review/Modify: `src/config/motion.py`

- [ ] **Step 1: 写联动失败测试**
  在 `tests/unit/runtime/test_dual_vehicle_communication_flow.py` 中覆盖: 主车最终回库时同步辅车进入回库 Play; 主车和辅车都由各自 Play 接管; 主车和辅车均不依赖回库完成停车事件。

- [ ] **Step 2: 运行联动失败测试**
  Run: `uv run pytest tests/unit/runtime/test_dual_vehicle_communication_flow.py -q`
  Expected: FAIL, 原因为联动仍按旧回库跟随口径执行。

- [ ] **Step 3: 清理旧速度常量引用**
  删除或停止使用旧回库固定后退、固定左移和辅车回库左移速度在回库主流程中的引用。若某个常量已无引用, 从 `src/config/motion.py` 删除。

- [ ] **Step 4: 清理旧测试断言**
  删除或改写仍断言回库固定左移、黄线速度混合、回库完成事件停车的测试。新的断言以 Play 接管和保持态为准。

- [ ] **Step 5: 验证联动测试通过**
  Run: `uv run pytest tests/unit/runtime/test_dual_vehicle_communication_flow.py tests/unit/runtime/test_transport_runtime_surface.py -q`
  Expected: PASS。

## Task 10: 文档必要性审查

**Files:**
- Review: `docs/developer/state.md`
- Review: `docs/developer/strategy.md`
- Review: `docs/developer/vision.md`

- [ ] **Step 1: 检查状态文档是否承担外部事实职责**
  阅读 `docs/developer/state.md`。如果回库 Play 的事实已经能从状态机常量、Play 类名、测试名和运行时调用看懂, 不修改该文档。

- [ ] **Step 2: 检查策略文档是否需要保留非代码决策**
  阅读 `docs/developer/strategy.md`。只有当“为什么选择固定回库动作链和向前保持”无法从代码和测试表达时, 才补充策略事实。

- [ ] **Step 3: 检查视觉文档是否存在错误外部口径**
  阅读 `docs/developer/vision.md`。只有当文档对外描述了错误事实, 例如“回库视觉黄线跟随速度”或“回库完成事件触发停车”, 才改为黄线条件输入口径。

- [ ] **Step 4: 跳过可由代码解释的文档改动**
  对所有准备写入文档的内容做筛选: 能通过文件名、类名、状态名、测试名或代码结构解释的内容不写文档。

- [ ] **Step 5: 文档规则自查**
  如确实修改文档, 检查新增内容不使用历史性口吻, 不写实现过程说明, 不复制代码细节。

## Task 11: 全量验证和收口

**Files:**
- Verify only.

- [ ] **Step 1: 运行 Play 测试**
  Run: `uv run pytest tests/unit/play -q`
  Expected: PASS。

- [ ] **Step 2: 运行视觉状态机测试**
  Run: `uv run pytest tests/unit/vision/test_master_state_machine.py tests/unit/vision/test_assistant_state_machine.py -q`
  Expected: PASS。

- [ ] **Step 3: 运行运行时测试**
  Run: `uv run pytest tests/unit/runtime/test_transport_runtime_surface.py tests/unit/runtime/test_dual_vehicle_communication_flow.py -q`
  Expected: PASS。

- [ ] **Step 4: 运行相关测试集合**
  Run: `uv run pytest tests/unit/play tests/unit/vision tests/unit/runtime -q`
  Expected: PASS。

- [ ] **Step 5: 运行视觉仓库测试**
  Run: `uv --directory ../SmartCar2026-Vision run pytest tests/unit/test_master_main_v2.py tests/unit/test_assistant_main_v2.py tests/contract/test_main_v2_vision_protocol_contract.py -q`
  Expected: PASS。

- [ ] **Step 6: 运行格式检查**
  Run: `git diff --check`
  Expected: no output。

- [ ] **Step 7: 运行视觉仓库格式检查**
  Run: `git -C ../SmartCar2026-Vision diff --check`
  Expected: no output。

- [ ] **Step 8: 检查未提交改动**
  Run: `git status --short`
  Expected: 只包含本计划执行产生的相关文件。

- [ ] **Step 9: 检查视觉仓库未提交改动**
  Run: `git -C ../SmartCar2026-Vision status --short`
  Expected: 只包含本计划执行产生的视觉仓库相关文件。

- [ ] **Step 10: 提交前确认**
  如需要 commit, 先向用户确认 commit 消息。commit 消息不添加 co-author 头。

## 自查清单

- [ ] Spec 中 `src/play/`、`play.run(...)`、`play.tick(...)`、局部常量、单 Play 拒绝规则均有任务覆盖。
- [ ] Plan 未在步骤中写实现代码。
- [ ] Plan 不要求使用字符串注册表。
- [ ] Plan 不引入 Play 抢占、队列、暂停和恢复。
- [ ] Plan 要求视觉仓库 v2 入口下掉回库黄线跟随速度。
- [ ] Plan 固定回库参数为直走速度 5、保持速度 3、辅车前进 30cm 对应的 core 位置单位值。
- [ ] Plan 固定黄线 ready 事件为 `RETURN_LINE_ALIGNED=10`, 主车和辅车 v2 使用同一判据语义。
- [ ] Plan 不把回库局部速度和距离常量默认放入 `config/`。
- [ ] Plan 保留主车状态机的全局任务主线和主辅同步职责。
