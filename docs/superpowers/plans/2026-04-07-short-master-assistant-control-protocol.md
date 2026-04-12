# 主辅控制短协议与可靠性收口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 把主车到辅车的高频控制协议缩短到更抗坏包的正式口径，同时确认主车发送节拍已经满足高频要求，并同步完成主辅解析与测试收口。

**Architecture:** 保留当前“主车每拍发送、辅车只消费最新完整控制”的总体结构，不再继续在高频控制链上堆长字段。把高频控制链收口为更短的固定头短文本协议，错误与状态链保持现有调试能力，避免把调试需求继续混入高频正式控制负载。

**Tech Stack:** MicroPython、串口文本协议、pytest

---

### Task 1: 确认正式短协议口径

**Files:**
- Modify: `src/master/protocol.py`
- Modify: `src/assistant/protocol.py`
- Test: `tests/unit/master/test_decision.py`
- Test: `tests/unit/assistant/test_protocol.py`

- [ ] 确认主辅高频控制正式改为短协议，保留乱序判断所需最小字段。
- [ ] 删除高频正式控制里的长字段头与无效原因字段。
- [ ] 保持辅车调试错误输出能力，不把错误调试信息重新混入正式控制正文。

### Task 2: 收口主车发送链

**Files:**
- Modify: `src/master/vision/decision.py`
- Modify: `src/master/app.py`
- Modify: `src/master/runtime_params.py`
- Test: `tests/unit/master/test_app.py`
- Test: `tests/unit/master/test_runtime_loop.py`
- Test: `tests/unit/master/test_runtime_params.py`

- [ ] 核对主车当前控制节拍是否已满足 30fps 以上要求。
- [ ] 若当前已满足，则不额外提高节拍，只更新相关测试口径。
- [ ] 若发现存在其他限速点，再仅修改真正限制发送频率的位置。

### Task 3: 收口辅车解析与调试回包

**Files:**
- Modify: `src/assistant/app.py`
- Modify: `src/assistant/protocol.py`
- Test: `tests/unit/assistant/test_app.py`
- Test: `tests/unit/assistant/test_runtime_loop.py`

- [ ] 让辅车按新短协议解析高频控制。
- [ ] 保持调试阶段正常包也回短确认、坏包回错误原因的现有联调能力。
- [ ] 确认回包格式不会重新把高频链拖长到失去收益。

### Task 4: 验证与收口

**Files:**
- Test: `tests/unit/master/test_decision.py`
- Test: `tests/unit/master/test_app.py`
- Test: `tests/unit/master/test_runtime_loop.py`
- Test: `tests/unit/master/test_runtime_params.py`
- Test: `tests/unit/assistant/test_protocol.py`
- Test: `tests/unit/assistant/test_app.py`
- Test: `tests/unit/assistant/test_runtime_loop.py`
- Test: `tests/unit/assistant/test_runtime_params.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`

- [ ] 先跑短协议直接相关测试，确认红绿收敛正确。
- [ ] 再跑主辅相关回归测试，确认没有把现有链路打坏。
- [ ] 最终汇报时明确说明：正式高频控制协议已缩短、主车当前发送节拍是否已满足目标、仍需现场验证的部分是什么。
