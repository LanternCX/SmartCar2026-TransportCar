# 2025 智能车蚂蚁搬家组 - 搬运车模代码

本仓库维护 RT1021 搬运车模控制代码, 覆盖主辅双车协同、底盘控制、主辅通信、本地视觉链路和主机侧测试。

文档只记录代码和 git log 难以稳定给出的信息: 项目方向、外部约定、硬件事实、跨仓库职责、调试结论和长期决策。当前软件行为以代码、注释和行为测试为准。

## 协作入口

- 项目规则: `AGENTS.md`
- 代码外项目约束: `docs/developer/`
- 赛题外部链接: `docs/problem_statement/README.md`
- 长期协作记忆: `.serena/memories/`

## 附属仓库

- OpenART 视觉仓库位于 `../SmartCar2026-Vision`。
- 主机端侧手柄控制上位机位于 `../SmartCar2026-Controller`。

## 板端事实

`/dev/cu.usbmodem101` 实测为 RT1021 MicroPython 板端:

- MicroPython: `v1.20.0`
- 固件标识: `RT1021 MicroPython by NXP & SeekFree with CoreBoard-144Pin-BTB V3.1.0`
- 平台: `mimxrt`
- `.mpy` 版本: `version=6`, `sub-version=1`
- `.mpy` native 架构: `armv7emdp`

交叉编译配置使用:

```toml
mpy_cross_arch = "armv7emdp"
```
