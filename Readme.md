# 2025 智能车蚂蚁搬家组 - 搬运车模代码

## 项目概述

这是一个基于 RT1021 微控制器的全向轮搬运车控制系统。车模支持通过串口消息在 `x`、`y`、`w` 三个自由度上进行速度模式和位置模式的灵活控制，具备完整的电机参数辨识、陀螺仪校准、多层滤波和级联 PID 控制的控制框架。

## 仓库定位

本仓库用于维护搬运车模的控制代码，以及面向开发者的总体方案、电控设计、视觉设计、串口协议和状态机文档。

## 附属仓库

- OpenART 视觉仓库位于 `../SmartCar2026-Vision`。
- 视觉仓库只维护 OpenART 运行时代码、协议行为测试、回归测试和必要说明。
- 项目规则、题面材料、协作文档和长期开发文档以本仓库为准。
- 视觉仓库验证命令: `cd ../SmartCar2026-Vision && python3 -m pytest tests/unit tests/contract -q`。

## 开发者文档

- [总体方案](docs/developer/strategy.md)
- [电控设计](docs/developer/control.md)
- [串口协议](docs/developer/protocol.md)
- [状态机定义](docs/developer/state.md)
- [视觉设计](docs/developer/vision.md)
