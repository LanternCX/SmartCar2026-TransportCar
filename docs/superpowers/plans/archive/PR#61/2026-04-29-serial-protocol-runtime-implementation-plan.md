# 串口协议运行时代码实现 Plan

执行状态：Archive（已由 `2026-04-29-short-packet-runtime-architecture-plan.md` 覆盖）
创建日期：2026-04-29
对应 Spec：`docs/superpowers/specs/archive/PR#61/2026-04-29-serial-protocol-runtime-implementation-spec.md`
归档说明：本 Plan 保留为早期实现计划记录，执行口径以 `docs/superpowers/plans/archive/PR#61/2026-04-29-short-packet-runtime-architecture-plan.md` 为准。下方未勾选项不作为当前执行状态。

## 目标

把运行时代码全量迁移到 `docs/developer/protocol.md` 中的 `v/s/a/o/r` 短包协议，删除键值速度字段、车端通用查询和其他历史协议入口。

## 执行方式

本 Plan 面向分任务执行。每个 Task 都应该独立完成 RED -> GREEN -> REFACTOR，并在进入下一个 Task 前完成对应测试验证。

本次不做 git commit；若后续需要提交，提交前先确认 commit message。

Review 强约束：本次是全量迁移到新协议，不是在旧协议旁边追加新协议。任何只服务历史协议的实现、入口、测试和说明都应删除或改写，不能作为正式可用路径保留。协议层不得把短包转换成旧键值命令字符串来复用历史链路。

## 文件变更范围

- 删除：`src/command/commands/query_enc.py`
- 删除：`src/command/commands/query_health.py`
- 删除：`src/command/commands/query_imu.py`
- 删除：`src/command/commands/query_lock.py`
- 删除：`src/command/commands/query_motor.py`
- 删除：`src/command/commands/query_pos.py`
- 删除：`src/command/commands/query_tick.py`
- 修改：`src/command/commands/__init__.py`
- 修改：`src/command/router.py`
- 修改：`src/core/runtime.py`
- 修改：`src/core/diagnostics.py`
- 新增：`src/vision/serial_protocol.py`
- 修改：`src/vision/assistant/velocity_packet.py`
- 修改：`src/vision/assistant/follow_runtime.py`
- 修改：`src/vision/master/forward_runtime.py`
- 新增：`tests/unit/vision/test_serial_protocol.py`
- 修改：`tests/unit/vision/test_assistant_velocity_packet.py`
- 修改：`tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- 修改：`tests/unit/runtime/test_master_forward_runtime.py`
- 修改：`tests/unit/core/test_runtime_uart_flow.py`
- 修改：`tests/unit/core/test_runtime_public_api.py`
- 修改：`tests/unit/core/test_diagnostics.py`
- 修改：`tests/unit/command/test_non_query_command_reply.py`
- 新增：`tests/contract/protocol/test_serial_short_packet_protocol_contract.py`

---

## Task 1：车端通用查询协议退役

### 目标

删除已退役的车端通用查询运行时代码，避免新协议实现继续被旧 `?query` 协议面牵制。

### 文件

- 删除：`src/command/commands/query_enc.py`
- 删除：`src/command/commands/query_health.py`
- 删除：`src/command/commands/query_imu.py`
- 删除：`src/command/commands/query_lock.py`
- 删除：`src/command/commands/query_motor.py`
- 删除：`src/command/commands/query_pos.py`
- 删除：`src/command/commands/query_tick.py`
- 修改：`src/command/commands/__init__.py`
- 修改：`src/command/router.py`
- 修改：`src/core/runtime.py`
- 修改：`src/core/diagnostics.py`
- 修改：`tests/unit/core/test_runtime_uart_flow.py`
- 修改：`tests/unit/core/test_runtime_public_api.py`
- 修改：`tests/unit/core/test_diagnostics.py`
- 修改：`tests/unit/command/test_non_query_command_reply.py`
- 修改：`tests/unit/runtime/test_master_forward_runtime.py`
- 修改：`tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- 修改：`tests/unit/vision/test_assistant_velocity_packet.py`

### 步骤

