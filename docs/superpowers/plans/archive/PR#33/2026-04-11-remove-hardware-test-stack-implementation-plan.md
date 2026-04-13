# 移除当前主线硬件测试体系实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 从当前仓库主线中移除 `stage2 / stage3 / HIL` 硬件测试体系，只保留本地自动测试与当前可用的主机侧验证口径。

**Architecture:** 先删除 `tests/hil/` 与所有明确服务于 `stage2 / stage3` 的板端工具入口，再把 `tests/README.md`、`pytest.ini`、当前主文档、任务文档和规则入口统一改成“正式测试体系只保留本地自动测试，板端确认通过用户与 AI 对话协作完成”的口径。历史归档材料保留，不把 archive 与 memory 当作当前正式规则处理。

**Tech Stack:** Git、pytest、Markdown 文档、测试说明与规则入口清理

---

## 文件结构与职责

- Delete: `tests/hil/`
- Delete: `tests/unit/tools/test_run_stage2_smoke.py`
- Delete: `tools/run_device_observe.py`
- Delete: `tools/device_observe_probe.py`
- Delete: `tools/run_stage2_smoke.py`
- Delete: `tools/stage2_smoke_probe.py`
- Delete: `tools/stage2_full_trace_probe.py`
- Modify: `tests/README.md`
- Modify: `pytest.ini`
- Modify: `docs/developer/tasks.md`
- Modify: `docs/developer/strategy.md`
- Modify: `docs/developer/control.md`
- Modify: `.agents/skills/using-rules/references/developer-docs.md`
- Modify: `.agents/skills/using-rules/references/implementation-rules.md`
- Modify: `.agents/skills/using-rules/references/hardware-and-protocol.md`
- Modify: `.agents/skills/project-extension-requesting-code-review/references/review-gates.md`
- Modify: `docs/superpowers/specs/2026-04-11-remove-hardware-test-stack-design.md`
- Modify: `docs/superpowers/plans/2026-04-11-remove-hardware-test-stack-implementation-plan.md`

### Task 1: 删除硬件测试目录与板端工具入口

**Files:**
- Delete: `tests/hil/`
- Delete: `tests/unit/tools/test_run_stage2_smoke.py`
- Delete: `tools/run_device_observe.py`
- Delete: `tools/device_observe_probe.py`
- Delete: `tools/run_stage2_smoke.py`
- Delete: `tools/stage2_smoke_probe.py`
- Delete: `tools/stage2_full_trace_probe.py`

- [x] 删除 `tests/hil/` 整个目录, 不保留任何 `HIL` 留证模板、场景文件或附件占位说明。
- [x] 删除 `tests/unit/tools/test_run_stage2_smoke.py`, 不再为已退出的板端工具保留主机侧单测。
- [x] 删除 `tools/run_device_observe.py` 与 `tools/device_observe_probe.py`, 结束当前仓库内 `stage3` 人工调试入口与相关探针。
- [x] 删除 `tools/run_stage2_smoke.py`、`tools/stage2_smoke_probe.py` 与 `tools/stage2_full_trace_probe.py`, 结束当前仓库内 `stage2` 工具入口与相关探针。
- [x] 运行 `python3 -m pytest tests/unit -q` 或当前仓库里仍可独立运行的最小主机侧自动测试命令, 确认删除板端工具后不会直接破坏本地自动测试入口。
- [x] 将这一阶段单独作为一个提交边界, 建议提交主题为 `chore(services): remove hardware test stack entrypoints`。

### Task 2: 收口测试说明与 pytest 口径

**Files:**
- Modify: `tests/README.md`
- Modify: `pytest.ini`

- [x] 更新 `tests/README.md`, 删除 `tests/hil/`、`stage2`、`stage3`、`HIL` 的分层说明与命令示例, 明确当前正式测试体系只保留本地自动测试。
- [x] 在 `tests/README.md` 中补充简短说明: 板端确认不再属于仓库内测试层, 后续通过用户与 AI 对话协作完成。
- [x] 更新 `pytest.ini`, 删除 `hil` marker, 只保留仍然有效的本地自动测试 marker。
- [x] 运行 `python3 -m pytest --markers` 或等效最小检查命令, 确认 `hil` marker 已从当前 pytest 口径退出。
- [x] 若这一部分单独提交, 建议提交主题为 `docs(services): drop hardware test markers and docs`。

### Task 3: 收口当前主文档、任务文档与规则入口

**Files:**
- Modify: `docs/developer/tasks.md`
- Modify: `docs/developer/strategy.md`
- Modify: `docs/developer/control.md`
- Modify: `.agents/skills/using-rules/references/developer-docs.md`
- Modify: `.agents/skills/using-rules/references/implementation-rules.md`
- Modify: `.agents/skills/using-rules/references/hardware-and-protocol.md`
- Modify: `.agents/skills/project-extension-requesting-code-review/references/review-gates.md`

- [x] 更新 `docs/developer/tasks.md`, 删除或改写当前仍把 `HIL` 作为现行交付项的条目, 例如把“补 HIL 记录模板/证据”改成更一般的“结果记录/人工复盘”。
- [x] 更新 `docs/developer/strategy.md` 与 `docs/developer/control.md`, 删除把 `stage2 / stage3 / HIL` 当作当前正式验证要求的表述, 统一成“本地自动测试保留, 板端确认通过对话协作完成”。
- [x] 更新 `.agents/skills/using-rules/references/developer-docs.md`, 避免后续新会话继续从当前主文档推出“仍需维护硬件测试体系”的结论。
- [x] 更新 `.agents/skills/using-rules/references/implementation-rules.md` 与 `.agents/skills/project-extension-requesting-code-review/references/review-gates.md`, 删除当前仍把 `stage2 / stage3 / HIL` 写成实现或收口硬门禁的表述。
- [x] 更新 `.agents/skills/using-rules/references/hardware-and-protocol.md`, 将仍以 `HIL` 命名的现行证据表述改成更一般的“板端确认/现场确认”口径。
- [x] 运行 `python3 -m pytest tests/unit -q` 或当前仍可稳定运行的最小主机侧自动测试命令, 确认文档与规则口径收口后, 仓库仍保留本地自动测试主线。

### Task 4: 收口 spec/plan 记录并做最终自洽验证

**Files:**
- Modify: `docs/superpowers/specs/2026-04-11-remove-hardware-test-stack-design.md`
- Modify: `docs/superpowers/plans/2026-04-11-remove-hardware-test-stack-implementation-plan.md`

- [x] 在 `docs/superpowers/specs/2026-04-11-remove-hardware-test-stack-design.md` 中把状态改成 `archive`, 表明这轮设计已经落地完成。
- [x] 在本计划文件中勾选所有已完成步骤, 保留“删除板端测试体系、保留本地自动测试”的执行记录。
- [x] 用 `grep` 或等效检查重新扫描当前主线文件, 确认 `tests/README.md`、`pytest.ini`、`docs/developer/*.md`、`using-rules` 引用页和收口门禁里不再把 `stage2 / stage3 / HIL` 写成现行正式测试要求。
- [x] 再运行一次本轮选定的最小主机侧自动测试命令, 作为最终验证证据。
