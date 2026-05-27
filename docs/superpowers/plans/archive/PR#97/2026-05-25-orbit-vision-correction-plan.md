# 绕行视觉修正实施计划

> 执行状态: Archive
>
> 面向执行代理: 执行本计划时使用 `superpowers:subagent-driven-development`, 按任务逐项实现, 使用复选框跟踪状态。

**目标:** 让主车和辅车绕行阶段都能使用本车 OpenART 输出的目标物体 `X/Y` 平移修正稳定绕行半径。

**架构:** OpenART 视觉仓库新增主车和辅车绕行修正模式, 继续输出 `v,<vx>,<vy>`。车端主车和辅车在绕行阶段保持共享底盘统一绕行模式为基准运动, 并把 `UART6` 视觉平移修正单独解算为三轮修正目标后叠加到底盘三轮目标速度, 角速度和完成判据仍由共享底盘控制。

**技术栈:** MicroPython, OpenART, RT1021, `uv`, `pytest`, 仓库现有 `src/vision/*` 角色运行入口和 `../SmartCar2026-Vision/*/main.py` 视觉入口。

---

## 范围检查

本任务跨两个仓库, 但目标是同一个闭环能力: 绕行阶段接入目标物体视觉修正。任务可以拆成视觉侧模式、车端主车融合、车端辅车融合、文档与验证四个阶段, 每个阶段都能独立测试。

## 文件结构

计划修改文件:

- `../SmartCar2026-Vision/master/main.py`: 增加主车绕行修正模式、同步识别和速度输出。
- `../SmartCar2026-Vision/assistant/main.py`: 增加辅车绕行修正模式、同步识别和速度输出。
- `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`: 增加主车绕行视觉模式行为测试。
- `../SmartCar2026-Vision/tests/unit/test_assistant_object_approach.py`: 增加辅车绕行视觉模式行为测试。
- `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`: 视协议覆盖缺口补充绕行同步合同测试。
- `src/config/vision.py`: 增加车端下发给本车 OpenART 的绕行视觉配置编号。
- `src/vision/master/forward_runtime.py`: 主车绕行阶段下发本地视觉同步, 读取并叠加 `UART6` 修正。
- `src/vision/assistant/follow_runtime.py`: 辅车绕行阶段下发本地视觉同步, 读取并叠加 `UART6` 修正。
- `tests/unit/runtime/test_master_forward_runtime.py`: 增加主车绕行视觉同步和叠加测试。
- `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`: 增加辅车绕行视觉同步和叠加测试。
- `docs/developer/vision.md`: 同步视觉职责说明。
- `docs/developer/control.md`: 同步控制链路说明。

## 任务 1: 主车 OpenART 绕行修正模式

**Files:**

- Modify: `../SmartCar2026-Vision/master/main.py`
- Test: `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`

- [ ] Step 1: 阅读主车视觉入口中同步包、目标点、速度计算和事件回报相关函数, 标记绕行模式可独立配置的目标识别与速度计算边界。
- [ ] Step 2: 新增失败测试: 主车视觉收到绕行配置同步后回复 ACK, 并进入绕行修正模式。
- [ ] Step 3: 使用 `uv run pytest tests/unit/test_master_hook_protocol.py -q` 在视觉仓库验证该测试失败, 失败原因应为绕行配置未被识别或模式不存在。
- [ ] Step 4: 实现主车绕行修正模式的最小同步识别, 使用新的绕行配置编号。
- [ ] Step 5: 运行同一测试, 确认通过。
- [ ] Step 6: 新增失败测试: 主车绕行修正模式有红色目标时输出 `v,<vx>,<vy>`, 且速度计算使用独立绕行参数。
- [ ] Step 7: 验证失败原因来自绕行模式未输出速度。
- [ ] Step 8: 实现主车绕行修正速度输出。
- [ ] Step 9: 新增失败测试: 主车绕行修正模式无目标时输出 `v,0,0`。
- [ ] Step 10: 实现无目标归零输出。
- [ ] Step 11: 新增失败测试: 主车绕行修正模式不产生可靠完成事件。
- [ ] Step 12: 实现或调整事件边界, 保证绕行修正模式只输出速度。
- [ ] Step 13: 运行 `uv run pytest tests/unit/test_master_hook_protocol.py -q`。

## 任务 2: 辅车 OpenART 绕行修正模式

**Files:**

- Modify: `../SmartCar2026-Vision/assistant/main.py`
- Test: `../SmartCar2026-Vision/tests/unit/test_assistant_object_approach.py`

