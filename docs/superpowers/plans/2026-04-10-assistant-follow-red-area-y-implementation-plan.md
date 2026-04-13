# 辅车红色色块面积纵向控制实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让辅车视觉主线只识别红色色块, 保持横向控制不变, 并把纵向控制从位置误差切换为面积误差。

**Architecture:** 改动集中在 Vision 仓库 `main.py` 与对应单元测试。先用测试锁定“只识别 red、面积误差驱动 y、死区与停下语义”, 再最小改动替换纵向控制输入与参数, 最后同步文档口径并完成回归。

**Tech Stack:** MicroPython / Python 3.8+, pytest

---

## 范围确认

- 只修改 `SmartCar2026-Vision` 仓库。
- 不改车端执行协议。
- 不改横向控制逻辑。
- 不改整体跟随阶段节奏, 只替换纵向判据。

## 文件范围

- 修改: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/main.py`
- 修改: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/tests/unit/test_vision_protocol_rebuild.py`
- 视实现情况修改: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/README.md`
- 视实现情况修改: `/Users/caoxin/Code/SmartCar/SmartCar2026-Vision/docs/Protocol.md`
- 修改归档状态: `docs/superpowers/specs/2026-04-10-assistant-follow-red-area-y-design.md`

## 任务拆分

### Task 1: 先补失败测试, 锁定新行为

- [ ] 在 `tests/unit/test_vision_protocol_rebuild.py` 增加或替换测试, 明确以下行为:
- [ ] 锁定任务集合只包含 `red`。
- [ ] 锁定纵向控制使用面积目标、面积死区、面积比例与输出上限。
- [ ] 锁定横向未对齐时仍只输出 `x`。
- [ ] 锁定横向已对齐后, 面积误差进入死区时 `y=0`。
- [ ] 锁定面积偏小时输出前进方向, 面积偏大时输出后退方向。
- [ ] 锁定丢目标仍输出无效跟随并停下。
- [ ] 运行新增测试并确认先失败。

### Task 2: 最小改动替换 `main.py` 的纵向控制来源

- [ ] 删除或停用旧的 `green` 识别任务。
- [ ] 新增面积目标、面积死区、面积比例、纵向输出上限这组参数。
- [ ] 让候选目标携带面积信息, 保证后续控制链可直接消费。
- [ ] 保持 `x` 计算方式不变。
- [ ] 把 `y` 从纵向位置误差切换为面积误差驱动。
- [ ] 保持阶段节奏不变: 先看横向, 再看纵向。
- [ ] 保持无目标立即停下语义不变。
- [ ] 运行目标单测并修到通过。

### Task 3: 同步最小文档口径

- [ ] 检查 `README.md` 与 `docs/Protocol.md` 是否还把纵向依据写成位置误差。
- [ ] 若有冲突, 改成“只识别 red, y 基于面积误差”的最新口径。
- [ ] 不扩散清理无关内容。

### Task 4: 回归与归档

- [ ] 运行 Vision 仓库相关单测与需要的契约测试。
- [ ] 确认没有引入与 follow 请求格式冲突的新行为。
- [ ] 将设计文档状态从 `draft` 改为 `archive`, 标明设计已执行完成。
- [ ] 更新本次执行结果说明, 方便后续回看。

## 验证命令

- `python3 -m pytest tests/unit/test_vision_protocol_rebuild.py -q`
- `python3 -m pytest tests/unit tests/contract -q`

## 自检结果

- Spec coverage: 已覆盖只识别 `red`、`x` 保持、`y` 改面积误差、目标面积参数化、丢目标停下、最小文档同步与回归。
- Placeholder scan: 计划未保留 TBD / TODO 占位。
- Scope check: 改动收口在 Vision 仓库, 未扩散到主车或车端执行协议。
