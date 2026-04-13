# 辅车 legacy 控制内核对齐实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 在保留当前辅车协议与入口的前提下，把控制内核的关键口径对齐到 legacy，并把“保护态继续保头、真停机仍真停机”的边界落实为可验证行为。

**Architecture:** 本轮只调整辅车控制内核，不回退协议和应用外壳。核心做法是把位置累计顺序、三轮限幅方式、零周期速度环拍长口径和保护/停机分层对齐到 legacy，同时保留上一轮已经修好的模式持续性。

**Tech Stack:** MicroPython、pytest、串口文本协议、三轮全向底盘控制链

---

### Task 1: 固化 legacy 对齐回归边界

**Files:**
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `tests/unit/assistant/test_stability_baseline.py`

- [ ] 补充“里程累计使用姿态更新前朝向”的失败测试，固定 legacy 的积分顺序。
- [ ] 补充“三轮目标在进入速度环前统一按比例缩放”的失败测试，禁止逐轮硬截断继续作为正确行为。
- [ ] 补充“零周期速度环使用固定控制拍长回退”的失败测试，避免零周期拍长口径继续漂移。
- [ ] 补充“保护态继续保头、显式真停机仍彻底停机”的边界测试。
- [ ] 运行最小相关测试，确认新增测试先按预期失败，而不是测试本身写坏。

### Task 2: 对齐 legacy 控制内核口径

**Files:**
- Modify: `src/assistant/ctrl/kinematics.py`
- Modify: `src/assistant/ctrl/pid.py`
- Modify: `src/assistant/motion_runtime.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`
- Test: `tests/unit/assistant/test_stability_baseline.py`

- [ ] 调整里程累计入口，让当前拍里程积分按姿态更新前朝向解释轮速。
- [ ] 调整三轮目标限幅方式，改为 legacy 的统一按比例缩放。
- [ ] 调整零周期速度环拍长回退口径，贴齐 legacy 的固定控制拍长理解。
- [ ] 保持上一轮已完成的模式持续性修复，不让普通模式或速度模式退回单拍行为。
- [ ] 运行直接相关测试，确认新增红灯转绿。

### Task 3: 收口保护态与真停机边界

**Files:**
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/state/__init__.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`

- [ ] 确保保护态清掉平移推进，但继续保头。
- [ ] 确保 `STOP`、`DISARM` 等显式真停机路径仍保持彻底停机。
- [ ] 确保保护态继续保头不会破坏当前状态标签、超时状态和外部可观察语义。
- [ ] 运行保护态与停机边界测试，确认没有互相覆盖。

### Task 4: 全量验证与实机关注点整理

**Files:**
- Test: `tests/unit/assistant/test_motion_runtime.py`
- Test: `tests/unit/assistant/test_app.py`
- Test: `tests/unit/assistant/test_protocol.py`
- Test: `tests/unit/assistant/test_runtime_loop.py`
- Test: `tests/unit/assistant/test_runtime_params.py`
- Test: `tests/unit/assistant/test_stability_baseline.py`

- [ ] 运行本轮新增和直接相关测试，确认 legacy 对齐点成立。
- [ ] 运行辅车相关完整回归，确认协议、回包、运行循环和上一轮模式持续性没有回归。
- [ ] 汇报时明确说明：本轮是 legacy 控制内核对齐，不宣称已完成单位重标定或整套 legacy 回退。
- [ ] 汇报时明确给出实机关注点：发过位置指令后是否仍持续保头、大平移时保头手感是否更接近 legacy、保护态是否停平移但继续保头。
