# 辅车主动跟随主车实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 把“辅车相机看主车标记并主动跟随主车”落到当前仓库主线，同时删掉主车侧旧双摄跟随职责。

**Architecture:** 本轮是双仓协同改动。视觉仓库把 OpenArt 输出从“给主车消费的像素观测”切到“直接输出当前辅车已经支持的 `follow` 控制请求”；车端仓库不重写辅车控制核心，只把控制输入来源切到辅车 `UART6`，继续沿用当前解析和底盘运动计算。主车侧则完整删除“读摄像头 -> 跳流程 -> 转发控制”的旧跟随整链，不在本轮处理主车剩余相机落位，也不扩展新的主辅通信协议；文档、测试和 HIL 留证同步改成“辅车单摄主动跟主，主车旧双摄跟随逻辑删除”的新口径。

**Tech Stack:** MicroPython、UART 文本协议、pytest、双仓协同文档与 HIL 留证

---

## 前置门禁

- [ ] 已确认硬件事实：辅车相机接辅车 `UART6`，相机发送的是位置式控制量。
- [ ] 本轮不新增主车侧通信协议主题；任何涉及主车如何发阶段命令的新需求，都要单独回到新 spec。
- [ ] 视觉仓库 `docs/problem_statement/spec.md` 中存在“辅助车不允许使用 OpenART”的规则摘录；当前实现按用户确认路线继续，但不要在本轮擅自改写该规则快照。

## 文件与职责

**辅车执行链**
- Modify: `src/assistant/config.py`
- Modify: `src/assistant/hw/uart.py`
- Modify: `src/assistant/app.py`
- Test: `tests/unit/assistant/test_protocol.py`
- Test: `tests/unit/assistant/test_app.py`
- Test: `tests/unit/assistant/test_runtime_loop.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`

职责收口：
- `config.py` 收口辅车 `UART6` 相机输入这一条硬件事实。
- `hw/uart.py` 负责把 `UART6` 接入当前逐行读取语义，不引入新的重型串口层。
- `app.py` 负责把高频控制入口切到 `UART6`，并继续保留超时、坏包和停机收口。
- `protocol.py` 与 `motion_runtime.py` 在本轮不做功能性重写，只通过回归测试锁住现有行为。

**主车删减链**
- Modify: `src/master/app.py`
- Modify: `src/master/protocol.py`
- Modify: `src/master/config.py`
- Modify: `src/master/hw/uart.py`
- Modify: `src/master/vision/ingress.py`
- Modify: `src/master/vision/decision.py`
- Modify: `src/master/vision/state_machine.py`
- Test: `tests/unit/master/test_protocol.py`
- Test: `tests/unit/master/test_app.py`
- Test: `tests/unit/master/test_runtime_loop.py`
- Test: `tests/unit/master/test_decision.py`
- Test: `tests/unit/master/test_vision_ingress.py`
- Test: `tests/unit/master/test_vision_state_machine.py`

职责收口：
- `app.py` 去掉主车替辅车做高频跟随输出和回读辅车反馈的旧主线。
- `protocol.py` 去掉只服务旧跟随主线的主车到辅车高频输出组织。
- `config.py`、`hw/uart.py`、`vision/*` 只负责删除与旧双摄跟随直接绑定的假设，不在本轮写死主车剩余相机端口。

**文档与留证**
- Modify: `docs/developer/strategy.md`
- Modify: `docs/developer/tasks.md`
- Modify: `docs/developer/vision.md`
- Modify: `.agents/skills/using-rules/references/hardware-and-protocol.md`
- Modify: `docs/superpowers/specs/2026-04-09-assistant-active-follow-master-design.md`
- Create: `tests/hil/2026-04-09-assistant-active-follow-master.md`

职责收口：
- 方向文档改成“辅车单摄主动跟主，主车旧双摄跟随逻辑删除”。
- 私有硬件事实页只写当前已确认事实，不用猜主车剩余相机端口。
- HIL 文档记录 stage2 smoke 和 stage3 人工跟随留证。
- 实现与留证完成后，把当前 spec 状态改为 `archive`。

