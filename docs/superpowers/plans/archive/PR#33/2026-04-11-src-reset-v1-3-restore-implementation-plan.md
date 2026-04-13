# 清空当前 `src` 并恢复 `v1.3.0` 主线实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 把当前仓库从 `legacy / master / assistant` 并存结构切回单一 `src/`，并以 donor `v1.3.0` 重新建立当前正式主线。

**Architecture:** 先在仓库外固化当前重构代码的参考副本，再删除当前 `src` 下三套运行结构及其绑定测试面，随后把 `../SmartCar2026-TransportCar-donor/src/` 原样恢复到当前仓库的 `src/`。部署工具和当前有效文档只同步到“单一 `src/` 主线”这一事实，不提前混入 3.0 入口适配、按钮分发或串口优化。

**Tech Stack:** Git、MicroPython、pytest、mpy-cli、目录对比与文件同步

---

## 文件结构与职责

- Create（仓库外参考）: `../SmartCar2026-TransportCar-refactor-backup/`
- Delete: `src/legacy/`
- Delete: `src/master/`
- Delete: `src/assistant/`
- Restore/Create: `src/boot.py`
- Restore/Create: `src/config/`
- Restore/Create: `src/control/`
- Restore/Create: `src/filters/`
- Restore/Create: `src/hardware/`
- Restore/Create: `src/script/`
- Restore/Create: `src/services/`
- Restore/Create: `src/storage/`
- Restore/Create: `src/utils/`
- Delete: `tests/unit/master/`
- Delete: `tests/unit/assistant/`
- Delete: `tests/unit/legacy/`
- Delete: `tests/unit/test_comment_annotation_layout.py`
- Modify: `tests/unit/test_runtime_entry_layout.py`
- Modify: `.mpy-cli.toml`
- Modify: `tools/run_stage2_smoke.py`
- Modify: `tests/unit/tools/test_run_stage2_smoke.py`
- Modify: `docs/developer/strategy.md`
- Modify: `docs/developer/control.md`
- Modify: `docs/developer/tasks.md`
- Modify: `.agents/skills/using-rules/references/developer-docs.md`
- Modify: `docs/superpowers/specs/2026-04-11-src-reset-v1-3-restore-design.md`
- Modify: `docs/superpowers/plans/2026-04-11-src-reset-v1-3-restore-implementation-plan.md`

### Task 1: 固化仓库外参考并重写最小布局检查

**Files:**
- Create（仓库外参考）: `../SmartCar2026-TransportCar-refactor-backup/`
- Delete: `tests/unit/master/`
- Delete: `tests/unit/assistant/`
- Delete: `tests/unit/legacy/`
- Delete: `tests/unit/test_comment_annotation_layout.py`
- Modify: `tests/unit/test_runtime_entry_layout.py`

- [x] 先确认 `../SmartCar2026-TransportCar-donor/` 仍停在 `v1.3.0`，并把当前这套重构代码额外 clone 到 `../SmartCar2026-TransportCar-refactor-backup/`，只作为后续串口修补参考，不再回写当前仓库。
- [x] 删除 `tests/unit/master/`、`tests/unit/assistant/`、`tests/unit/legacy/` 与 `tests/unit/test_comment_annotation_layout.py`，结束对 `legacy / master / assistant` 三套结构的测试绑定。
- [x] 将 `tests/unit/test_runtime_entry_layout.py` 改写为新的单 `src/` 布局检查：`src/boot.py` 存在，`src/config/`、`src/control/`、`src/filters/`、`src/hardware/`、`src/script/`、`src/services/`、`src/storage/`、`src/utils/` 存在，且 `src/legacy/`、`src/master/`、`src/assistant/` 不存在。
- [x] 运行 `python3 -m pytest tests/unit/test_runtime_entry_layout.py -q`，确认新的布局检查会在当前旧结构下先按预期失败，而不是测试本身失效。

### Task 2: 删除当前 `src` 下的三套运行结构

**Files:**
- Delete: `src/legacy/`
- Delete: `src/master/`
- Delete: `src/assistant/`
- Test: `tests/unit/test_runtime_entry_layout.py`

- [x] 删除 `src/legacy/`、`src/master/`、`src/assistant/`，不在当前仓库内保留 `backup/`、`legacy/` 或其它参考副本目录。
- [x] 清理删除后三套结构留下的无效路径和空目录，让当前仓库的 `src/` 进入“待恢复”的单一根目录状态。
- [x] 再次运行 `python3 -m pytest tests/unit/test_runtime_entry_layout.py -q`，确认此时失败原因只剩 donor 目录尚未恢复，而不是旧三套结构仍然残留。
- [x] 将这一阶段单独作为一个提交边界，建议提交主题为 `refactor(services): remove legacy master assistant runtime trees`。

