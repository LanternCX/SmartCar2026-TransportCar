# 辅车位置式跟随速度上限调整实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 在不改变位置式语义、协议和超时边界的前提下，提高辅车位置式跟随在单个有效窗口内的可达位移。

**Architecture:** 本轮只调整位置式链路中的固定平移速度上限，不改速度模式、不改位置比例项，也不改变 150ms 超时边界。实现应继续复用现有位置误差到车体系速度的解算链，只把参数读取、限速结果和回归边界收口到可验证状态。

**Tech Stack:** MicroPython、pytest、串口文本协议、三轮全向底盘控制链

---

### Task 1: 固化本轮回归边界

**Files:**
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `tests/unit/assistant/test_runtime_params.py`
- Modify: `tests/unit/assistant/test_stability_baseline.py`

- [x] 补充“位置式平移速度上限由运行时参数读取”的失败测试，固定参数入口仍然由 `runtime_params` 统一提供
- [x] 补充“位置式大误差阶段会被新的固定上限限制，但限制值高于当前版本”的失败测试，避免实现时误改为动态调速或误改比例项
- [x] 复用现有速度模式持续性回归作为保护边界，防止单参数调整误伤另一条链路
- [x] 运行最小相关测试，确认新增测试先按预期失败，而不是测试本身写坏

### Task 2: 上调位置式固定平移速度上限

**Files:**
- Modify: `src/assistant/runtime_params.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/ctrl/kinematics.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`
- Test: `tests/unit/assistant/test_runtime_params.py`
- Test: `tests/unit/assistant/test_stability_baseline.py`

- [x] 只调整位置式固定平移速度上限对应参数，不同时改位置比例项、超时窗口或协议字段
- [x] 确认运行时继续从统一参数入口读取该上限，并让位置误差解算仍通过现有限速逻辑收口
- [x] 保持现有速度模式、停机、超时和默认保头规则不变，不引入新的模式分支
- [x] 运行直接相关测试，确认新增红灯转绿

### Task 3: 收口主机侧回归与行为边界

**Files:**
- Test: `tests/unit/assistant/test_motion_runtime.py`
- Test: `tests/unit/assistant/test_runtime_params.py`
- Test: `tests/unit/assistant/test_stability_baseline.py`

- [x] 复跑位置式相关回归，确认相同误差下的输出上限已经提高
- [x] 复跑速度模式、超时停机、STOP、DISARM 和保头相关回归，确认行为边界没有被连带改坏
- [x] 检查本轮改动面，确认没有顺手扩大到协议、模式语义或额外控制参数

### Task 4: 整理板端验证关注点与收口说明

**Files:**
- Modify: `docs/superpowers/specs/2026-04-08-assistant-follow-position-speed-cap-design.md`

- [x] 在 spec 执行完成后按仓库约定标记为 archive，不继续把它当作待设计文档
- [x] 汇报时明确说明：本轮只是提高位置式固定平移速度上限，不宣称已经完成新的调速策略或里程计精度提升
- [x] 给出板端联调关注点：同样 150ms 窗口内追赶距离是否变大、近距离是否明显更冲、速度模式与停机语义是否保持原样