**视觉仓库执行链**
- Modify: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/main.py`
- Modify: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/README.md`
- Modify: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/docs/Protocol.md`
- Test: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- Test: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`
- Create: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/hil/2026-04-09-assistant-follow-master-marker.md`

职责收口：
- `main.py` 继续保持单文件架构，但把输出语义从像素观测改成辅车可直接消费的位置式控制量。
- `main.py` 直接产出当前辅车已经支持的 `follow` 请求, 不要求辅车重写控制核心。
- `README.md` 与 `docs/Protocol.md` 同步改成“辅车相机主动跟主”的当前路线，不再保留“只给主车看”的旧说法。
- 单元与契约测试负责锁住视觉端输出直接对齐辅车现有协议。
- `docs/problem_statement/spec.md` 不在本轮改写，只把冲突作为已知背景记录在实现和留证里。

### Task 1: 锁住辅车控制核心保持不变

**Files:**
- Modify: `tests/unit/assistant/test_protocol.py`
- Modify: `tests/unit/assistant/test_app.py`
- Modify: `tests/unit/assistant/test_runtime_loop.py`
- Modify: `tests/unit/assistant/test_motion_runtime.py`

- [ ] 补一组失败测试，锁住辅车当前 `follow` 协议解析保持不变。
- [ ] 补一组失败测试，锁住辅车当前底盘运动计算和安全收口保持不变。
- [ ] 补一组失败测试，明确本轮只允许改输入来源，不允许顺手改控制行为。
- [ ] 先只跑这组辅车定向测试，确认后续改动不会把现有控制核心带偏。

### Task 2: 仅做辅车输入来源切换

**Files:**
- Modify: `src/assistant/config.py`
- Modify: `src/assistant/hw/uart.py`
- Modify: `src/assistant/app.py`
- Test: `tests/unit/assistant/test_app.py`
- Test: `tests/unit/assistant/test_runtime_loop.py`

- [ ] 在辅车配置中补齐 `UART6` 相机输入事实。
- [ ] 让辅车串口薄封装支持当前最小 `UART6` 逐行读取语义，但不要顺手扩成新的串口抽象层。
- [ ] 把辅车主循环的高频控制读取入口从旧主车来源切到 `uart6`。
- [ ] 保留“同拍只吃最新一条完整命令”的现有止积压策略，不回退成追旧包。
- [ ] 跑辅车应用入口和主循环测试，确认只是输入来源变了，控制行为没有变。

### Task 3: 把主车旧跟随逻辑迁到 ART

**Files:**
- Modify: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- Modify: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`
- Modify: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/main.py`

- [ ] 先补失败测试，锁住 ART 端输出直接对齐当前辅车已经支持的 `follow` 请求格式。
- [ ] 先补失败测试，锁住 ART 端承担原本主车侧的跟随阶段判断和控制量生成，而不是只发像素观测。
- [ ] 在保持单文件架构的前提下改 `main.py`，把当前主车旧跟随逻辑迁到 ART。
- [ ] 不额外扩展第二套视觉发包字段，也不要求辅车为了 ART 适配新协议。
- [ ] 跑视觉仓库 unit 与 contract 定向测试，确认逻辑迁移完成。

### Task 4: 完整删除主车旧跟随整链

**Files:**
- Modify: `tests/unit/master/test_protocol.py`
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/master/test_runtime_loop.py`
- Modify: `tests/unit/master/test_decision.py`
- Modify: `src/master/app.py`
- Modify: `src/master/protocol.py`
- Modify: `src/master/vision/decision.py`
- Modify: `src/master/vision/state_machine.py`

- [ ] 先补失败测试，锁住主车不再读取跟随相机、不再跳跟随阶段、不再转发跟随控制。
- [ ] 从主车运行时里完整删掉旧的“读摄像头 -> 跳流程 -> 转发控制”整链。
- [ ] 不保留为了兼容旧跟随流程而存在的中间适配层。
- [ ] 跑主车应用和运行循环相关测试，确认旧跟随整链已经退出主车。

### Task 5: 把主车重构成后续找物前的最薄骨架

**Files:**
- Modify: `tests/unit/master/test_app.py`
- Modify: `tests/unit/master/test_runtime_loop.py`
- Modify: `tests/unit/master/test_vision_ingress.py`
- Modify: `src/master/app.py`
- Modify: `src/master/config.py`
- Modify: `src/master/hw/uart.py`
- Modify: `src/master/vision/ingress.py`