### Task 3: 以 donor `v1.3.0` 恢复新的 `src/`

**Files:**
- Restore/Create: `src/boot.py`
- Restore/Create: `src/config/`
- Restore/Create: `src/control/`
- Restore/Create: `src/filters/`
- Restore/Create: `src/hardware/`
- Restore/Create: `src/script/`
- Restore/Create: `src/services/`
- Restore/Create: `src/storage/`
- Restore/Create: `src/utils/`
- Test: `tests/unit/test_runtime_entry_layout.py`

- [x] 以 `../SmartCar2026-TransportCar-donor/src/` 为唯一主参考，恢复 `src/boot.py` 与 `src/config/`、`src/control/`、`src/filters/`、`src/hardware/`、`src/script/`、`src/services/`、`src/storage/`、`src/utils/`。
- [x] 恢复时保持 donor 原有目录布局、脚本组织和入口方式，不主动引入 `main.py` 单入口、按钮分发、车号识别或串口优化。
- [x] 使用 `diff -qr "src" "../SmartCar2026-TransportCar-donor/src"` 或等效目录对比命令，确认当前 `src/` 与 donor 一致；若有差异，只允许保留本轮明确批准的最小同步。
- [x] 运行 `python3 -m pytest tests/unit/test_runtime_entry_layout.py -q`，确认单一 `src/` 布局检查转绿。
- [x] 将这一阶段单独作为一个提交边界，建议提交主题为 `refactor(services): restore v1.3.0 runtime tree`。

### Task 4: 收口部署工具到单一 `src` 运行根

**Files:**
- Modify: `.mpy-cli.toml`
- Modify: `tools/run_stage2_smoke.py`
- Modify: `tests/unit/tools/test_run_stage2_smoke.py`

- [x] 将 `.mpy-cli.toml` 的 `source_dir` 从 `src/legacy` 改为 `src`，让设备部署默认对齐恢复后的正式运行根。
- [x] 将 `tools/run_stage2_smoke.py` 的 `SUPPORTED_SOURCE_DIRS`、默认 `source_dir` 与命令行帮助统一改为单一 `src` 口径，不再暴露 `src/master` / `src/assistant`。
- [x] 同步更新 `tests/unit/tools/test_run_stage2_smoke.py`，把原本围绕 `src/assistant` 的断言改为围绕 `src` 的单运行根断言。
- [x] 运行 `python3 -m pytest tests/unit/tools/test_run_stage2_smoke.py -q`，确认部署工具已经贴齐新的单一运行根。
- [x] 如果工具口径改动独立，单独形成一个小提交；建议提交主题为 `chore(services): align stage2 smoke source dir with src root`。

### Task 5: 同步当前文档口径并做最终验证

**Files:**
- Modify: `docs/developer/strategy.md`
- Modify: `docs/developer/control.md`
- Modify: `docs/developer/tasks.md`
- Modify: `.agents/skills/using-rules/references/developer-docs.md`
- Modify: `docs/superpowers/specs/2026-04-11-src-reset-v1-3-restore-design.md`
- Modify: `docs/superpowers/plans/2026-04-11-src-reset-v1-3-restore-implementation-plan.md`
- Test: `tests/unit/test_runtime_entry_layout.py`
- Test: `tests/unit/tools/test_run_stage2_smoke.py`
- Test: `tests/contract/test_openart_protocol_doc_contract.py`

- [x] 更新 `docs/developer/strategy.md`，去掉当前阶段仍以 `master / assistant` 为正式主线的表述，改成“当前正式基线是恢复后的 `src/`，3.0 适配另开下一轮”。
- [x] 更新 `docs/developer/control.md`，把面向当前正式结构的路径说明从 `src/legacy/...` 改回 `src/...`，并明确 `main.py` 单入口适配尚未开始。
- [x] 更新 `docs/developer/tasks.md` 与 `.agents/skills/using-rules/references/developer-docs.md`，避免后续新会话继续按 `legacy / master / assistant` 并存结构展开。
- [x] 实施完成后把 `docs/superpowers/specs/2026-04-11-src-reset-v1-3-restore-design.md` 标记为 `archive`，并在本计划中勾选已完成事项，保留这轮“先删除、再恢复”的执行记录。
- [x] 运行 `python3 -m pytest tests/unit/test_runtime_entry_layout.py tests/unit/tools/test_run_stage2_smoke.py tests/contract/test_openart_protocol_doc_contract.py -q`，再执行 `diff -qr "src" "../SmartCar2026-TransportCar-donor/src"`，确认结构验证、工具验证和 donor 对照同时成立。
