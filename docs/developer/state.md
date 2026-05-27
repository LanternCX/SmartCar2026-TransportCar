# 状态机说明

## 文档边界

本文件只维护状态机所有权和阅读入口。状态编号、事件编号、状态流、等待条件和跳转细节以状态机代码和行为测试为准。

## 所有权

- 主车全局状态机由 [src/vision/master/state_machine.py](../../src/vision/master/state_machine.py) 维护。
- 辅车子状态机由 [src/vision/assistant/state_machine.py](../../src/vision/assistant/state_machine.py) 维护。
- 协议层只解析和格式化短包字段，不维护业务状态机。
- 视觉端只提供速度控制量和事件，不维护车端全局状态机。
- 辅车子状态由主车同步包驱动，不由辅车本地视觉包、速度包或底盘状态自行切换。

## 代码阅读顺序

1. 主车状态编号、目标编号、事件编号和状态跳转: [src/vision/master/state_machine.py](../../src/vision/master/state_machine.py)
2. 辅车子状态编号、目标编号和主车同步应用: [src/vision/assistant/state_machine.py](../../src/vision/assistant/state_machine.py)
3. 搬运收尾阶段编号: [src/vision/clear_phase.py](../../src/vision/clear_phase.py)
4. 主车状态机接入运行时的位置: [src/vision/master/forward_runtime.py](../../src/vision/master/forward_runtime.py)
5. 辅车状态机接入运行时的位置: [src/vision/assistant/follow_runtime.py](../../src/vision/assistant/follow_runtime.py)

## 行为事实入口

- 主车纯状态机行为: [tests/unit/vision/test_master_state_machine.py](../../tests/unit/vision/test_master_state_machine.py)
- 辅车纯状态机行为: [tests/unit/vision/test_assistant_state_machine.py](../../tests/unit/vision/test_assistant_state_machine.py)
- 主车运行时状态接入: [tests/unit/runtime/test_master_forward_runtime.py](../../tests/unit/runtime/test_master_forward_runtime.py)
- 辅车运行时状态接入: [tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py](../../tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py)

## 变更入口

改状态编号、事件编号或状态顺序时，优先改状态机代码和行为测试，再按需要更新本页入口说明。需要理解某次状态机调整的背景时查 [docs/superpowers/memory/milestone/INDEX.md](../superpowers/memory/milestone/INDEX.md) 与 [docs/superpowers/memory/debug/INDEX.md](../superpowers/memory/debug/INDEX.md)。