- [ ] 把主车当前双摄跟随假设收口成一个最薄骨架，只为后续找物预留接口。
- [ ] 不实现新的找物流程、不接回新的相机主线、不顺手扩展后续阶段能力。
- [ ] 删掉只服务旧双摄跟随优先级的旧配置与旧测试假设。
- [ ] 跑主车最小骨架相关测试，确认已经为后续找物重构出干净起点。

### Task 6: 同步双仓文档口径

**Files:**
- Modify: `docs/developer/strategy.md`
- Modify: `docs/developer/tasks.md`
- Modify: `docs/developer/vision.md`
- Modify: `.agents/skills/using-rules/references/hardware-and-protocol.md`
- Modify: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/README.md`
- Modify: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/docs/Protocol.md`

- [ ] 把方向文档里的“主车双摄统一驱动辅车”改成“辅车单摄主动跟主，主车旧跟随整链删除”。
- [ ] 删掉主车侧仍承担辅车高频跟随闭环的旧任务描述。
- [ ] 把“搬运阶段先不纳入当前目标”同步到相关方向描述里，避免再次扩大范围。
- [ ] 在硬件事实页只写本轮已确认事实：辅车相机接辅车 `UART6`；主车剩余相机落位本轮先不处理。
- [ ] 把视觉仓库 README 和协议文档同步改成“ART 直接输出当前辅车已支持控制请求”的口径。
- [ ] 不改写视觉仓库的官方题面整理正文，只把冲突作为已知背景显式保留。
- [ ] 跑双仓文档契约与必要结构测试，确认口径已经换到新方向。

### Task 7: 完成双仓 HIL 留证并归档当前 spec

**Files:**
- Create: `tests/hil/2026-04-09-assistant-active-follow-master.md`
- Modify: `docs/superpowers/specs/2026-04-09-assistant-active-follow-master-design.md`
- Create: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/hil/2026-04-09-assistant-follow-master-marker.md`

- [ ] 先做最小 stage2 smoke，使用仓库既有最小命令 `python3 tools/run_stage2_smoke.py --port <port>` 留下连接、上传、导入和最小启动证据。
- [ ] 再做 stage3 人工留证，记录“ART 直接发当前辅车已支持控制请求”“辅车能稳定跟主车标记”“丢目标或停输入后能停下”三类实测结论。
- [ ] 把步骤、预期、实测和结论写进新的 HIL 文档，不用一句话口头代替证据。
- [ ] 所有实现与留证完成后，把 `docs/superpowers/specs/2026-04-09-assistant-active-follow-master-design.md` 的状态改成 `archive`。
- [ ] 如需提交，先向用户确认提交信息；不要自行创建提交。

### Task 8: 双仓全量回归与收口检查

**Files:**
- Test: `tests/unit/assistant/test_protocol.py`
- Test: `tests/unit/assistant/test_app.py`
- Test: `tests/unit/assistant/test_runtime_loop.py`
- Test: `tests/unit/assistant/test_motion_runtime.py`
- Test: `tests/unit/master/test_protocol.py`
- Test: `tests/unit/master/test_app.py`
- Test: `tests/unit/master/test_runtime_loop.py`
- Test: `tests/unit/master/test_decision.py`
- Test: `tests/unit/master/test_vision_ingress.py`
- Test: `tests/unit/master/test_vision_state_machine.py`
- Test: `tests/contract/test_openart_protocol_doc_contract.py`
- Test: `tests/unit/test_runtime_entry_layout.py`
- Test: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- Test: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`
- Test: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/unit/test_agentization_baseline.py`
- Test: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/contract/test_problem_statement_contract.py`

- [ ] 先跑本轮新增和直接相关测试，确认红转绿。
- [ ] 再跑双仓运行时、结构约束和文档契约相关回归，确认没有把现有入口和治理边界打坏。
- [ ] 汇报时明确说明：本轮完成的是“双仓协同下的辅车主动跟随主车”和“主车旧跟随职责删减”，不宣称搬运阶段已经完成。
