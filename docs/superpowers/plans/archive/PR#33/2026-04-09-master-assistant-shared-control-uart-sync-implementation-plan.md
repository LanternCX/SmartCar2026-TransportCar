# 主辅车底盘控制与 UART3 共享边界同步实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 按最近一次有效改动为准，把主车补齐到辅车当前的底盘共享控制口径，并把 master 侧通用串口读取结构同步到 assistant。

**Architecture:** 本轮只处理共享边界，不碰主车视觉阶段、不碰辅车执行语义。底盘控制以辅车 `2713d7c` 为准同步到主车；串口读取按“共享 `UART3` 边界”和“主车视觉口专属预算”分开处理，在保留 `UART6/UART8` 专属预算的前提下，把 master 已落地的通用读取结构同步到 assistant。

**Tech Stack:** MicroPython、pytest、三轮全向底盘控制链、UART 文本链路

---

### Task 1: 固化最近改动优先的共享边界回归

**Files:**
- Modify: `tests/unit/master/test_motion_runtime.py`
- Modify: `tests/unit/master/test_stability_baseline.py`
- Modify: `tests/unit/master/test_runtime_loop.py`
- Modify: `tests/unit/assistant/test_runtime_loop.py`

- [x] 补充主车失败测试，固定“三轮目标超过上限时统一按比例缩放”的共享底盘规则。
- [x] 补充主车失败测试，固定“零周期时速度环回退到固定控制拍长”的共享底盘规则。
- [x] 补充主车失败测试，固定“里程累计使用姿态更新前朝向”的共享底盘规则。
- [x] 检查并补齐主车串口读取测试，确认共享 `UART3` 边界已经与辅车最近强化结果一致，同时不误伤 `UART6/UART8` 专属预算。
- [x] 运行最小相关测试，确认新增断言先按预期失败，而不是测试本身写坏。

### Task 2: 以辅车最近控制改动为准补齐主车底盘口径

**Files:**
- Modify: `src/master/ctrl/kinematics.py`
- Modify: `src/master/ctrl/pid.py`
- Modify: `src/master/motion_runtime.py`
- Test: `tests/unit/master/test_motion_runtime.py`
- Test: `tests/unit/master/test_stability_baseline.py`

- [x] 在主车底盘入口补齐统一按比例缩放逻辑，避免继续保留逐轮硬截断口径。
- [x] 在主车速度环入口补齐零周期固定拍长回退逻辑，贴齐辅车最近控制改动。
- [x] 在主车底座刷新链中补齐“里程累计使用姿态更新前朝向”的顺序。
- [x] 保持主车当前视觉状态机、跟随阶段和诊断收口行为不变，不把本轮扩大到视觉主线。
- [x] 运行直接相关测试，确认新增红灯转绿。

### Task 3: 同步 assistant 串口通用读取结构并收口边界结论

**Files:**
- Modify: `src/assistant/hw/uart.py`
- Modify: `tests/unit/master/test_runtime_loop.py`
- Modify: `tests/unit/assistant/test_runtime_loop.py`

- [x] 用测试明确记录本轮裁决：共享 `UART3` 读取边界以辅车最近改动为准。
- [x] 用测试明确记录主车 `UART6/UART8` 预算属于视觉口专属设计，不向辅车扩散。
- [x] 在 assistant 串口模块中同步 master 侧已落地的通用读取结构，但不引入 `UART6/UART8` 专属预算。
- [x] 运行最小串口相关测试，确认通用读取结构同步后，`UART3` 共享边界和视觉口专属预算结论同时成立。

### Task 4: 定向验证与文档收口

**Files:**
- Modify: `docs/superpowers/specs/2026-04-09-master-assistant-shared-control-uart-sync-design.md`
- Modify: `docs/superpowers/plans/2026-04-09-master-assistant-shared-control-uart-sync-implementation-plan.md`
- Test: `tests/unit/master/test_motion_runtime.py`
- Test: `tests/unit/master/test_stability_baseline.py`
- Test: `tests/unit/master/test_runtime_loop.py`
- Test: `tests/unit/assistant/test_runtime_loop.py`

- [x] 运行定向测试：`python3 -m pytest tests/unit/master/test_motion_runtime.py tests/unit/master/test_stability_baseline.py tests/unit/master/test_runtime_loop.py tests/unit/assistant/test_runtime_loop.py -q`。
- [x] 确认这轮只改变主车底盘共享规则和 assistant 串口通用读取结构，不引入辅车运行时或协议层额外改动。
- [x] 实现完成后把本轮 spec 标记为 archive，避免后续继续在同一份设计文档上叠加新主题。
- [x] 在 plan 中勾选已完成事项，确保这轮“最近改动优先”的执行路径可回看。
