# 2026-04-21 车端整仓测试目录整理与系统补强设计

> 状态: Archive
> 当前约束以 `docs/developer/strategy.md`、`docs/developer/tasks.md`、`tests/README.md` 与 `tests/AGENTS.md` 为准。

## 背景

当前仓库测试已经不只存在 `core` 一处混乱。

从现状看:

1. `tests/unit/` 根目录同时混放了入口、运行时、命令、视觉协议辅助等多类测试。
2. `tests/contract/` 根目录同时混放了代码协议契约和文档契约。
3. 单个文件名虽然还能勉强表达主题, 但目录层次无法直接表达模块边界。
4. 后续要在整仓范围内做 TDD 时, 很难快速判断“改这个模块, 应该进哪个目录补回归测试”。

用户这轮目标已经明确:

1. 当前变更先提交后, 继续把整个车端仓库 `tests/` 都整理好。
2. 允许我直接移动现有测试文件位置, 按模块整体重组目录。
3. 不只做目录规划, 而是要真正搬迁并顺手补缺口。
4. 目标是整仓范围内更完整的回归测试和行为测试组织方式。

## 目标

1. 把整个车端仓库 `tests/` 目录按模块重新分层。
2. 让 `tests/unit/` 只承担行为测试与回归测试。
3. 让 `tests/contract/` 只承担协议、文档和对外口径契约。
4. 搬迁过程中补上少量明显缺失的行为测试, 并顺手清理仍然过死的断言。
5. 让后续修改任一模块时, 能直接在对应目录下继续做 TDD。

## 非目标

1. 不整理 Vision 仓库测试。
2. 不重构生产代码目录。
3. 不追求覆盖率数字。
4. 不把整仓所有测试辅助都抽成统一大基类。
5. 不改板端验证流程。

## 方案比较

### 方案一: 整仓按模块整体搬迁, 推荐

做法:

1. 直接重组 `tests/unit/` 和 `tests/contract/`。
2. 现有文件整体搬迁归位。
3. 搬迁时同步清理边界不清和过度约束测试。

优点:

1. 一次把整仓测试结构理顺。
2. 后续最适合继续补测试。
3. 用户感知最直接, 目录边界最清楚。

### 方案二: 只重组 `tests/unit/`

做法:

1. `unit` 先按模块拆目录。
2. `contract` 暂时保持平铺。

问题:

1. 结构仍然割裂。
2. 协议类与文档类 contract 继续混在一起。

本轮不采用。

### 方案三: 只新增新目录, 旧文件尽量不动

做法:

1. 后续新文件放新目录, 旧文件先保留原位。

问题:

1. 目录仍然会长期同时存在新旧两套组织方式。
2. 不能真正解决“测试太乱”。

本轮不采用。

## 推荐方案

本轮采用方案一。

一句话概括:

把整仓 `tests/` 直接重组为“`unit` 按模块分目录, `contract` 按协议与文档分目录”的结构, 并在搬迁过程中补齐少量缺口与清理过度约束。

## 设计细节

### 1. 新目录结构

本轮整理后目录固定为:

1. `tests/unit/core/`
2. `tests/unit/command/`
3. `tests/unit/runtime/`
4. `tests/unit/entry/`
5. `tests/unit/vision/`
6. `tests/contract/protocol/`
7. `tests/contract/docs/`

### 2. 单元测试目录职责

#### `tests/unit/core/`

负责 `src/core/` 的运行时与诊断行为。

#### `tests/unit/command/`

负责 `command.router`、`command.policy` 相关命令语义与行为边界。

当前文件归位:

1. `test_non_query_command_reply.py`
2. `test_optional_lock_commands.py`

#### `tests/unit/runtime/`

负责角色运行时与运行时装配逻辑。

当前文件归位:

1. `test_master_forward_runtime.py`
2. `test_assistant_follow_runtime.py`
3. `test_role_vision_layer_factory.py`

#### `tests/unit/entry/`

负责入口、启动、布局、角色识别与分流。

当前文件归位:

1. `test_main_entry.py`
2. `test_runtime_entry_layout.py`
3. `test_startup_log.py`
4. `test_remote_control_role_dispatch.py`
5. `test_vehicle_role.py`

#### `tests/unit/vision/`

负责当前仓库内仍属于车端的视觉协议辅助和视觉速度解析行为。

当前文件归位:

1. `test_assistant_velocity_packet.py`
2. `test_assistant_velocity_source_state.py`

### 3. 契约测试目录职责

#### `tests/contract/protocol/`

只保留对外协议契约。

当前文件归位:

1. 从 `test_non_query_command_reply_contract.py` 拆出速度协议契约测试。

#### `tests/contract/docs/`

只保留文档事实与文档口径约束。

当前文件归位:

1. `test_openart_protocol_doc_contract.py`
2. `test_optional_lock_protocol_doc_contract.py`
3. 从 `test_non_query_command_reply_contract.py` 拆出的文档口径测试。

### 4. 文件迁移原则

1. 迁移优先保持测试语义不变。
2. 迁移后统一更新 `Path(__file__).resolve().parents[...]` 这类目录推导。
3. 若某个文件内部同时混合不同职责, 则按职责拆分, 而不是整文件照搬。
4. 目录内如确实需要公用辅助, 优先就近放到对应模块目录, 不做整仓大一统辅助层。

### 5. 补测与清理原则

搬迁过程中只顺手做这些高价值整理:

1. 清理仍然明显过度约束的断言。
2. 为新目录中职责过于空洞的模块补少量关键行为测试。
3. 把 contract 中混入的 unit 行为测试或 unit 中混入的 contract 文档测试拉回对应边界。

本轮不做:

1. 大规模新增全新测试体系。
2. 统一重写所有测试桩。
3. 重新设计 `pytest` 配置。

### 6. 完成标准

当以下条件同时满足时, 本轮算完成:

1. 整个车端仓库 `tests/` 已按新目录结构重组。
2. 原先平铺在 `tests/unit/` 根下的测试已归入对应模块目录。
3. `tests/contract/` 已按协议契约与文档契约拆开。
4. 迁移后相关测试通过。
5. 目录职责比当前明显清晰, 并且没有引入新的过度约束测试。
