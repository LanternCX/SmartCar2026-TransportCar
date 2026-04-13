# 辅车红色色块速度模式跟随实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前红色色块跟随主线从位置式输出切到辅车现成支持的速度式入口, 保持误差来源与分阶段节奏不变。

**Architecture:** 改动集中在 Vision 仓库, 辅车执行侧不重写。先用测试锁定速度模式报文、阶段输出与停下语义, 再最小改动替换发包格式和控制量口径, 最后同步文档并完成回归。

**Tech Stack:** MicroPython / Python 3.8+, pytest

---

## 范围确认

- 只修改 `SmartCar2026-Vision` 仓库。
- 不改 `TransportCar` 辅车控制核心。
- 不改 `red` 目标选择范围。
- 不改横向偏差来源与纵向面积误差来源。
- 不改“先横向, 后纵向”的分阶段节奏。

## 文件范围

- 修改: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/main.py`
- 修改: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- 修改: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`
- 修改: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/README.md`
- 修改: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/docs/Protocol.md`
- 修改归档状态: `docs/superpowers/specs/2026-04-10-assistant-follow-red-speed-mode-design.md`

## 任务拆分

### Task 1: 先补失败测试, 锁定速度模式新行为

- [ ] 在 `tests/unit/test_vision_protocol_rebuild.py` 把位置式报文断言改成速度式入口断言。
- [ ] 锁定无目标时输出零速度报文。
- [ ] 锁定横向阶段只输出 `x` 速度。
- [ ] 锁定纵向阶段只输出 `y` 速度。
- [ ] 锁定 `red` 目标范围保持不变。
- [ ] 在 `tests/contract/test_main_vision_protocol_contract.py` 同步最小协议契约。
- [ ] 运行目标测试并确认先失败。

### Task 2: 最小改动切换 `main.py` 到速度模式输出

- [ ] 保留当前 `red + 横向偏差 + 面积误差 + 分阶段` 框架。
- [ ] 将 `format_vision_frame` 从位置式 `follow` 输出改为速度式 `follow_velocity` 输出。
- [ ] 将 `build_follow_command` 的返回语义从位置量改成速度量。
- [ ] 保持目标丢失或保持阶段统一输出零速度。
- [ ] 保持不输出外部角度目标。
- [ ] 运行目标单测并修到通过。

### Task 3: 同步最小文档口径

- [ ] 在 `README.md` 中把当前输出描述改成速度模式入口。
- [ ] 在 `docs/Protocol.md` 中把当前协议示例和字段语义改成速度量口径。
- [ ] 不扩散清理无关内容。

### Task 4: 回归与归档

- [ ] 运行 Vision 仓库单元测试和契约测试。
- [ ] 确认与辅车现成速度模式入口兼容。
- [ ] 将本次速度模式设计文档状态从 `draft` 改为 `archive`。
- [ ] 在结果说明里写清“只切输出语义, 不动辅车控制核心”。

## 验证命令

- `python3 -m pytest tests/unit/test_vision_protocol_rebuild.py -q`
- `python3 -m pytest tests/unit tests/contract -q`

## 自检结果

- Spec coverage: 已覆盖速度模式入口、零速度停下、分阶段输出、文档同步与回归。
- Placeholder scan: 计划未保留 TBD / TODO 占位。
- Scope check: 改动收口在 Vision 仓库, 不扩散到辅车执行核心。