- [ ] Step 1: 阅读辅车视觉入口中 follow、approach object、同步 ACK、事件回报和速度输出相关函数。
- [ ] Step 2: 新增失败测试: 辅车视觉收到绕行配置同步后回复 ACK, 并进入绕行修正模式。
- [ ] Step 3: 使用 `uv run pytest tests/unit/test_assistant_object_approach.py -q` 在视觉仓库验证该测试失败。
- [ ] Step 4: 实现辅车绕行修正模式的最小同步识别, 使用新的绕行配置编号。
- [ ] Step 5: 运行同一测试, 确认通过。
- [ ] Step 6: 新增失败测试: 辅车绕行修正模式有红色目标时输出 `v,<vx>,<vy>`, 且速度计算使用独立绕行参数。
- [ ] Step 7: 验证失败原因来自绕行模式未输出速度。
- [ ] Step 8: 实现辅车绕行修正速度输出。
- [ ] Step 9: 新增失败测试: 辅车绕行修正模式无目标时输出 `v,0,0`。
- [ ] Step 10: 实现无目标归零输出。
- [ ] Step 11: 新增失败测试: 辅车绕行修正模式不产生 `TARGET_FOUND` 或 `ALIGNED` 事件。
- [ ] Step 12: 实现或调整事件边界。
- [ ] Step 13: 运行 `uv run pytest tests/unit/test_assistant_object_approach.py -q`。

## 任务 3: 视觉协议合同补充

**Files:**

- Modify: `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`

- [ ] Step 1: 阅读当前合同测试覆盖的短包格式、同步包和输出帧。
- [ ] Step 2: 增加主车绕行同步编号的合同测试, 确认仍使用可靠 ACK 和 `v,<vx>,<vy>` 数据流。
- [ ] Step 3: 增加辅车绕行同步编号的合同测试, 确认仍使用可靠 ACK 和 `v,<vx>,<vy>` 数据流。
- [ ] Step 4: 使用 `uv run pytest tests/contract/test_main_vision_protocol_contract.py -q` 验证失败。
- [ ] Step 5: 根据 Task 1 和 Task 2 的实现补齐合同覆盖。
- [ ] Step 6: 运行视觉仓库完整测试: `uv run pytest tests -q`。

## 任务 4: 车端配置编号

**Files:**

- Modify: `src/config/vision.py`
- Test: `tests/unit/runtime/test_master_forward_runtime.py`, `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`

- [ ] Step 1: 在车端配置中新增主车本地绕行视觉配置编号和辅车本地绕行视觉配置编号。
- [ ] Step 2: 保持编号语义与视觉仓库一致。
- [ ] Step 3: 在后续车端测试中动态读取配置值, 不在断言中写死编号。

## 任务 5: 主车绕行阶段下发视觉同步

**Files:**

- Modify: `src/vision/master/forward_runtime.py`
- Test: `tests/unit/runtime/test_master_forward_runtime.py`

- [ ] Step 1: 阅读主车运行时 `_drain_state_machine_outputs`、`_send_pending_hook`、`_handle_uart6_line` 和绕行命令激活流程。
- [ ] Step 2: 新增失败测试: 主车进入 `ORBITING` 时向本车 `UART6` 下发绕行视觉同步。
- [ ] Step 3: 使用 `uv run pytest tests/unit/runtime/test_master_forward_runtime.py -q` 验证该测试失败。
- [ ] Step 4: 实现主车绕行本地视觉同步请求, 复用现有可靠同步发送边界。
- [ ] Step 5: 运行该测试, 确认通过。
- [ ] Step 6: 新增失败测试: 主车绕行结束后清空绕行视觉速度缓存, 并由后续状态重新建立视觉上下文。
- [ ] Step 7: 实现绕行状态退出时的缓存清理。
- [ ] Step 8: 运行主车运行时测试文件。

## 任务 6: 主车绕行阶段叠加视觉修正

**Files:**

- Modify: `src/vision/master/forward_runtime.py`
- Test: `tests/unit/runtime/test_master_forward_runtime.py`

