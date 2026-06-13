# 视觉职责

## 文档边界

本文件只维护本仓库和 OpenART 视觉仓库之间的职责边界。具体识别算法、参数、状态编号、速度输出和可靠事件格式以对应仓库代码与测试为准。

## 仓库边界

- 本仓库维护 RT1021 车端角色运行、底盘执行、主辅通信和本地视觉链路接入。
- OpenART 视觉仓库位于 `../SmartCar2026-Vision`，维护 OpenART 端识别、速度计算、task 同步确认和事件回报。
- 视觉仓库不维护车端全局状态机。
- 本仓库不实现红色目标、色标或边线的图像识别算法，只消费视觉侧输出的速度和事件。

## 外部职责

- 主车 OpenART 负责目标物体识别、主车搜索速度、搬运入口对正、搬运结束判定、绕行视觉修正和回库黄线停车判定。
- 辅车 OpenART 负责主车色标跟随、辅车找物体、辅车搬运入口对正、辅车绕行视觉修正和辅车自主回库黄线巡线。
- 主车 RT1021 负责本车 `UART6` 视觉 task 编排、主车视觉速度接入、主车状态机调度和 `UART8` 主辅同步。
- 辅车 RT1021 负责 `UART8` 前馈输入、`UART8` 子状态同步、本车 `UART6` 视觉任务同步、本车 `UART6` 视觉输入和共享底盘写回。
- 辅车搬运态丢弃 `UART8` 的 x 前馈, 使用 `UART8` 的 y 前馈完成头对头方向换算, 并叠加本车 `UART6` 视觉修正。

## 代码阅读顺序

1. 角色入口分发: [src/vision/__init__.py](../../src/vision/__init__.py)
2. 车辆角色识别: [src/vision/vehicle_role.py](../../src/vision/vehicle_role.py)
3. 主车角色运行时: [src/vision/master/forward_runtime.py](../../src/vision/master/forward_runtime.py)
4. 主车状态机: [src/vision/master/state_machine.py](../../src/vision/master/state_machine.py)
5. 辅车角色运行时: [src/vision/assistant/follow_runtime.py](../../src/vision/assistant/follow_runtime.py)
6. 辅车状态机: [src/vision/assistant/state_machine.py](../../src/vision/assistant/state_machine.py)
7. 视觉相关配置: [src/config/vision.py](../../src/config/vision.py)

## 主车全局状态

主车状态机共定义 9 个状态。当前实际参与主流程的状态为：

- `IDLE` (0) → `SEARCH_OBJECT` (1) → `ORBITING` (2) → `SEARCH_OBJECT` (1) → `TRANSPORT_OBJECT` (4) → `CLEAR_OBJECT` (5)
- 全部物体搬运完成后：`CLEAR_OBJECT` (5) → `RETURN_GARAGE_RETREAT` (6) → `RETURN_GARAGE_LINE` (7) → `FINISHED` (8)

`STATE_STOP` (3) 停车状态虽然在状态机中有编号定义并在运行时 `assistant_idle` 处理分支中预留了不同 `stop_source` 语义，但状态机没有任何路径通过 `_enter_state` 进入该状态，因此当前不参与主流程。未启用的原因是基于视觉固定列采样的停车判定算法在场地上不够稳定。待算法稳定后可直接把回库完成后的 `FINISHED` 路径替换为进入 `STOP` 收尾链路。

## 行为事实入口

- 主车运行时视觉链路: [tests/unit/runtime/test_master_forward_runtime.py](../../tests/unit/runtime/test_master_forward_runtime.py)
- 辅车运行时视觉链路: [tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py](../../tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py)
- 角色入口分发: [tests/unit/runtime/test_role_vision_layer_factory.py](../../tests/unit/runtime/test_role_vision_layer_factory.py)
- 视觉状态机行为: [tests/unit/vision/](../../tests/unit/vision/)
- 视觉协议契约: [tests/contract/serial_protocol/](../../tests/contract/serial_protocol/)

## 追溯入口

- 视觉链路设计闭环优先查 [docs/superpowers/memory/milestone/INDEX.md](../superpowers/memory/milestone/INDEX.md)。
- 视觉联调和故障收敛优先查 [docs/superpowers/memory/debug/INDEX.md](../superpowers/memory/debug/INDEX.md)。
