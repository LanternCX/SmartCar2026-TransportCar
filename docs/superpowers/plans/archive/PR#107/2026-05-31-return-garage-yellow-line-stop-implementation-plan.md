# 主车回库黄线停车实现计划

执行状态: Archive

> 给 Agent 工作者: 使用 `superpowers:subagent-driven-development` 按任务逐项实现。每个任务完成后由主线程 review diff、运行对应验证命令, 再进入下一个任务。

## 目标

按 `docs/superpowers/specs/archive/PR#107/2026-05-31-return-garage-yellow-line-stop-design.md` 取消回库色标状态, 让主车只通过回库黄线完成横移入库和停车。

## 架构边界

主车全局状态机仍由 `src/vision/master/state_machine.py` 维护。主车运行时复用现有 hook 同步、ACK、可靠事件、辅车同步和速度前馈链路, 不新增通信机制。

主车 OpenART 只保留回库黄线配置作为回库视觉主线。黄线配置在后退段负责对正事件, 在平移段负责固定参考 Y 和丢线完成事件。

## 文件结构

- 修改: `src/vision/master/state_machine.py`  
  取消回库色标状态主线, 让回库黄线平移收到完成事件后进入完成态。
- 修改: `src/vision/master/forward_runtime.py`  
  取消回库色标 hook 下发和色标状态速度消费, 保留黄线平移和完成同步。
- 修改: `src/vision/assistant/state_machine.py`  
  保留辅车回库跟随和完成同步语义, 不新增色标相关行为。
- 修改: `src/vision/assistant/follow_runtime.py`  
  保持辅车回库跟随等同普通跟随, 完成同步后停止。
- 修改: `tests/unit/vision/test_master_state_machine.py`  
  调整主车回库状态机测试, 覆盖黄线平移直接完成。
- 修改: `tests/unit/runtime/test_transport_runtime_surface.py` 或现有回库运行时测试文件  
  覆盖主车回库平移、完成事件、停车和辅车完成同步。
- 修改: `../SmartCar2026-Vision/master/main.py`  
  取消回库色标主流程, 增加黄线控制值固定参考和丢线完成事件。
- 修改: `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`  
  覆盖黄线固定参考、丢线完成和回库色标退出主流程。
- 修改: `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`  
  调整回库事件契约, 确认回库黄线配置承担完成事件。
- 视实现结果修改: `docs/developer/state.md`
- 视实现结果修改: `docs/developer/vision.md`
- 视实现结果修改: `../SmartCar2026-Vision/README.md`

## 任务拆分

### 任务 1: 主车状态机取消回库色标主线

**修改范围:**

- `src/vision/master/state_machine.py`
- `tests/unit/vision/test_master_state_machine.py`

**任务目标:**

- 取消主流程中的 `RETURN_GARAGE_MARKER` 跳转。
- `RETURN_GARAGE_LINE` 收到回库完成事件后直接进入 `FINISHED`。
- 回库色标发现事件不触发状态切换。
- 非本轮上下文事件不能改变回库状态。

**测试要求:**

- 先写失败测试覆盖黄线平移直接完成。
- 先写失败测试覆盖回库色标发现事件不改变状态。
- 保留全部物体完成后进入回库后退、黄线对正后进入黄线平移的测试。

**验证命令:**

- `uv run --group test python -m pytest tests/unit/vision/test_master_state_machine.py -q`

**完成判据:**

- 主车状态机不依赖回库色标状态完成回库。
- 主车状态机相关测试通过。

### 任务 2: 主车运行时取消回库色标 hook 和速度消费

**修改范围:**

- `src/vision/master/forward_runtime.py`
- `tests/unit/runtime/test_transport_runtime_surface.py` 或现有回库运行时测试文件

**任务目标:**

- 不下发回库色标 hook。
- 回库黄线平移只组合固定左移速度和黄线纵向速度。
- 回库完成事件到达后写入零速度。
- 完成态停止消费本车视觉速度。
- 完成态向辅车发送完成同步。

**测试要求:**

- 先写失败测试覆盖回库黄线平移收到完成事件后停车。
- 先写失败测试覆盖没有回库色标 hook 下发。
- 保留回库阶段向辅车发送速度前馈的测试。

**验证命令:**

- `uv run --group test python -m pytest tests/unit/runtime -q`

**完成判据:**

- 主车运行时回库流程不依赖色标 hook。
- 主车运行时相关测试通过。

### 任务 3: 主车 OpenART 固定黄线控制参考

**修改范围:**

- `../SmartCar2026-Vision/master/main.py`
- `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`

**任务目标:**