- [ ] Step 1: 确认共享底盘统一绕行模式能暴露或保留当前绕行基准速度目标。
- [ ] Step 2: 新增失败测试: 主车 `ORBITING` 中收到合法 `UART6` 速度后, 最终底盘三轮目标包含绕行基准目标与视觉修正目标。
- [ ] Step 3: 验证测试失败, 失败原因应为 `UART6` 速度在绕行阶段未生效。
- [ ] Step 4: 在主车绕行周期中加入视觉平移修正三轮目标叠加, 保持角速度和完成判据不变。
- [ ] Step 5: 新增失败测试: 主车 `ORBITING` 中合法 `UART3` 速度不会覆盖绕行控制。
- [ ] Step 6: 确认现有屏蔽逻辑仍成立。
- [ ] Step 7: 新增失败测试: `v,0,0` 会把主车绕行视觉修正归零。
- [ ] Step 8: 实现显式零包归零行为。
- [ ] Step 9: 运行主车运行时测试文件。

## 任务 7: 辅车绕行阶段下发视觉同步

**Files:**

- Modify: `src/vision/assistant/follow_runtime.py`
- Test: `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`

- [ ] Step 1: 阅读辅车运行时 `_apply_sync_context`、`_enter_orbit_state`、`_send_pending_local_vision_sync` 和 `UART6` 输入消费流程。
- [ ] Step 2: 新增失败测试: 辅车进入 `ASSISTANT_ORBIT` 后向本车 OpenART 下发绕行视觉同步。
- [ ] Step 3: 使用 `uv run pytest tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py -q` 验证该测试失败。
- [ ] Step 4: 实现辅车绕行本地视觉同步请求。
- [ ] Step 5: 运行该测试, 确认通过。
- [ ] Step 6: 新增失败测试: 辅车离开 `ASSISTANT_ORBIT` 时清空绕行视觉速度缓存。
- [ ] Step 7: 实现缓存清理。
- [ ] Step 8: 运行辅车运行时速度流测试文件。

## 任务 8: 辅车绕行阶段叠加视觉修正

**Files:**

- Modify: `src/vision/assistant/follow_runtime.py`
- Test: `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`

- [ ] Step 1: 新增失败测试: 辅车 `ASSISTANT_ORBIT` 中收到合法 `UART6` 速度后, 最终底盘三轮目标包含绕行基准目标与视觉修正目标。
- [ ] Step 2: 验证测试失败, 失败原因应为 `ASSISTANT_ORBIT` 中直接跳过有效速度写入。
- [ ] Step 3: 在辅车绕行周期中加入视觉平移修正三轮目标叠加, 保持角速度和完成判据不变。
- [ ] Step 4: 新增失败测试: 辅车 `ASSISTANT_ORBIT` 中 `UART8` 前馈速度不会参与最终速度。
- [ ] Step 5: 确认绕行期间只使用本地 `UART6` 视觉修正。
- [ ] Step 6: 新增失败测试: `v,0,0` 会把辅车绕行视觉修正归零。
- [ ] Step 7: 实现显式零包归零行为。
- [ ] Step 8: 运行辅车运行时速度流测试文件。

## 任务 9: 文档同步

**Files:**

- Modify: `docs/developer/vision.md`
- Modify: `docs/developer/control.md`

- [ ] Step 1: 在 `docs/developer/vision.md` 中补充主车和辅车绕行视觉修正模式职责。
- [ ] Step 2: 在 `docs/developer/control.md` 中补充绕行阶段的速度叠加口径。
- [ ] Step 3: 检查文档只描述当前事实, 不写历史性口吻。
- [ ] Step 4: 检查新增注释和文档字符串均为中文。

## 任务 10: 全量验证与板端检查准备

**Files:**

- Verify: 主仓库测试与视觉仓库测试

- [ ] Step 1: 在主仓库运行 `uv run pytest tests/unit tests/contract -q`。
- [ ] Step 2: 在视觉仓库运行 `uv run pytest tests -q`。
- [ ] Step 3: 记录主车板端检查步骤: 绕行阶段目标偏左、偏右、偏近、偏远时观察修正方向。
- [ ] Step 4: 记录辅车板端检查步骤: 绕行阶段目标偏左、偏右、偏近、偏远时观察修正方向。
- [ ] Step 5: 记录绕行完成检查: 目标角度达到后命令锁释放, 状态机继续推进。
- [ ] Step 6: 完成前使用 `project-extension-requesting-code-review` 做收口评审。

## 完成标准

- 主车和辅车 OpenART 都支持绕行视觉修正模式。
- 主车和辅车车端绕行阶段都能把 `UART6` 视觉 `X/Y` 修正叠加到底盘三轮目标速度。
- 视觉修正不改变绕行角度目标、半径倍率、角速度来源和完成判据。
- 两个仓库相关测试通过。
- 开发文档同步更新。
- 板端验证步骤明确, 能用于后续实车确认。