- [ ] 写失败测试或改写现有测试：`?health` 不再路由到通用查询回复。
- [ ] 写失败测试或改写现有测试：未知 `?xxx` 不再返回 `?unknown=xxx`。
- [ ] 写失败测试或改写现有测试：非查询命令仍不产生回复。
- [ ] 删除 `query_*.py` 文件。
- [ ] 修改命令自动发现逻辑，只加载 `cmd_*.py`。
- [ ] 删除 `CommandRouter.query()` 和 `CommandRouter.handle_query()`。
- [ ] 修改 `TransportCar._handle_uart_line()`，不再把 `?` 开头输入交给查询路由。
- [ ] 删除 `TransportCar.get_query_uart()`。
- [ ] 删除 `format_query_response()`；保留仍被诊断链路使用的格式化函数。
- [ ] 改写涉及 `?health` 透传的主车、辅车测试，使其不再要求查询协议继续可用。
- [ ] 运行 `python3 -m pytest tests/unit/command tests/unit/core -q`。

### 验收

- 正式运行时代码中不再有通用查询处理器。
- `?health/?pos/?imu/?enc/?motor/?tick/?lock` 不再作为正式串口入口。
- 非查询命令处理不退化。
- 角色层诊断快照能力不被误删。

---

## Task 2：短包协议纯解析模块

### 目标

新增不依赖硬件的短包解析能力，先让 `v/s/a/o/r` 格式在纯逻辑层可测试。

### 文件

- 新增：`src/vision/serial_protocol.py`
- 新增：`tests/unit/vision/test_serial_protocol.py`

### 步骤

- [ ] 写失败测试：`parse_short_packet("v,1.25,-0.5,0.75")` 返回速度字段和 `has_omega=True`。
- [ ] 写失败测试：`parse_short_packet("v,1.25,-0.5")` 返回速度字段和 `has_omega=False`。
- [ ] 写失败测试：`parse_short_packet("s,12,3,1,0")` 返回同步字段。
- [ ] 写失败测试：`parse_short_packet("a,12")` 返回 ACK 字段。
- [ ] 写失败测试：`parse_short_packet("r,12,2,-1")` 返回事件字段。
- [ ] 写失败测试：`parse_short_packet("o,12,1.0,-0.5,3.0")` 返回观测字段。
- [ ] 写失败测试：非法字段数量、非法数字、越界 `seq` 返回 `None`。
- [ ] 实现 `parse_short_packet()`。
- [ ] 实现 `format_velocity_packet()`、`format_state_sync_packet()`、`format_ack_packet()` 和 `format_event_packet()`。
- [ ] 实现 `is_newer_seq()`，按 `0..255` 环形序号判断新旧。
- [ ] 运行 `python3 -m pytest tests/unit/vision/test_serial_protocol.py -q`。

### 验收

- 纯解析测试通过。
- 模块不依赖硬件对象、不读取串口、不修改运行时状态。
- 模块覆盖 `docs/developer/protocol.md` 中定义的正式短包类型。

---

## Task 3：键值速度入口退役与 `v` 速度短包接入

### 目标

让速度解析入口只接受正式 `v,<vx>,<vy>[,<omega>]` 短包，不再把 `vx=...` 等键值字段作为正式串口速度协议。

### 文件

- 修改：`src/vision/assistant/velocity_packet.py`
- 修改：`tests/unit/vision/test_assistant_velocity_packet.py`

### 步骤

- [ ] 写失败测试：`split_velocity_line("v,1.25,-0.5,0.75")` 返回 accepted，解析出 `vx/vy/omega`。
- [ ] 写失败测试：`split_velocity_line("v,1.25,-0.5")` 返回 accepted，`omega=0.0`。
- [ ] 写失败测试：`split_velocity_line("vx=1,vy=2")` 不再返回 accepted。
- [ ] 写失败测试：`v` 短包处理过程中不会生成 `vx=...`、`vy=...`、`omega=...` 旧键值命令字符串。
- [ ] 写失败测试：非法 `v` 短包返回 invalid，不能透传成普通命令执行。
- [ ] 在 `velocity_packet.py` 中接入 `parse_short_packet()`，返回结构化速度值。
- [ ] 删除或改写键值速度字段测试。
- [ ] 运行 `python3 -m pytest tests/unit/vision/test_assistant_velocity_packet.py -q`。

### 验收

- `v` 短包可被速度解析入口接受。
- 键值速度字段不再作为正式速度入口。
- 测试不继续锁定键值速度协议。

---

## Task 4：主车 `UART3` 输入和 `UART8` 速度转发迁移

### 目标

主车从 `UART3` 消费 `v` 包，并通过 `UART8` 转发 `v` 包；不再从键值字段派生 `angle` 转发。

### 文件

- 修改：`tests/unit/runtime/test_master_forward_runtime.py`
- 修改：`src/vision/master/forward_runtime.py`

