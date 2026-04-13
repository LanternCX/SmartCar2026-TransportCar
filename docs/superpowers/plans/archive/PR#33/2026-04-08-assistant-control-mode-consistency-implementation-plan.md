# 辅车控制模式一致性修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 修复辅车普通跟随模式与速度模式在后续周期中的行为不一致问题，并把“默认持续启用朝向保持、显式角速度例外”的规则落实到统一控制链中。

**Architecture:** 本轮不扩大协议面，也不处理单位重标定，只在辅车控制链内部补齐最小模式状态与周期分发规则。平移模式和转向来源分开管理：普通跟随与速度模式决定平移输出，自动朝向保持与显式角速度决定转向输出。

**Tech Stack:** MicroPython、串口文本协议、pytest

---

### Task 1: 固化回归测试边界

**Files:**
- Modify: `tests/unit/assistant/test_protocol.py`
- Modify: `tests/unit/assistant/test_app.py`
- Modify: `tests/unit/assistant/test_motion_runtime.py`
- Modify: `tests/unit/assistant/test_runtime_loop.py`

- [ ] 补充“速度模式收包后后续周期仍持续输出速度目标”的失败测试。
- [ ] 补充“普通模式在后续周期继续保持位置控制”的保护测试，确保本轮修复不打坏已跑通行为。
- [ ] 补充“默认持续启用朝向保持”的失败测试，覆盖普通模式与速度模式。
- [ ] 补充“显式角速度输入接管转向、撤销后回到自动朝向保持”的失败测试。
- [ ] 运行新增测试，确认它们在当前实现上以预期方式失败。

### Task 2: 增加最小模式状态

**Files:**
- Modify: `src/assistant/state/__init__.py`
- Modify: `src/assistant/motion_runtime.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`

- [ ] 为运行时增加最小平移模式状态，只区分无激活、普通跟随、速度模式。
- [ ] 为运行时增加最小转向来源状态，只区分自动朝向保持与显式角速度控制。
- [ ] 保持现有主线公开字段尽量不变，不引入无关状态重构。
- [ ] 运行模式状态直接相关测试，确认状态切换逻辑通过。

### Task 3: 修复速度模式跨周期持续行为

**Files:**
- Modify: `src/assistant/protocol.py`
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/app.py`
- Test: `tests/unit/assistant/test_protocol.py`
- Test: `tests/unit/assistant/test_app.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`
- Test: `tests/unit/assistant/test_runtime_loop.py`

- [ ] 保持 `f=1,m=1,x=...,y=...` 协议入口不变。
- [ ] 让速度模式在收包后写入跨周期可持续保持的速度目标。
- [ ] 修正后续周期分发，让速度模式不再错误落回普通位置路径。
- [ ] 保持现有调试确认与错误回包行为，不在本轮扩大回包协议面。
- [ ] 运行速度模式相关测试，确认红转绿。

### Task 4: 收口朝向保持规则

**Files:**
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/ctrl/attitude.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`
- Test: `tests/unit/assistant/test_stability_baseline.py`

- [ ] 明确普通模式默认持续启用朝向保持。
- [ ] 明确速度模式默认持续启用朝向保持。
- [ ] 明确无激活/空闲阶段仍按当前设计保留零平移下的朝向保持或对应停机行为。
- [ ] 明确只有显式角速度输入非零时，转向来源才切到手动角速度。
- [ ] 明确显式角速度撤销后，转向来源回到当前平移模式对应的自动朝向保持。
- [ ] 运行角度保持与显式角速度相关测试，确认规则闭合。

### Task 5: 修复停机与超时收口

**Files:**
- Modify: `src/assistant/motion_runtime.py`
- Modify: `src/assistant/state/__init__.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`
- Test: `tests/unit/assistant/test_runtime_params.py`

- [ ] 确保 `HOLD`、`STOP`、`DISARM`、超时和重置里程都会清空当前模式状态。
- [ ] 确保旧速度目标不会在停机后残留到后续周期。
- [ ] 运行停机与超时相关测试，确认没有回归。

### Task 6: 全量验证与收口说明

**Files:**
- Test: `tests/unit/assistant/test_protocol.py`
- Test: `tests/unit/assistant/test_app.py`
- Test: `tests/unit/assistant/test_runtime_loop.py`
- Test: `tests/unit/assistant/test_runtime_params.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`
- Test: `tests/unit/assistant/test_stability_baseline.py`

- [ ] 先跑本轮新增和直接相关测试，确认修复点成立。
- [ ] 再跑辅车控制链相关完整回归，确认没有打坏现有普通模式与状态回包。
- [ ] 汇报时明确说明：本轮只修控制模式持续性与朝向保持规则，不宣称已完成单位重标定。
