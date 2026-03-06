---
name: hardware-integration
description: Use when adding or debugging hardware drivers, peripheral communication, and real-time constraints on RT1021 MicroPython.
---

# Overview
规范硬件驱动开发与联调流程，确保外设通信稳定、控制周期可控、故障可定位。

# When to Use
- 新增或改造 UART、PWM、电机、编码器、IMU、定时器相关代码
- 出现串口冲突、方向异常、读数跳变、时序抖动等硬件问题
- 需要评估 5ms 控制周期预算是否被破坏

# Platform Baseline
- MCU：RT1021
- Runtime：MicroPython
- 控制周期：5ms（200Hz）
- 约束：主循环和中断路径禁止阻塞

# Driver Rules
- 每个外设一个独立模块，接口最小化（初始化、读写、关闭）
- 驱动层不夹带业务逻辑，业务编排放 `services/`
- 读写接口要包含边界检查与失败路径
- 串口处理默认非阻塞，避免等待式读取
- PWM、方向切换与占空比限幅要原子化处理

# Real-Time Rules
- 中断回调只置标志，不执行重计算或 I/O
- 关键路径避免动态分配和大字符串操作
- 新增逻辑必须给出耗时评估（建议用 `ticks_us` 量测）
- 若控制周期超预算，先降复杂度再讨论新特性

# Integration Checklist
- UART3/UART6 波特率与收发方向配置一致
- 电机方向、编码器方向与运动学坐标系一致
- IMU 设备 ID 校验通过，零漂校准文件可用
- 控制循环在目标场景下保持稳定 5ms 周期

# Common Fix Patterns
- 编码器跳变：增强滤波、检查走线与电机干扰
- 电机反转/不转：核对引脚映射、PWM 频率、电源余量
- 串口乱码：统一波特率、清理缓冲区、规避总线冲突
- 周期抖动：缩短中断逻辑，挪走阻塞式调用

# Git Policy
- 分支和提交规范只使用 `.agents/skills/git-workflow/SKILL.md`
- 不要使用 superpowers 自带的 git workflow 作为本项目规范

# Deliverables
- 可运行的驱动/集成修改
- 最小验证记录（通信、方向、时序、稳定性）
- 已知硬件限制与规避建议