### 步骤

- [ ] 写失败测试：`UART3` 收到 `v,1.0,-2.5,0.5` 后，主车本地底盘接收等效速度输入。
- [ ] 写失败测试：主车本地执行速度时不调用旧键值命令字符串入口。
- [ ] 写失败测试：`UART3` 收到 `v,1.0,-2.5,0.5` 后，`UART8` 写出 `v,1.0,-2.5,0.5\r\n`。
- [ ] 写失败测试：`UART3` 收到 `vx=1.0,vy=2.0` 后不再转发到 `UART8`。
- [ ] 写失败测试：`UART3` 收到 `omega=...` 后不再派生 `angle=...` 转发。
- [ ] 修改主车行处理逻辑，识别 `v` 包并以结构化速度值驱动本地运行时，同时转发正式短包。
- [ ] 保留非协议底盘入口需要的内部调用，但不得把键值文本作为串口正式入口。
- [ ] 运行 `python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`。

### 验收

- 主车速度输入和转发都使用 `v` 包。
- 键值速度字段和 `angle` 派生转发不再作为正式路径。
- 主车不装配视觉输入分支的既有职责不变。

---

## Task 5：辅车 `UART8/UART6` 速度短包运行时接入

### 目标

确认短包速度进入实际辅车运行时后，仍遵守当前两路输入职责。

### 文件

- 修改：`tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- 修改：`src/vision/assistant/follow_runtime.py`

### 步骤

- [ ] 写失败测试：`UART8` 收到 `v,1.0,2.0,0.5`，辅车最终速度包含 `omega=0.5`。
- [ ] 写失败测试：`UART6` 收到 `v,0.25,-0.5,9.0`，辅车只贡献 `vx/vy`，不贡献 `omega`。
- [ ] 写失败测试：`UART8` 和 `UART6` 同时使用 `v` 短包时，`vx/vy` 按现有规则相加。
- [ ] 写失败测试：`UART8` 或 `UART6` 收到键值速度字段时，不作为正式速度输入更新。
- [ ] 修改 `follow_runtime.py`，只把正式 `v` 包纳入速度融合，并避免把短包改写成旧键值命令字符串。
- [ ] 运行相关辅车速度测试。

### 验收

- `UART8` 可通过 `v` 包携带角速度。
- `UART6` 仍只作为视觉平移修正入口。
- 两路速度融合规则不改变。
- 键值速度字段不再作为正式路径。

---

## Task 6：辅车状态同步接收与 ACK

### 目标

让辅车在双向 `UART8` 上处理 `s` 同步包，并按协议回复 `a`。

### 文件

- 修改：`tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- 修改：`src/vision/assistant/follow_runtime.py`

### 步骤

- [ ] 写失败测试：辅车收到 `s,12,3,1,0` 后记录当前同步上下文。
- [ ] 写失败测试：辅车收到 `s,12,3,1,0` 后向 `UART8` 写出 `a,12\r\n`。
- [ ] 写失败测试：重复收到相同 `s` 包时重复 ACK，但不重复应用状态。
- [ ] 写失败测试：收到旧 `seq` 的 `s` 包时不回退同步上下文。
- [ ] 在 `AssistantFollowRuntime` 中增加最小同步状态字段。
- [ ] 在 `UART8` 行处理处识别 `s` 包并调用同步处理函数。
- [ ] 保持 `UART6` 不处理状态同步包。
- [ ] 运行相关辅车运行时测试。

### 验收

- 新同步会记录并 ACK。
- 重复同步只 ACK，不重复应用。
- 旧同步不会回退状态。
- `UART6` 不承担状态同步职责。

---

## Task 7：主车状态同步发送与 ACK 完成

### 目标

让主车具备最小“通过 UART8 重复发送直到 ACK”的状态同步能力。

### 文件

- 修改：`tests/unit/runtime/test_master_forward_runtime.py`
- 修改：`src/vision/master/forward_runtime.py`

### 步骤

- [ ] 写失败测试：调用同步请求入口后，下一次 `step()` 向 `UART8` 写出 `s,<seq>,<state>,<target>,<arg>\r\n`。
- [ ] 写失败测试：未收到 ACK 时，多次 `step()` 会重复写出同一个 `s` 包。
- [ ] 写失败测试：`UART8` 收到匹配 `a,<seq>` 后，后续 `step()` 不再发送该同步包。
- [ ] 写失败测试：`UART8` 收到不匹配 ACK 时，不清除待确认同步。
- [ ] 在 `MasterForwardRuntime` 中新增待确认同步状态。
- [ ] 新增同步请求入口，生成 `seq` 并保存待发送字段。
- [ ] 在 `UART8` 行处理中识别 ACK 包。
- [ ] 在角色周期中发送待确认同步包。
- [ ] 运行相关主车运行时测试。

