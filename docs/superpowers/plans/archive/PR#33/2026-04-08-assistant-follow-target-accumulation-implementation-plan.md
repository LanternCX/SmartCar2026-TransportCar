# 辅车高频跟随目标累计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 把辅车高频跟随的目标更新从“每包覆盖当前位置目标”改成“首包建目标、后续有效包持续累计到已有目标”。

**Architecture:** 本轮只调整辅车位置式跟随中 `follow_target_world` 的更新语义，不改主车协议、不改辅车本地位置闭环、不改超时保护与 `seq` 去重。实现应继续沿用“本包位移先按当前朝向转到世界坐标”的解释方式，只把累计基准从当前位置改到已有目标位置。

**Tech Stack:** MicroPython、pytest、串口文本协议、辅车位置式跟随主线

---

### Task 1: 固化累计目标行为回归

**Files:**
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `tests/unit/assistant/test_protocol.py`

- [x] 补充失败测试，固定第一个有效跟随包会从当前位置建立 `follow_target_world`
- [x] 补充失败测试，固定后续前进的新 `seq` 包会在已有目标上继续累计，而不是重新覆盖成“当前位置 + 本包偏移”
- [x] 补充失败测试，固定重复包和倒退包不会被再次累计
- [x] 补充失败测试，固定 `valid=0` 会立刻清掉累计目标
- [x] 运行最小相关测试，确认新增测试先按预期失败，而不是测试本身写坏

### Task 2: 在辅车主线里实现累计目标更新

**Files:**
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/state/__init__.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`

- [x] 保持当前超时保护和 `seq` 前进检查不变，不把重复包纳入累计
- [x] 把首个有效包的目标建立逻辑保留为“当前位置 + 本包偏移”
- [x] 把后续有效包的目标更新逻辑改成“已有目标 + 本包偏移”
- [x] 保持本包位移仍按当前朝向转到世界坐标，不同时修改坐标解释时机
- [x] 运行直接相关测试，确认新增红灯转绿

### Task 3: 收口目标清理边界

**Files:**
- Modify: `src/assistant/motion_runtime.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`

- [x] 固定 `valid=0` 会清掉累计目标，不让旧目标跨无效段残留
- [x] 固定停机与超时路径仍会清掉累计目标，不让旧目标跨安全边界泄漏
- [x] 复跑相关回归，确认累计语义没有破坏当前停机与超时保护链路

### Task 4: 收口辅车主线回归与文档状态

**Files:**
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `docs/superpowers/specs/2026-04-08-assistant-follow-target-accumulation-design.md`
- Modify: `docs/superpowers/plans/2026-04-08-assistant-follow-target-accumulation-implementation-plan.md`

- [x] 复跑辅车相关单元测试，确认位置式跟随、协议解析、停机与超时保护仍保持可用
- [x] 在实现完成后把本轮 spec 标记为 archive，避免后续继续在同一份设计文档上叠加新需求
- [x] 在 plan 中勾选已完成事项，确保这轮变更的执行路径可回看
- [x] 汇报时明确说明：这轮只是把辅车目标改成逐包累计，不宣称已经同时解决所有耦合和整定问题
