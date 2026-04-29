# 短包协议运行时架构重构 Plan

执行状态：Archive  
创建日期：2026-04-29  
对应 Spec：`docs/superpowers/specs/2026-04-29-short-packet-runtime-architecture-spec.md`  
前置提交：`a6bca53 refactor(protocol): migrate runtime to short packet protocol`

## 目标

把运行时串口入口从等号命令路由架构重构为短包分发架构，同时保证主车电脑遥控、主车速度前馈、辅车色标视觉跟随和前馈加视觉融合链路行为保持一致。

## 执行方式

本 Plan 面向 Subagent-Driven Development。每个 Task 由独立 subagent 执行，主流程负责调度、审查和集成。

每个 Task 必须包含：

1. RED：先写或改写行为测试，并确认失败原因符合预期。
2. GREEN：实现最小改动让对应测试通过。
3. REFACTOR：清理命名、职责边界和无用路径，保持测试通过。
4. 行为 Review：检查主辅跟随测试场景行为是否保持一致。
5. 架构 Review：检查是否真正采用短包分发和结构化控制入口。

本次不做 git commit；如需提交，提交前先确认 commit message。

## 强约束

- 本次采用完整替换策略，不保留等号命令架构、兼容入口、空壳转接或字段集合驱动路径。
- 正式运行时串口入口只接受 `v/s/a/o/r` 短包。
- 正常路径不允许生成或消费 `key=value` 文本。
- 不允许把短包转成等号命令文本再交给底盘。
- 不允许保留命令注册路由作为运行时主线。
- `vx/vy/omega` 只作为协议位置字段和控制物理量名称存在。
- 位置、角度、复位和安全停止只作为底盘内部结构化控制意图进入，不新增串口字段。
- 行为测试必须证明协议入口变化没有改变底盘控制结果。
- 主辅跟随链路是核心验收场景，局部解析测试通过不能单独作为完成依据。
- 文档和注释迁移不写测试，只做规则检查和 subagent 专项 Review。

## 文件变更范围

预期删除或停止作为运行时依赖：

- `src/command/router.py`
- `src/command/commands/`
- `src/command/policy.py` 中面向字段集合的运行时入口

预期修改：

- `src/core/runtime.py`
- `src/core/diagnostics.py`
- `src/vision/serial_protocol.py`
- `src/vision/master/forward_runtime.py`
- `src/vision/assistant/follow_runtime.py`
- `src/vision/assistant/velocity_packet.py`
- `tests/unit/command/`
- `tests/unit/core/`
- `tests/unit/runtime/`
- `tests/unit/vision/`
- `tests/contract/protocol/`
- `docs/developer/`
- 代码注释、文档字符串和测试说明文本

如某个文件在实现后没有正式职责，应删除而不是保留空壳。文档和注释只描述当前短包协议事实。

---

## Task 1：建立主辅跟随行为基线测试

### 目标

先把核心测试电路固定成行为测试：主车电脑遥控、主车速度前馈、辅车视觉修正、前馈加视觉融合。后续架构重构都以这些行为测试为保护网。

### 文件