- 回库黄线平移状态中, 原始黄线 Y 大于目标 Y 时使用原始 Y。
- 回库黄线平移状态中, 原始黄线 Y 小于或等于目标 Y 时使用目标 Y。
- 该规则只作用于黄线平移控制, 不破坏后退段黄线对正判定。
- 无有效黄线时输出零速度。

**测试要求:**

- 先写失败测试覆盖原始 Y 大于目标 Y 时输出后退修正。
- 先写失败测试覆盖原始 Y 小于或等于目标 Y 时输出零修正。
- 先写失败测试覆盖后退段仍按原始黄线 Y 触发对正。

**验证命令:**

- 在 `../SmartCar2026-Vision` 下运行 `uv run --with pytest python -m pytest tests/unit/test_master_hook_protocol.py -q`

**完成判据:**

- 黄线长边线导致原始 Y 偏小时, 控制值固定在目标 Y。
- 视觉单元测试通过。

### 任务 4: 主车 OpenART 丢线完成事件

**修改范围:**

- `../SmartCar2026-Vision/master/main.py`
- `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`
- `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`

**任务目标:**

- `RETURN_GARAGE_LINE` 的回库黄线配置在无有效黄线时回报回库完成事件。
- 无有效黄线时速度输出为零。
- 回库后退状态无有效黄线时不回报完成事件。
- 回库完成事件通过现有可靠事件链路发送。
- 取消或停用回库色标发现和色标完成主流程。

**测试要求:**

- 先写失败测试覆盖黄线平移丢线回报完成。
- 先写失败测试覆盖后退段丢线不回报完成。
- 先写失败测试覆盖回库完成事件的协议契约。

**验证命令:**

- 在 `../SmartCar2026-Vision` 下运行 `uv run --with pytest python -m pytest tests/unit/test_master_hook_protocol.py tests/contract/test_main_vision_protocol_contract.py -q`

**完成判据:**

- 黄线平移丢线能可靠触发回库完成。
- 视觉仓库相关测试通过。

### 任务 5: 辅车完成同步回归

**修改范围:**

- `src/vision/assistant/state_machine.py`
- `src/vision/assistant/follow_runtime.py`
- `tests/unit/vision/test_assistant_state_machine.py`
- `tests/unit/runtime/test_transport_runtime_surface.py` 或现有辅车运行时测试文件

**任务目标:**

- 辅车回库跟随继续等同普通跟随。
- 辅车只在主车完成同步后停止。
- 取消主车色标状态时, 辅车完成同步链路仍然有效。

**测试要求:**

- 保留或补齐辅车完成同步后清空输入并停止的测试。
- 保留或补齐辅车回库跟随不改变速度融合行为的测试。

**验证命令:**

- `uv run --group test python -m pytest tests/unit/vision/test_assistant_state_machine.py tests/unit/runtime -q`

**完成判据:**

- 辅车不参与回库完成判定。
- 辅车相关测试通过。

### 任务 6: 文档收口与双仓回归

**修改范围:**

- `docs/developer/state.md`
- `docs/developer/vision.md`
- `../SmartCar2026-Vision/README.md`
- `docs/superpowers/specs/archive/PR#107/2026-05-31-return-garage-yellow-line-stop-design.md`
- `docs/superpowers/plans/archive/PR#107/2026-05-31-return-garage-yellow-line-stop-implementation-plan.md`

**任务目标:**

- 只在正式文档中同步本轮事实和阅读入口。
- 不保留回库色标作为回库主流程说明。
- 将本 Spec 与 Plan 状态更新为 `Archive`。
- 完成主车仓库和视觉仓库相关测试。

**验证命令:**

- 主车仓库: `uv run --group test python -m pytest tests/unit/vision tests/unit/runtime -q`
- 视觉仓库: 在 `../SmartCar2026-Vision` 下运行 `uv run --with pytest python -m pytest tests/unit tests/contract -q`

**完成判据:**

- 双仓相关测试通过。
- 文档不使用历史性口吻。
- Spec 与 Plan 归档。

## 执行顺序

1. 先执行任务 1, 固定主车状态机的新回库主线。
2. 再执行任务 2, 取消主车运行时色标 hook 和色标速度消费。
3. 再执行任务 3, 调整 OpenART 黄线控制参考。
4. 再执行任务 4, 接入 OpenART 黄线丢线完成事件。
5. 再执行任务 5, 回归辅车完成同步。
6. 最后执行任务 6, 同步文档并完成双仓回归。

## Review 门禁

- 不新增窗口滤波。
- 不维护跳变次数。
- 不新增跳变阈值。
- 不通过高频速度包传业务阶段或完成标志。
- 不新增第二套 ACK、重发或去重机制。
- 不让辅车参与回库完成判定。
- 不保留回库色标状态作为主流程。
- 不为了本次回库改动扩大找物体、绕行、搬运和搬运收尾范围。
