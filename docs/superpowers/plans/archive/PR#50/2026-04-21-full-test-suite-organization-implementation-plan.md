# 车端整仓测试目录整理与系统补强实施计划

> 状态: Archive
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> 当前约束以 `docs/superpowers/specs/archive/PR#50/2026-04-21-full-test-suite-organization-design.md`、`docs/developer/strategy.md`、`docs/developer/tasks.md`、`tests/README.md` 与 `tests/AGENTS.md` 为准。

**Goal:** 把整个车端仓库 `tests/` 目录按模块与契约类型重新分层, 并在搬迁过程中补齐少量关键回归测试和行为测试。

**Architecture:** `tests/unit` 只承担运行时行为与回归保护, `tests/contract` 只承担对外协议和文档口径。先建立目标目录, 再按模块整体搬迁现有文件, 对混合职责文件做最小拆分, 最后跑整仓测试验证边界是否清晰且行为保持一致。

**Tech Stack:** Python、pytest、`tests/unit`、`tests/contract`

---

## 文件范围与职责

- 新增目录: `tests/unit/entry/`
- 新增目录: `tests/unit/runtime/`
- 新增目录: `tests/unit/command/`
- 新增目录: `tests/unit/vision/`
- 新增目录: `tests/contract/protocol/`
- 新增目录: `tests/contract/docs/`

- 搬迁: `tests/unit/test_main_entry.py` -> `tests/unit/entry/test_main_entry.py`
- 搬迁: `tests/unit/test_runtime_entry_layout.py` -> `tests/unit/entry/test_runtime_entry_layout.py`
- 搬迁: `tests/unit/test_startup_log.py` -> `tests/unit/entry/test_startup_log.py`
- 搬迁: `tests/unit/test_remote_control_role_dispatch.py` -> `tests/unit/entry/test_remote_control_role_dispatch.py`
- 搬迁: `tests/unit/test_vehicle_role.py` -> `tests/unit/entry/test_vehicle_role.py`

- 搬迁: `tests/unit/test_master_forward_runtime.py` -> `tests/unit/runtime/test_master_forward_runtime.py`
- 搬迁: `tests/unit/test_assistant_follow_runtime.py` -> `tests/unit/runtime/test_assistant_follow_runtime.py`
- 搬迁: `tests/unit/test_role_vision_layer_factory.py` -> `tests/unit/runtime/test_role_vision_layer_factory.py`

- 搬迁: `tests/unit/test_non_query_command_reply.py` -> `tests/unit/command/test_non_query_command_reply.py`
- 搬迁: `tests/unit/test_optional_lock_commands.py` -> `tests/unit/command/test_optional_lock_commands.py`

- 搬迁: `tests/unit/test_assistant_velocity_packet.py` -> `tests/unit/vision/test_assistant_velocity_packet.py`
- 搬迁: `tests/unit/test_assistant_velocity_source_state.py` -> `tests/unit/vision/test_assistant_velocity_source_state.py`

- 拆分: `tests/contract/test_non_query_command_reply_contract.py`
  - 协议类测试 -> `tests/contract/protocol/test_assistant_velocity_protocol_contract.py`
  - 文档类测试 -> `tests/contract/docs/test_runtime_output_doc_contract.py`

- 搬迁: `tests/contract/test_openart_protocol_doc_contract.py` -> `tests/contract/docs/test_openart_protocol_doc_contract.py`
- 搬迁: `tests/contract/test_optional_lock_protocol_doc_contract.py` -> `tests/contract/docs/test_optional_lock_protocol_doc_contract.py`

- 修改: `tests/README.md`
  - 更新新的目录结构和常用测试命令。

## Task 1: 建立目标目录骨架

**Files:**
- Create: `tests/unit/entry/__init__.py`
- Create: `tests/unit/runtime/__init__.py`
- Create: `tests/unit/command/__init__.py`
- Create: `tests/unit/vision/__init__.py`
- Create: `tests/contract/protocol/__init__.py`
- Create: `tests/contract/docs/__init__.py`

- [ ] 建立新的 unit/contract 子目录骨架。
- [ ] 确认新目录名称与职责一一对应。
- [ ] 保持现有 `tests/unit/core/` 结构不动, 只把其他测试归位。

## Task 2: 搬迁入口类与运行时类 unit 测试

**Files:**
- Modify: `tests/unit/test_main_entry.py`
- Modify: `tests/unit/test_runtime_entry_layout.py`
- Modify: `tests/unit/test_startup_log.py`
- Modify: `tests/unit/test_remote_control_role_dispatch.py`
- Modify: `tests/unit/test_vehicle_role.py`
- Modify: `tests/unit/test_master_forward_runtime.py`
- Modify: `tests/unit/test_assistant_follow_runtime.py`
- Modify: `tests/unit/test_role_vision_layer_factory.py`

- [ ] 把入口类、角色识别和角色分流测试搬到 `tests/unit/entry/`。
- [ ] 把角色运行时和角色装配测试搬到 `tests/unit/runtime/`。
- [ ] 修正文件内 `PROJECT_ROOT` / `ROOT` 路径推导。
- [ ] 运行受影响目录测试, 确认行为不变。

## Task 3: 搬迁命令类与视觉辅助类 unit 测试

**Files:**
- Modify: `tests/unit/test_non_query_command_reply.py`
- Modify: `tests/unit/test_optional_lock_commands.py`
- Modify: `tests/unit/test_assistant_velocity_packet.py`
- Modify: `tests/unit/test_assistant_velocity_source_state.py`

- [ ] 把命令层测试搬到 `tests/unit/command/`。
- [ ] 把车端视觉速度解析测试搬到 `tests/unit/vision/`。
- [ ] 修正路径推导与必要导入。
- [ ] 顺手清理仍然明显过死的断言。

## Task 4: 拆分并整理 contract 测试

**Files:**
- Modify: `tests/contract/test_non_query_command_reply_contract.py`
- Modify: `tests/contract/test_openart_protocol_doc_contract.py`
- Modify: `tests/contract/test_optional_lock_protocol_doc_contract.py`

- [ ] 把协议类 contract 测试放入 `tests/contract/protocol/`。
- [ ] 把文档类 contract 测试放入 `tests/contract/docs/`。
- [ ] 拆开当前同时混协议和文档职责的 contract 文件。
- [ ] 确保 contract 文件不再混入 unit 级行为测试。

## Task 5: 更新测试说明并补少量缺口

**Files:**
- Modify: `tests/README.md`
- Modify: 搬迁后的相关测试文件

- [ ] 在 `tests/README.md` 写清新的目录结构。
- [ ] 更新常用命令, 至少覆盖 `tests/unit` 和 `tests/contract`。
- [ ] 只补少量新目录下明显缺的关键行为测试, 不扩大到全面重写。

## Task 6: 全量验证与收口

**Files:**
- Modify: 如上测试与文档文件

- [ ] 运行 `python3 -m pytest tests/unit/core -q` 以确认 `core` 未被迁移影响。
- [ ] 运行 `python3 -m pytest tests/unit -q`。
- [ ] 运行 `python3 -m pytest tests/contract -q`。
- [ ] 复查是否仍有路径错误、职责混杂或明显过度约束。
- [ ] 完成后将本轮 spec / plan 标记为 `Archive`。
