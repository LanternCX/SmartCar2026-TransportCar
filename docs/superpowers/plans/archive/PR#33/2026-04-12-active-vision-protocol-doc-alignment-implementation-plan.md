# 当前视觉协议生效文档对齐实施计划

> **面向代理执行者：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 让当前仍在生效位置的规则文档、开发文档与当前代码中的视觉协议事实完全一致，并把与当前代码不一致的非归档视觉设计文档移出根目录。

**Architecture:** 先以 `src/services/vision_protocol.py` 和 `src/services/transport_car.py` 为唯一事实源，收口规则入口正文，再同步 `docs/developer/*` 的现状口径，最后把两份位于生效位置的未落地视觉设计文档归入 `archive/PR#25/`。整个过程只改文档，不碰运行时代码，不改 `AGENTS.md`。

**Tech Stack:** Markdown 文档、`rg` 内容核对、git 变更检查

---

## 文件边界

- Modify: `.agents/skills/using-rules/references/openart-protocol.md`
- Modify: `.agents/skills/using-rules/references/hardware-and-protocol.md`
- Modify: `docs/developer/strategy.md`
- Modify: `docs/developer/tasks.md`
- Modify: `docs/developer/vision.md`
- Modify: `docs/developer/control.md`
- Move: `docs/superpowers/specs/2026-04-06-vision-minimal-text-protocol-design.md` -> `docs/superpowers/specs/archive/PR#25/2026-04-06-vision-minimal-text-protocol-design.md`
- Move: `docs/superpowers/plans/2026-04-06-vision-minimal-text-protocol-implementation-plan.md` -> `docs/superpowers/plans/archive/PR#25/2026-04-06-vision-minimal-text-protocol-implementation-plan.md`
- Exclude: `AGENTS.md`

### Task 1: 收口规则入口正文

**Files:**
- Modify: `.agents/skills/using-rules/references/openart-protocol.md`
- Modify: `.agents/skills/using-rules/references/hardware-and-protocol.md`

- [ ] 先以 `src/services/vision_protocol.py` 与 `src/services/transport_car.py` 提炼当前唯一有效事实：`uart6`、纯 `x,y` 文本、单向观测输入。
- [ ] 改写 `openart-protocol.md` 的视觉协议现状正文，使其只描述当前代码事实，不出现 `UART8` 双路现状、`v/s`、完整框、`camera_id/category`、识别框摘要等正文口径。
- [ ] 改写 `hardware-and-protocol.md`，把硬件存在事实与当前运行时现状分开表达；联调检查项只保留当前代码可验证的内容。
- [ ] 运行核对命令，检查两份规则正文中不再残留错误的现状口径：`rg "UART8|v=1|v=0|camera_id|category|obs_left|obs_right|obs_bottom" .agents/skills/using-rules/references/openart-protocol.md .agents/skills/using-rules/references/hardware-and-protocol.md`

### Task 2: 同步开发文档口径

**Files:**
- Modify: `docs/developer/strategy.md`
- Modify: `docs/developer/tasks.md`
- Modify: `docs/developer/vision.md`
- Modify: `docs/developer/control.md`

- [ ] 改写 `docs/developer/vision.md` 的现状正文，只保留当前视觉协议事实，并把后续规划单独标记。
- [ ] 改写 `docs/developer/strategy.md` 中涉及视觉链路的现状描述，不把双路输入、多检测、`camera_id/category` 写成当前事实。
- [ ] 改写 `docs/developer/tasks.md`，把双 UART、多检测等内容放回后续任务位置，不让任务清单暗示当前代码已经按另一套协议运行。
- [ ] 同步 `docs/developer/control.md` 中涉及视觉链路的表述，使其与其余开发文档一致。
- [ ] 运行核对命令，检查开发文档中的现状正文不再残留错误口径：`rg "UART8|v=1|v=0|camera_id|category|obs_left|obs_right|obs_bottom|多条检测|双 UART" docs/developer/strategy.md docs/developer/tasks.md docs/developer/vision.md docs/developer/control.md`

### Task 3: 归档未落地的非归档视觉设计文档

**Files:**
- Verify archive target: `docs/superpowers/specs/archive/PR#25/2026-04-06-vision-minimal-text-protocol-design.md`
- Verify archive target: `docs/superpowers/plans/archive/PR#25/2026-04-06-vision-minimal-text-protocol-implementation-plan.md`

- [ ] 按 `superpowers-doc-archive` 规则，将两份 2026-04-06 文档归入时间最近的已合并 `PR#25` 桶。
- [ ] 确认 `docs/superpowers/specs/archive/PR#25/2026-04-06-vision-minimal-text-protocol-design.md` 已归档到位。
- [ ] 确认 `docs/superpowers/plans/archive/PR#25/2026-04-06-vision-minimal-text-protocol-implementation-plan.md` 已归档到位。
- [ ] 运行核对命令，按文件路径检查根目录下是否还保留这两份源文件：`rg --files docs/superpowers/specs docs/superpowers/plans | rg "^docs/superpowers/(specs/2026-04-06-vision-minimal-text-protocol-design\.md|plans/2026-04-06-vision-minimal-text-protocol-implementation-plan\.md)$"`

### Task 4: 做最终一致性检查

**Files:**
- Verify only

- [ ] 通读本轮改动后的规则入口正文与开发文档，确认现状正文全部采用只描述当前事实的口吻。
- [ ] 运行变更范围检查，确认本轮只触及计划内文档，且 `AGENTS.md` 未被修改：`git diff --name-only`
- [ ] 再次运行关键内容搜索，确认当前生效文档中不再把 `UART8`、`v/s`、完整框、`camera_id/category`、多检测结果写成当前已落地事实。
- [ ] 记录无法通过主机侧命令验证的部分，只保留“文档与代码事实一致”这一轮结论，不扩展到协议实现完成的表述。

## 自检要点

- 计划覆盖了 Spec 中的全部硬边界：规则入口正文、开发文档、非归档 superpowers 文档、`AGENTS.md` 排除项。
- 计划没有把运行时代码修改、测试补强或协议实现瘦身混入本轮。
- 计划中的现状核对都以当前代码事实为准，不依赖历史叙述。
