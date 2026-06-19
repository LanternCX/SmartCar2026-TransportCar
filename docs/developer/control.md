# 电控与运行入口

## 文档边界

本文件只维护代码外的运行约定和阅读入口。控制流程、状态切换、参数值和模式细节以代码、注释和行为测试为准。

## 外部约定

- 正式入口是 [src/main.py](../../src/main.py)，不按按钮进入 [src/script/remote_control.py](../../src/script/remote_control.py)。
- 长按 `C14` 上电进入参数辨识脚本，长按 `C15` 上电进入陀螺仪校准脚本。
- `src/config/startup.py` 开启测试模式时，不按按钮进入 [src/script/test.py](../../src/script/test.py)。
- 主车和辅车身份由车号读取结果决定，不由启动按钮决定。
- 主车使用旧硬件接线映射，辅车使用新硬件接线映射，底盘控制内核保持统一。
- 上电低压保护按车辆身份选择阈值: 主车 `11.5V`，辅车 `3.7V`。
- `UART3` 用作 REPL 与现场调试链路，`UART8` 用作主辅直连链路，两台车各自用本车 `UART6` 连接本车 OpenART。
- 陀螺仪零飘结果保存到 `/flash/gyro_offset.txt`，电机辨识结果保存到 `/flash/ident_params.txt`。

## 代码阅读顺序

1. 入口分发: [src/main.py](../../src/main.py)
2. 正式控制循环: [src/script/remote_control.py](../../src/script/remote_control.py)
3. 板端测试入口: [src/script/test.py](../../src/script/test.py)
4. 角色选择: [src/vision/vehicle_role.py](../../src/vision/vehicle_role.py)
5. 共享底盘执行内核: [src/core/runtime.py](../../src/core/runtime.py)
6. 主车角色运行时: [src/vision/master/forward_runtime.py](../../src/vision/master/forward_runtime.py)
7. 辅车角色运行时: [src/vision/assistant/follow_runtime.py](../../src/vision/assistant/follow_runtime.py)
8. 运动、通信、视觉、安全和存储参数: [src/config/](../../src/config/)

## 行为事实入口

- 入口与角色分发: [tests/unit/entry/](../../tests/unit/entry/)
- 共享底盘行为: [tests/unit/core/](../../tests/unit/core/)
- 主辅运行时行为: [tests/unit/runtime/](../../tests/unit/runtime/)
- 串口协议契约: [tests/contract/serial_protocol/](../../tests/contract/serial_protocol/)

## 追溯入口

- 控制和运行时调试结论优先查 [docs/superpowers/memory/debug/INDEX.md](../superpowers/memory/debug/INDEX.md)。
- 架构和边界调整优先查 [docs/superpowers/memory/refactor/INDEX.md](../superpowers/memory/refactor/INDEX.md)。
- 完整能力闭环优先查 [docs/superpowers/memory/milestone/INDEX.md](../superpowers/memory/milestone/INDEX.md)。