- 修改：`tests/unit/runtime/test_master_forward_runtime.py`
- 修改：`tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- 修改：`tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py`
- 修改：`tests/unit/runtime/assistant_follow_runtime_support.py`

### 子任务

- [x] RED：新增主车接收 `UART3` 遥控 `v` 包后本地速度目标保持一致的行为测试。
- [x] RED：新增主车接收 `UART3` 遥控 `v` 包后 `UART8` 前馈输出保持一致的行为测试。
- [x] RED：新增辅车接收 `UART8` 前馈和 `UART6` 视觉修正后融合结果保持一致的行为测试。
- [x] RED：新增 `UART6` 视觉修正只贡献平移速度的行为测试。
- [x] RED：新增缺包保持最新值、显式零包清理对应来源的行为测试。
- [x] GREEN：只调整测试辅助桩，不改生产代码，使基线测试能表达结构化底盘目标。
- [x] REFACTOR：清理测试名称和辅助桩中的等号命令口径，使基线只描述短包入口和底盘行为。
- [x] 运行：`python3 -m pytest tests/unit/runtime -q`，确认基线测试通过。
- [x] 记录后续 Task 需要触发 RED 的行为点，不让 Task 1 以失败测试结束。

### 验收

- 测试名称表达整车行为，不表达旧字段路由过程。
- 正常行为测试不使用等号输入。
- 基线测试可通过，并能作为后续重构的行为保护网。
- 后续 RED 失败原因指向结构化控制入口或短包分发缺失，而不是测试桩自身错误。

### Review 要求

- 行为 Review：确认测试覆盖主车遥控、速度前馈、视觉修正和融合输出。
- 架构 Review：确认测试没有继续固定等号命令路径。

---

## Task 2：建立底盘结构化控制入口

### 目标

让 `TransportCar` 提供面向角色层的结构化控制入口，底盘不再通过串口命令文本或字段集合接收速度目标。

### 文件

- 修改：`src/core/runtime.py`
- 修改：`tests/unit/core/test_runtime_uart_flow.py`
- 修改：`tests/unit/core/test_runtime_public_api.py`
- 修改：`tests/unit/command/test_optional_lock_commands.py`

### 子任务

- [x] RED：新增结构化速度目标写入后底盘当前速度目标保持当前行为的测试。
- [x] RED：新增速度限幅行为测试，确认短包速度值沿用当前限幅边界。
- [x] RED：新增平移速度更新不清除当前角度目标的行为测试。
- [x] RED：新增显式角速度更新清除当前角度目标的行为测试。
- [x] RED：新增复位、安全停止和电机清零行为保持一致的测试。
- [x] GREEN：在 `TransportCar` 内建立结构化速度目标入口和必要的控制状态更新入口。
- [x] GREEN：把字段集合驱动的模式切换改为结构化控制事件。
- [x] REFACTOR：清理 `last_cmd` 中承担命令协议职责的结构；如仍需保留内部控制状态，命名必须表达控制状态而不是串口命令。
- [x] 运行：`python3 -m pytest tests/unit/core tests/unit/command -q`。

### 验收

- 底盘速度入口不接收字符串命令。
- 底盘内部不依赖 `dispatched={"vx", "vy", "omega"}` 这类字段集合驱动模式切换。
- 控制物理量命名保持清晰。
- 底盘行为测试证明速度、角度、复位、安全停止结果保持一致。

### Review 要求

- 行为 Review：确认底盘关键控制结果没有因入口重构而变化。
- 架构 Review：确认结构化入口没有包装调用旧命令路由。

---

## Task 3：重构 `TransportCar` 串口短包分发入口

### 目标

`TransportCar._handle_uart_line()` 只解析正式短包，合法包进入结构化控制入口，非法或未定义输入不进入等号命令路由。

### 文件

- 修改：`src/core/runtime.py`
- 修改：`tests/unit/core/test_runtime_uart_flow.py`
- 修改：`tests/contract/protocol/test_serial_short_packet_protocol_contract.py`

### 子任务

- [x] RED：新增 `v` 包通过 `_handle_uart_line()` 进入结构化速度入口的测试。
- [x] RED：新增 `key=value` 输入无正式行为的测试。
- [x] RED：新增非法短包不会改变底盘控制状态的测试。
- [x] RED：新增 `_handle_uart_line()` 不调用命令路由的测试。
- [x] GREEN：让 `_handle_uart_line()` 只走 `parse_short_packet()` 和短包分发。
- [x] REFACTOR：删除 `_handle_uart_line()` 中与等号命令路由相关的分支。
- [x] 运行：`python3 -m pytest tests/unit/core tests/contract/protocol -q`。

### 验收

- 串口入口不调用命令路由。
- 正常串口速度输入只接受 `v` 包。
- 等号输入只作为拒绝用例存在。

### Review 要求

- 行为 Review：确认 `v` 包进入底盘后的控制结果和 Task 2 行为一致。
- 架构 Review：确认串口入口没有文本适配层。

---

## Task 4：重构主车短包运行时

### 目标

主车角色层采用短包分发和结构化底盘入口：`UART3` 接收遥控 `v` 包，本地执行并通过 `UART8` 转发；`UART8` 处理 `a/r` 包。

### 文件

- 修改：`src/vision/master/forward_runtime.py`
- 修改：`tests/unit/runtime/test_master_forward_runtime.py`

### 子任务

- [x] RED：新增 `UART3` 遥控 `v` 包驱动本地结构化速度入口的测试。
- [x] RED：新增 `UART3` 遥控 `v` 包原样按短包语义写入 `UART8` 的测试。
- [x] RED：新增主车运行时不生成等号命令文本的测试。
- [x] RED：新增 `UART8` 收到匹配 `a` 包后停止同步重发的测试。
- [x] RED：新增 `UART8` 收到 `r` 包后记录事件的测试。
- [x] GREEN：重构主车行处理逻辑为短包分发。
- [x] GREEN：主车速度本地执行直接调用底盘结构化入口。
- [x] REFACTOR：移除主车运行时中等号字段抽取、角速度派生等文本逻辑。
- [x] 运行：`python3 -m pytest tests/unit/runtime/test_master_forward_runtime.py -q`。

### 验收

- 主车电脑遥控行为保持一致。
- 主车速度前馈行为保持一致。
- 主车运行时不调用命令路由、不生成等号文本。
- 主车同步 ACK 和事件记录保持可用。

### Review 要求

- 行为 Review：重点检查主车作为前车的遥控和速度前馈行为。
- 架构 Review：确认主车运行时只依赖短包解析和结构化底盘入口。

---

## Task 5：重构辅车短包运行时

### 目标

辅车角色层采用短包分发和结构化底盘入口：`UART8` 前馈、`UART6` 视觉修正、`UART8` 状态同步和 ACK 都按短包职责处理。

### 文件

- 修改：`src/vision/assistant/follow_runtime.py`
- 修改：`src/vision/assistant/velocity_packet.py`
- 修改：`tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- 修改：`tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py`
- 修改：`tests/unit/runtime/test_assistant_follow_runtime_error_handling.py`
- 修改：`tests/unit/runtime/test_assistant_follow_runtime_public_api.py`