### 验收

- 主车可启动同步发送。
- 未 ACK 时会重复发送。
- 匹配 ACK 后停止发送。
- 不匹配 ACK 不影响当前同步。

---

## Task 8：主车事件回报 `r` 包记录

### 目标

让主车通过 `UART8` 接收并记录 `r` 事件包，为后续状态机决策留下入口。

### 文件

- 修改：`tests/unit/runtime/test_master_forward_runtime.py`
- 修改：`src/vision/master/forward_runtime.py`

### 步骤

- [ ] 写失败测试：主车通过 `UART8` 收到 `r,12,2,0` 后记录最近事件。
- [ ] 写失败测试：事件包不触发全局状态跳转，也不改写速度命令。
- [ ] 在主车短包处理函数中识别 `r` 包。
- [ ] 保存最近事件字段。
- [ ] 运行相关主车运行时测试。

### 验收

- `r` 包被记录。
- `r` 包不直接改变全局状态。
- 现有速度转发行为不退化。

---

## Task 9：协议契约测试与全量验证

### 目标

确认正式短包协议作为运行时入口存在，并保证现有单元和契约测试不退化。

### 文件

- 新增：`tests/contract/protocol/test_serial_short_packet_protocol_contract.py`

### 步骤

- [ ] 新增契约测试：`v` 短包是正式速度入口。
- [ ] 新增契约测试：`s/a` 是正式状态同步和确认入口。
- [ ] 新增契约测试：`o` 是正式观测包解析入口。
- [ ] 新增契约测试：`r` 是正式事件回报入口。
- [ ] 运行 `python3 -m pytest tests/unit tests/contract -q`。
- [ ] 检查 `docs/developer/protocol.md` 与实现命名一致。
- [ ] 检查没有新增硬件串口、引脚或接线假设。
- [ ] 检查没有恢复车端通用查询作为正式协议主线。
- [ ] 检查 `src/command/commands/query_*.py` 不再存在。
- [ ] 检查查询路由和查询回复格式化能力不再存在。
- [ ] 检查键值速度字段不再作为正式串口速度入口。
- [ ] 检查短包处理链路没有转成旧键值命令字符串。
- [ ] 检查没有任何历史协议实现继续作为正式可用路径保留。
- [ ] 检查测试没有继续固定旧协议入口。

### 验收

- 单元测试通过。
- 契约测试通过。
- 实现范围与 Spec 一致。

---

## 总体验收

- [ ] `UART3`、`UART8`、`UART6` 的速度运行链路使用 `v` 短包。
- [ ] 键值速度字段不再作为正式串口速度入口保留。
- [ ] `s` 包能让辅车更新本地同步上下文并回复 ACK。
- [ ] 重复 `s` 包不重复应用状态。
- [ ] 旧 `s` 包不回退本地同步上下文。
- [ ] 主车能通过 `UART8` 发送 `s` 包，并在收到匹配 ACK 后停止发送。
- [ ] 主车能通过 `UART8` 记录 `r` 包。
- [ ] `o` 包具备解析和契约边界，但不接入具体业务消费。
- [ ] 通用查询处理器、查询路由和查询回复格式化能力已删除。
- [ ] 本地单元测试和协议契约测试通过。
- [ ] 没有新增硬件事实假设。
- [ ] 没有恢复查询主线。
- [ ] 没有引入旧协议兼容层。
- [ ] 没有保留历史实现作为正式可用路径。
- [ ] 没有用测试继续锁定旧协议行为。

## 最终 Review 强约束

- [ ] 运行时代码已全量迁移到 `docs/developer/protocol.md` 的短包协议。
- [ ] 旧协议入口、旧查询入口和旧字段双轨说明没有作为正式路径保留。
- [ ] 为旧协议服务的测试已删除或改写为新协议测试。
- [ ] 所有保留下来的辅助函数都有当前新协议或非协议底盘职责。
- [ ] 文档、注释和测试名称不使用历史性口吻解释旧实现残留。
- [ ] 正式协议文档、代码和测试完全同口径。
- [ ] 协议层没有保留短包到旧键值命令字符串的适配层。
