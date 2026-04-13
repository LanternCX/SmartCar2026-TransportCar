# 主车跟随轴向分阶段状态机实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 把主车当前最小跟随主线改成“先对正 `x`, 再对正 `y`”的状态机驱动控制，并在 `x` 再次偏出时立刻回退到横向对正。

**Architecture:** 继续沿用主车现有最小框架，由 `vision/state_machine.py` 负责阶段切换，由 `vision/decision.py` 负责按阶段生成单轴输出。本轮只把 `TRACKING` 拆成 `ALIGN_X / ALIGN_Y`，不改辅车协议、不改头对头方向换算、不改当前死区参数。

**Tech Stack:** MicroPython、pytest、串口文本协议、主车最小视觉状态机

---

### Task 1: 固化状态机分阶段行为回归

**Files:**
- Modify: `tests/unit/master/test_vision_state_machine.py`
- Modify: `tests/unit/master/test_decision.py`

- [x] 补充主车状态机失败测试，固定“`x` 未进死区时进入 `ALIGN_X`，且不会直接进入 `ALIGN_Y`”的行为
- [x] 补充主车状态机失败测试，固定“`x` 已进死区但 `y` 未进时进入 `ALIGN_Y`”的行为
- [x] 补充主车状态机失败测试，固定“`ALIGN_Y` 期间只要 `x` 再偏出死区就立刻回到 `ALIGN_X`”的行为
- [x] 补充决策层失败测试，固定 `ALIGN_X` 只发横向、`ALIGN_Y` 只发纵向、另一轴强制归零
- [x] 运行最小相关测试，确认新增测试先按预期失败，而不是测试本身写坏

### Task 2: 在当前框架内实现 `ALIGN_X / ALIGN_Y`

**Files:**
- Modify: `src/master/vision/state_machine.py`
- Modify: `src/master/vision/decision.py`
- Test: `tests/unit/master/test_vision_state_machine.py`
- Test: `tests/unit/master/test_decision.py`

- [x] 把主车状态机正式阶段从三态扩成 `MARKER_MISSING / CENTER_HOLD / ALIGN_X / ALIGN_Y`
- [x] 保持“无目标进 `MARKER_MISSING`、双轴都在死区进 `CENTER_HOLD`”的原边界不变
- [x] 实现“`x` 不在死区时优先 `ALIGN_X`、只有 `x` 已进死区后才允许进入 `ALIGN_Y`”的切换规则
- [x] 实现“`ALIGN_Y` 期间 `x` 再次偏出当前死区就立刻回 `ALIGN_X`”的回退规则
- [x] 在决策层按阶段输出单轴控制量，确保 `ALIGN_X` 时 `y=0`、`ALIGN_Y` 时 `x=0`
- [x] 运行直接相关测试，确认新增红灯转绿

### Task 3: 收口主车主线回归边界

**Files:**
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/master/test_runtime_loop.py`
- Test: `tests/unit/master/test_vision_state_machine.py`
- Test: `tests/unit/master/test_decision.py`

- [x] 更新主车应用层与运行环路测试中的阶段预期，确保它们跟随新的 `ALIGN_X / ALIGN_Y / CENTER_HOLD / MARKER_MISSING` 语义
- [x] 固定主车对辅车的输出链路仍沿用当前协议，只改变当前拍允许输出哪一轴
- [x] 复跑主车相关回归，确认改动没有扩散到无目标、保持态和反馈读取链路

### Task 4: 整理文档状态与汇报边界

**Files:**
- Modify: `docs/superpowers/specs/2026-04-08-master-follow-axis-sequencing-design.md`
- Modify: `docs/superpowers/plans/2026-04-08-master-follow-axis-sequencing-implementation-plan.md`

- [x] 在实现完成后把本轮 spec 标记为 archive，避免后续继续在同一份设计文档上叠加新需求
- [x] 在 plan 中勾选已完成事项，确保这轮变更的执行路径可回看
- [x] 汇报时明确说明：这轮只是把主车跟随切成“先 `x` 后 `y`”的状态机规则，不宣称已经解决所有底盘耦合问题