### 子任务

- [x] RED：新增 `UART8` 前馈 `v` 包进入前馈来源的测试。
- [x] RED：新增 `UART6` 视觉 `v` 包进入视觉来源的测试。
- [x] RED：新增两路速度融合后直接调用底盘结构化入口的测试。
- [x] RED：新增辅车运行时不生成等号命令文本的测试。
- [x] RED：新增重复 `s` 包只重复 ACK、不重复应用的测试。
- [x] RED：新增较早同步编号不回退上下文的测试。
- [x] GREEN：重构辅车输入处理为短包分发。
- [x] GREEN：把速度融合结果直接写入底盘结构化入口。
- [x] REFACTOR：删除速度包处理中的透传命令文本概念。
- [x] 运行：`python3 -m pytest tests/unit/runtime/test_assistant_follow_runtime_* -q`。

### 验收

- 辅车色标视觉跟随链路保持一致。
- 前馈加视觉融合行为保持一致。
- `UART6` 只贡献平移速度。
- 状态同步 ACK、重复确认和同步编号判断保持可用。
- 辅车运行时不调用命令路由、不生成等号文本。

### Review 要求

- 行为 Review：重点检查辅车作为后车的前馈、视觉修正和融合输出。
- 架构 Review：确认辅车运行时没有短包到等号命令文本的适配层。

---

## Task 6：移除等号命令路由模块和测试绑定

### 目标

删除或退出运行时主线中的等号命令路由架构，避免新协议继续被原有注册机制牵制。

### 文件

- 删除或停止使用：`src/command/router.py`
- 删除或停止使用：`src/command/commands/`
- 删除或改写：`src/command/policy.py`
- 修改：`tests/unit/command/`
- 修改：`tests/unit/core/`

### 子任务

- [x] RED：新增行为测试，证明删除命令路由后运行时控制结果保持一致。
- [x] RED：改写 `tests/unit/command/`，不再验证等号命令正常路径。
- [x] GREEN：删除不再有正式职责的命令处理器文件。
- [x] GREEN：删除或改写字段集合驱动的 policy 入口。
- [x] REFACTOR：清理导入、文档字符串和测试辅助桩中的等号命令残留。
- [x] Review：通过人工检查确认运行时不依赖 `CommandRouter`，不把该检查作为最终行为测试保留。
- [x] 运行：`python3 -m pytest tests/unit/command tests/unit/core -q`。

### 验收

- 命令注册路由不参与运行时主线。
- `src/command/commands/` 中没有为串口运行协议服务的处理器。
- `tests/unit/command/` 不把等号命令当正常路径固定。
- 如果 `src/command/` 没有正式职责，应删除或只保留明确非运行时用途。

### Review 要求

- 行为 Review：确认删除命令路由后底盘行为测试仍通过。
- 架构 Review：确认没有保留空壳兼容层。

---

## Task 7：收紧协议契约

### 目标

确保协议解析、格式化和契约测试同口径，等号协议只作为拒绝用例出现。

### 文件

