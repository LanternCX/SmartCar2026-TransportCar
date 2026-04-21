# 辅车视觉输入与速度前馈裸相加实施计划

> 状态: Archive
> **给 Agent 工作者:** 必须使用 `superpowers:subagent-driven-development` 按任务逐项实现, 步骤统一使用复选框 `- [ ]` 维护执行状态。
> 当前约束以 `docs/superpowers/specs/2026-04-20-assistant-dual-input-feedforward-visual-design.md`、`docs/developer/control.md`、`docs/developer/vision.md` 与 `.agents/skills/using-rules/references/strategy-and-control.md` 为准。

**目标:** 让辅车 `UART6` 作为视觉输入、`UART8` 作为前馈输入, 两路都保持上一包、异步读取, 并在每个控制拍对 `vx / vy` 做按轴裸相加后写回共享底盘速度入口。

**架构:** 保留当前 `vision/assistant/` 的双路读取、共享解析、最近一包缓存和角色层编排, 不引入新的同步器或模式开关。角色层负责按控制拍取两路最新有效值完成融合, 其中 `UART6` 只贡献视觉侧 `vx / vy`, `UART8` 贡献前馈侧 `vx / vy / omega`, 最终继续通过共享底盘现有速度入口执行。

**技术栈:** Python、MicroPython 兼容运行时代码、pytest 单元测试、当前 `vision/assistant/` 角色层与 `src/core/runtime.py`

---

## 文件范围与职责

- 修改: `src/vision/assistant/follow_runtime.py`
  - 把双路输入职责收口为 `UART6` 视觉、`UART8` 前馈。
  - 保留异步读取和最近一包缓存语义。
  - 调整最终融合规则为 `vx / vy` 裸相加, `omega` 仅取 `UART8`。

- 修改: `src/vision/assistant/diagnostics.py`
  - 让快照能表达两路职责、最近一包和最终输出关系。

- 修改: `tests/unit/test_assistant_follow_runtime.py`
  - 固定视觉单路、前馈单路、双路裸相加、保持上一包、零包清零和 `omega` 来源语义。

- 修改: `docs/developer/control.md`
  - 收口辅车当前最小闭环的输入角色和融合语义。

- 修改: `docs/developer/vision.md`
  - 收口 `UART6` / `UART8` 的角色职责、异步读取和裸相加口径。

- 修改: `.agents/skills/using-rules/references/strategy-and-control.md`
  - 清掉与当前正式口径冲突的端口职责描述。

## Task 1: 先用失败测试固定新口径

**Files:**
- 修改: `tests/unit/test_assistant_follow_runtime.py`

- [ ] 新增或改写运行时测试, 固定以下行为:
  - `UART6` 单独输入时, 视觉链可以直接形成最终速度。
  - `UART8` 单独输入时, 前馈链可以直接形成最终速度。
  - 双路同时输入时, `vx / vy` 等于两路裸相加。
  - `omega` 只由 `UART8` 提供, `UART6` 不参与该轴融合。
  - 任一路本拍没有新包时继续保持上一包。
  - 任一路显式零包时只清该路自己的贡献。
  - 两路异步输入时不互相等待、不互相阻塞。

- [ ] 运行定向测试并保留失败证据:
  - `python3 -m pytest tests/unit/test_assistant_follow_runtime.py -q`

## Task 2: 收口角色层实现到新职责与新融合规则

**Files:**
- 修改: `src/vision/assistant/follow_runtime.py`
- 修改: `src/vision/assistant/diagnostics.py`
- 修改: `tests/unit/test_assistant_follow_runtime.py`

- [ ] 保留当前双路缓冲、逐行解析和共享速度字段解析边界, 不新增第二套解析器。

- [ ] 明确 `UART6` 只作为视觉侧 `vx / vy` 输入参与融合, `UART8` 作为前馈侧 `vx / vy / omega` 输入参与融合。

- [ ] 保持两路“收到新包就覆盖本路状态, 没有新包就保持上一包”的语义, 不新增超时清零。

- [ ] 把最终融合规则改为:
  - `final_vx = uart8_vx + uart6_vx`
  - `final_vy = uart8_vy + uart6_vy`
  - `final_omega = uart8_omega`

- [ ] 保留必要的非速度片段透传和现有共享底盘速度写回边界。

- [ ] 重新运行定向测试确认转绿:
  - `python3 -m pytest tests/unit/test_assistant_follow_runtime.py -q`

## Task 3: 同步文档与规则入口, 收口仓库正式口径

**Files:**
- 修改: `docs/developer/control.md`
- 修改: `docs/developer/vision.md`
- 修改: `.agents/skills/using-rules/references/strategy-and-control.md`

- [ ] 把 `docs/developer/control.md` 改成当前正式口径: `UART6` 视觉、`UART8` 前馈、按控制拍融合、保持上一包、`vx / vy` 裸相加。

- [ ] 把 `docs/developer/vision.md` 改成同一口径, 并写清 `omega` 当前只由前馈侧提供。

- [ ] 把规则入口里写反或写旧的端口职责一起修正, 避免后续 Agent 再按错误口径继续实现。

## Task 4: 完成验证并准备后续联调

**Files:**
- 修改: 如上文件范围

- [ ] 运行主机侧最小回归集合:
  - `python3 -m pytest tests/unit/test_assistant_follow_runtime.py tests/unit/test_assistant_velocity_packet.py tests/unit/test_assistant_velocity_source_state.py -q`

- [ ] 自检以下重点是否都已经被测试和实现覆盖:
  - 单独视觉可跑
  - 单独前馈可跑
  - 双路裸相加
  - 保持上一包
  - 零包清零
  - `omega` 只来自 `UART8`

- [ ] 若主机侧通过, 准备后续板端联调清单:
  - 只送 `UART6`
  - 只送 `UART8`
  - 两路同时异步送
  - 单路停更后观察“保持上一包”
  - 单路显式送零后观察该路贡献归零
