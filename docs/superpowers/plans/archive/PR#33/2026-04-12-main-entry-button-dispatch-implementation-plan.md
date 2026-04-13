# `main.py` 单入口与按钮脚本分发实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans（推荐）或 superpowers:subagent-driven-development 来执行本计划。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**Goal:** 在不扩大运行时改动面的前提下, 把当前仓库正式入口从 `boot.py` 切到 `main.py`, 并把脚本分发改成 `C8/C9` 长按。

**Architecture:** 先用主机侧测试锁住入口边界, 再以最小改动新增 `src/main.py`、删除 `src/boot.py`, 并用临时 `KEY_HANDLER + ticker` 完成长按判定后跳转到现有脚本。脚本主体、运行时主链和底层读写链保持不动, 只同步当前正式文档对入口事实的描述。

**Tech Stack:** Python 3.8+ 主机侧测试、RT1021 MicroPython、`smartcar.ticker`、`seekfree.KEY_HANDLER`

---

## 文件边界

- Create: `src/main.py`
- Delete: `src/boot.py`
- Create: `tests/unit/test_main_entry.py`
- Modify: `tests/unit/test_runtime_entry_layout.py`
- Modify: `docs/developer/strategy.md`
- Modify: `docs/developer/tasks.md`
- Modify: `docs/developer/control.md`

### Task 1: 先锁定入口测试边界

**Files:**
- Create: `tests/unit/test_main_entry.py`
- Modify: `tests/unit/test_runtime_entry_layout.py`

- [ ] 先把现有入口布局测试从“`boot.py` 必须存在”改成“`main.py` 必须存在、`boot.py` 不再是正式入口”。
- [ ] 新增入口规则测试, 只覆盖本轮需要锁住的事实: 使用 `KEY_HANDLER`、默认进入 `remote_control`、`C8` 长按进入 `pid_identify`、`C9` 长按进入 `calibrate_gyro`、同时长按走异常分支、脚本分发不再读取 `D8/D9`。
- [ ] 运行入口相关测试并确认先失败, 失败原因应直接指向当前仓库还没有 `src/main.py` 和新的入口规则。

**Run:** `python3 -m pytest tests/unit/test_runtime_entry_layout.py tests/unit/test_main_entry.py -q`

### Task 2: 以最小改动实现新的 `main.py`

**Files:**
- Create: `src/main.py`
- Delete: `src/boot.py`

- [ ] 在 `src/main.py` 中实现最小入口流程: 启动等待、临时按键扫描、脚本分发、异常启动分支。
- [ ] 长按判定采用 `KEY_HANDLER` + 临时 `ticker` 的一次性入口扫描方式, 判定完成后立即停止, 不把这套扫描链带入后续脚本。
- [ ] 脚本跳转继续复用现有 `script/` 路径, 不重写三份脚本主体。
- [ ] 明确保持 `D8/D9` 不参与脚本分发逻辑。
- [ ] 重新运行入口相关测试并确认通过。

**Run:** `python3 -m pytest tests/unit/test_runtime_entry_layout.py tests/unit/test_main_entry.py -q`

### Task 3: 同步当前正式文档口径

**Files:**
- Modify: `docs/developer/strategy.md`
- Modify: `docs/developer/tasks.md`
- Modify: `docs/developer/control.md`

- [ ] 把当前正式入口口径从 `boot.py` 更新为 `main.py`。
- [ ] 把脚本分发规则更新为 `C8/C9` 长按, 并明确 `D8/D9` 只保留车号识别职责。
- [ ] 删除或改写文档中“`main.py` 单入口仍属于下一轮主题”的相关表述, 避免实现完成后文档继续误导后续会话。

### Task 4: 做最小验证并收口范围

**Files:**
- Verify only

- [ ] 运行当前主机侧单元测试, 确认入口改动没有破坏已有自动测试。
- [ ] 人工检查变更列表, 确认本轮只落在入口、入口测试和相关文档上, 没有顺手扩大到运行时主链。
- [ ] 若当前会话无法直接做真实板端验证, 在结果说明中明确板端确认仍待补, 不把“主机侧通过”误报成“板端已确认”。

**Run:** `python3 -m pytest tests/unit -q`

## 自检要点

- 计划覆盖了 Spec 中的全部硬约束: `main.py` 单入口、`KEY_HANDLER` 长按、`C8/C9` 分发、`D8/D9` 退出脚本分发、最小测试保护网、文档同步。
- 计划没有把脚本主体重构、主辅目录重排、控制链改写或大规模测试补齐混入本轮。
- 计划只提供执行边界、文件落点和验证命令, 不额外扩大实现范围。