- 修改：`tests/contract/protocol/test_assistant_velocity_protocol_contract.py`
- 修改：`tests/contract/protocol/test_serial_short_packet_protocol_contract.py`
- 修改：`tests/unit/vision/test_serial_protocol.py`
- 修改：`tests/unit/vision/test_assistant_velocity_packet.py`
- 修改：`tests/unit/vision/test_assistant_velocity_source_state.py`

### 子任务

- [x] RED：新增契约测试，确认正式短包类型 `v/s/a/o/r` 可解析。
- [x] RED：新增契约测试，确认等号速度文本不属于正式协议。
- [x] RED：新增契约测试，确认速度格式化输出短包而非等号文本。
- [x] GREEN：调整协议测试和速度包测试到短包口径。
- [x] REFACTOR：检查 `vx/vy/omega` 只作为位置字段和物理量说明出现。
- [x] 运行：`python3 -m pytest tests/unit/vision tests/contract/protocol -q`。

### 验收

- 协议解析、格式化和契约测试一致。
- 正常测试不构造等号协议输入。
- 拒绝用例清楚表达等号协议不属于正式入口。

### Review 要求

- 行为 Review：确认协议测试没有替代整车行为测试。
- 架构 Review：确认契约测试没有保留多套正式协议说明。

---

## Task 8：文档与注释语义全量收口

### 目标

正式文档、代码注释、文档字符串和测试说明文本只描述当前短包协议事实。该任务不写行为测试，只做规则检查和 subagent 专项 Review。

### 文件

- 修改：`docs/developer/protocol.md`
- 修改：`docs/developer/control.md`
- 修改：`docs/developer/vision.md`
- 修改：`docs/developer/state.md`
- 修改：`src/core/runtime.py`
- 修改：`src/vision/master/forward_runtime.py`
- 修改：`src/vision/assistant/follow_runtime.py`
- 修改：`src/vision/assistant/velocity_packet.py`
- 修改：相关测试文件中的测试名称和说明文本

### 子任务

- [x] 检查 `docs/developer/` 中是否仍把等号文本描述成正式串口入口。
- [x] 检查运行时代码注释和文档字符串是否仍描述命令路由、字段注册或等号速度入口。
- [x] 检查测试名称和说明文本是否仍把等号命令描述成正常运行路径。
- [x] 修改上述文档和注释，使其只描述短包协议和结构化控制入口。
- [x] 保留 `vx/vy/omega` 作为协议位置字段和控制物理量说明。
- [x] 不为文档和注释改动新增测试。
- [x] 派发 subagent 做文档与注释专项 Review。

### 验收

- 正式文档只描述 `v/s/a/o/r` 短包协议。
- 注释不把等号文本描述成正式串口入口。
- 测试说明不把等号命令描述成正常运行路径。
- 文档和注释只描述当前事实。

### Review 要求

- 文档 Review：确认正式文档没有多套正式协议口径。
- 注释 Review：确认运行时代码注释没有等号协议运行口径。
- 规则 Review：确认文档和注释改动没有使用 TDD，也没有引入行为约束测试。

---

## Task 9：全量验证与最终 Review

### 目标

完成整套验证，确认行为等价、短包原生架构和测试约束全部满足。

### 文件

- 检查：`src/`
- 检查：`tests/`
- 检查：`docs/developer/protocol.md`
- 检查：本 Plan 和对应 Spec

### 子任务

- [x] 运行全量测试：`python3 -m pytest tests/unit tests/contract -q`。
- [x] 检查源码正常路径中不存在 `key=value` 串口文本生成。
- [x] 检查源码运行时入口没有调用命令路由。
- [x] 检查角色层没有把短包转换成等号命令文本。
- [x] 检查 `vx/vy/omega` 没有作为路由 key 或模式切换 key 使用。
- [x] 检查行为测试覆盖主车电脑遥控、主车速度前馈、辅车视觉修正和融合输出。
- [x] 检查文档与注释专项 Review 已通过。
- [x] 检查没有新增硬件事实假设。
- [x] 检查没有新增常驻重型对象或导入期副作用。
- [x] 将 Plan 执行状态更新为 `Archive`。

### 验收

- 全量测试通过。
- 行为 Review 通过。
- 架构 Review 通过。
- 文档与注释专项 Review 通过。
- 对应 Spec 的验收标准全部满足。

### Review 要求

- 行为 Review：以主辅跟随测试电路为核心判断，不以局部解析通过代替整链路行为。
- 架构 Review：确认运行时架构已经适配短包协议，不是在等号命令架构上补适配层。
