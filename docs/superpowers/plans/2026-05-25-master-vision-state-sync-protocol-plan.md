# 主车视觉状态同步协议结构实施 Plan

> 执行状态: Archive
> 关联 Spec: `docs/superpowers/specs/2026-05-25-master-vision-state-sync-protocol-design.md`
> 执行方式: 默认使用 Subagent-Driven Development 逐任务执行
> 文档任务: 只作为手动触发项, 不进入默认开发流程

## 1. 目标

将主车视觉通信结构调整为“车端同步任务, 视觉按任务输出速度或事件”的模型, 与辅车任务切换思路对齐。主车保留上下文编号, 用于识别过期视觉事件并避免误触发当前任务。

## 2. 执行边界

- 默认开发流程只执行第 4 节中的任务。
- 第 5 节文档任务只在用户明确要求时执行。
- Plan 只作为任务编排说明, 不包含实现代码。
- 协议层相关实现改动前必须先完成行为测试基线盘点。
- 如果现有行为测试不足以证明三端协议行为, 先补齐测试, 再改实现。
- 每个开发任务执行前先写或调整对应测试。
- 每个开发任务完成后运行本任务相关测试。
- 涉及 commit 前必须先向用户确认 commit message, 不自动提交。
- 使用 `uv run pytest ...` 执行测试。
- 不修改硬件串口号、引脚、电平或接线事实。
- 不改变底盘控制核心、运动学、PID、编码器和 IMU 逻辑。
- 不保留两套主车视觉任务切换语义。
- 默认开发流程包含附属视觉仓库 `../SmartCar2026-Vision` 的主车入口调整。

## 3. 目标文件边界

### 3.1 预期新增或调整的共享通信文件

- `src/vision/velocity_packet.py`: 承载主车与辅车共用的速度短包解析、限幅和消费结果定义。
- `src/vision/uart_line_reader.py`: 承载主车与辅车共用的串口按行读取、缓存上限和坏包处理机制。
- `src/vision/reliable_channel.py`: 承载可靠短包待确认、重发、确认匹配和重复确认所需的通用机制。

若实现阶段发现某个共享文件职责过小, 可以合并到同一共享模块, 但不得回到主车和辅车各自复制一套通信基础逻辑。

### 3.2 预期修改的角色运行时文件

- `src/vision/master/forward_runtime.py`: 主车视觉任务同步、主车视觉速度和事件处理、主车 `UART3/UART6/UART8` 输入基础能力复用。
- `src/vision/assistant/follow_runtime.py`: 复用共享速度解析和读行能力, 修正重复同步幂等行为。
- `src/vision/master/uart8_packet.py`: 若仍保留, 只负责主车 `UART8` 方向上的轻量包解析边界。
- `src/vision/assistant/uart8_packet.py`: 若仍保留, 只负责辅车状态同步和事件轻量包边界。
- `src/protocol/packet.py`: 只在通用短包格式需要补齐契约时调整。

### 3.3 预期测试文件

- `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`
- `tests/contract/serial_protocol/test_assistant_velocity_protocol_contract.py`
- `tests/unit/runtime/test_master_forward_runtime.py`
- `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- `tests/unit/runtime/test_assistant_follow_runtime_error_handling.py`
- `tests/unit/vision/test_assistant_state_machine.py`

必要时新增聚焦共享通信机制的单元测试文件, 文件名应表达被测职责, 不新增泛化测试入口。

### 3.4 视觉仓库文件边界

- `../SmartCar2026-Vision/master/main.py`: 主车 OpenART 状态同步接收、视觉任务切换、速度输出和事件回报。
- `../SmartCar2026-Vision/tests/unit/test_master_hook_protocol.py`: 主车视觉任务切换、上下文、事件和图像路径行为测试。
- `../SmartCar2026-Vision/tests/contract/test_main_vision_protocol_contract.py`: 主车视觉协议契约测试。
- `../SmartCar2026-Vision/README.md`: 仅在手动文档任务中处理, 不进入默认开发流程。

## 4. 默认开发任务

### Task 0: 协议行为测试基线补全

**目标**

在协议层实现改动前, 先确认车端主车、车端辅车和主车视觉端已有足够行为测试。若覆盖不足, 先补齐测试, 让后续协议结构调整有明确行为基线。

**范围**

- 盘点当前车端主车运行时协议行为测试。
- 盘点当前车端辅车运行时协议行为测试。
- 盘点当前车端协议契约测试。
- 盘点附属视觉仓库主车 OpenART 协议行为测试。
- 补齐缺失的行为测试和契约测试。
- 不改协议实现和运行时行为。

**必须覆盖的行为基线**

- 主车车端发送主车视觉任务同步。
- 主车车端处理视觉确认、重发和过期事件。
- 主车车端只接受当前上下文事件推进状态。
- 主车视觉速度在允许状态写入底盘。
- 辅车车端处理 `UART8` 子状态同步。
- 辅车车端重复同步只确认, 不重复执行进入状态副作用。
- 辅车车端速度前馈与视觉修正融合行为保持稳定。
- 主车视觉端处理状态同步、重复同步和较早上下文。
- 主车视觉端输出 `v,<vx>,<vy>`。
- 主车视觉端输出带上下文的可靠事件。
- 主车视觉端按确认包清理待确认事件。
- 主车视觉格式和辅车轻量同步格式不会互相误解析。

**测试**

- 缺失的测试补到现有最贴近的测试文件中。
- 若现有测试文件职责不适合, 新增聚焦协议行为的测试文件。
- 测试名称必须表达具体行为, 避免只按实现函数命名。
- 对应未来行为变化的测试应能在当前实现下暴露差异。
- 对应不应变化的行为测试应在当前实现下通过。

**验证**

- `uv run pytest tests/unit/runtime/test_master_forward_runtime.py -q`
- `uv run pytest tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py -q`
- `uv run pytest tests/contract/serial_protocol -q`
- `cd ../SmartCar2026-Vision && uv run pytest tests/unit/test_master_hook_protocol.py tests/contract/test_main_vision_protocol_contract.py -q`

**Review 检查**

- 没有修改协议实现或运行时行为。
- 行为测试覆盖三端协议边界。
- 测试能区分“任务同步语义变化”和“不应变化的速度/事件格式”。
- 后续 Task 1 到 Task 4 可以引用这些测试作为行为基线。

### Task 1: 通信基础能力共享化

**目标**

建立主车与辅车共用的通信基础入口, 让速度解析、串口按行读取和可靠重发机制有一个正式维护位置。

**前置条件**

- Task 0 已完成。
- 协议行为基线测试已经能证明当前应保留行为。

**范围**

- 从辅车现有速度解析中抽出共享速度包处理能力。
- 从主车和辅车现有读行逻辑中抽出共享串口读行能力。
- 抽出可靠短包发送节流、待确认状态、重发判断和确认匹配的共享机制。
- 保持共享层不持有主车或辅车业务状态机。

**测试**

- 添加共享速度解析测试, 覆盖合法 `v` 包、非法 `v` 包、非速度短包忽略、速度限幅和 `omega` 可选语义。
- 添加串口读行测试, 覆盖完整行、半行缓存、超长输入、解码失败和读取异常。
- 添加可靠通道测试, 覆盖首次发送、未到重发间隔不发送、到达重发间隔重发、确认匹配清理和确认不匹配保留。

**验证**

- `uv run pytest tests/contract/serial_protocol -q`
- `uv run pytest tests/unit/vision -q`

**Review 检查**

- 共享层只提供机制, 不包含主车或辅车业务状态。
- 没有新增重型常驻对象或导入期副作用。
- 主车和辅车后续可以通过该共享层替换各自重复逻辑。

### Task 2: 主车视觉任务同步重构

**目标**

将主车 `UART6` 视觉任务切换整理为状态同步驱动模型。主车状态机创建视觉任务上下文, 主车 RT1021 同步给主车 OpenART, 并只接受当前上下文中的视觉事件。

**前置条件**

- Task 0 已完成。
- Task 1 已完成。
- 主车车端相关行为测试已覆盖任务同步、确认、重发、过期事件和速度写入。

**范围**

- 主车进入搜索、搬运入口对正、搬运结束判定时创建视觉任务同步。
- 主车 `UART6` 同步包表达 `context/state/target/arg`。
- 主车收到视觉确认后清理待确认同步。
- 未收到确认时按可靠间隔重发。
- 主车视觉速度只在允许状态写入底盘。
- 主车视觉事件必须匹配当前上下文才能推进主车状态机。
- 过期上下文事件需要确认, 但不推进主车状态机。
- 状态切换时清理上一任务的视觉速度缓存。

**测试**

- 覆盖进入搜索任务时发送视觉任务同步。
- 覆盖视觉确认清理待确认同步。
- 覆盖同步重发。
- 覆盖视觉速度写入底盘的允许状态。
- 覆盖当前上下文事件推进状态。
- 覆盖过期上下文事件只确认不推进状态。
- 覆盖重复事件只确认不重复推进状态。
- 覆盖状态切换后上一任务速度缓存被清理。

**验证**

- `uv run pytest tests/unit/runtime/test_master_forward_runtime.py -q`
- `uv run pytest tests/contract/serial_protocol/test_serial_packet_protocol_contract.py -q`

**Review 检查**

- 主车视觉任务切换只有一种正式语义。
- 主车全局状态机仍是任务决策方。
- 主车 OpenART 仍只被视为速度和事件来源。
- 不把辅车轻量状态同步格式强行套到主车事件载荷上。

### Task 3: 视觉仓库主车入口同步调整

**目标**

让 `../SmartCar2026-Vision/master` 的主车 OpenART 入口与车端主车状态同步模型一致。视觉端接收车端同步的视觉任务, 根据状态和参数切换内部任务, 输出速度或带上下文的可靠事件。

**前置条件**

- Task 0 已完成。
- 主车视觉端相关行为测试已覆盖同步、重复同步、较早上下文、速度输出、事件输出和事件确认。

**范围**

- 主车 OpenART 接收 `context/state/target/arg` 任务同步。
- 主车 OpenART 对同步包返回确认。
- 更新的上下文切换当前视觉任务。
- 重复上下文只确认, 不重复执行进入任务副作用。
- 较早上下文只确认, 不回退当前视觉任务。
- 视觉速度继续输出 `v,<vx>,<vy>`。
- 视觉事件继续携带当前上下文。
- 事件确认继续按可靠序号清理待确认事件。
- 不让视觉端维护主车全局状态机。

**测试**

- 覆盖搜索状态同步后进入搜索任务。
- 覆盖搬运入口对正状态同步后进入对正任务。
- 覆盖搬运结束判定状态同步后进入结束判定任务。
- 覆盖重复同步只确认, 不重置稳定计数、待确认事件或接触判定状态。
- 覆盖较早上下文只确认, 不回退当前任务。
- 覆盖速度输出仍不携带任务名、阶段名或上下文。
- 覆盖事件输出携带当前上下文。
- 覆盖确认包清理匹配的待确认事件。

**验证**

- `cd ../SmartCar2026-Vision && uv run pytest tests/unit/test_master_hook_protocol.py -q`
- `cd ../SmartCar2026-Vision && uv run pytest tests/contract/test_main_vision_protocol_contract.py -q`
- `cd ../SmartCar2026-Vision && uv run pytest tests -q`

**Review 检查**

- 视觉端只根据车端同步任务切换内部视觉任务。
- 视觉端不拥有主车全局状态机。
- 视觉端事件上下文与车端当前上下文语义一致。
- 视觉仓库文档未在默认开发任务中改动。

### Task 4: 辅车通信路径对齐与重复同步幂等修正

**目标**

让辅车复用共享通信基础能力, 并修正重复同步包可能重复执行进入状态副作用的问题。

**前置条件**

- Task 0 已完成。
- Task 1 已完成。
- 辅车车端相关行为测试已覆盖同步幂等、较早同步确认和速度融合。

**范围**

- 辅车 `UART6/UART8` 速度解析改为使用共享速度解析能力。
- 辅车输入读行改为使用共享串口读行能力。
- 辅车可靠同步与事件回报保留现有轻量格式。
- 重复同步包只重复确认, 不重复清空输入、重发本地视觉同步或重置阶段副作用。
- 较早同步包只确认, 不回退辅车子状态。

**测试**

- 覆盖辅车 `FOLLOW` 重复同步只确认一次状态副作用。
- 覆盖辅车 `APPROACH_OBJECT` 重复同步不重复重置本地视觉同步。
- 覆盖辅车 `TRANSPORT_OBJECT` 重复同步不重复清空输入和重置对正流程。
- 覆盖较早同步包确认但不回退状态。
- 覆盖辅车速度融合规则保持稳定。

**验证**

- `uv run pytest tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py -q`
- `uv run pytest tests/unit/runtime/test_assistant_follow_runtime_error_handling.py -q`
- `uv run pytest tests/contract/serial_protocol/test_assistant_velocity_protocol_contract.py -q`

**Review 检查**

- 辅车仍通过 `state/target/arg` 切换本地视觉任务。
- 辅车事件仍按当前子状态解释。
- 共享通信基础能力没有改变辅车速度融合语义。

### Task 5: 集成验证与边界回归

**目标**

确认车端主车、车端辅车、车端协议契约和视觉仓库主车入口在同一套通信语义下整体稳定。

**范围**

- 运行主车运行时测试。
- 运行辅车运行时测试。
- 运行协议契约测试。
- 运行视觉仓库主车入口测试。
- 检查主车与辅车包格式不会互相误解析。
- 检查没有遗留重复速度解析或重复读行逻辑作为正式入口。

**测试**

- 主车运行时全量测试。
- 辅车运行时全量测试。
- 串口协议契约测试。
- 视觉相关单元测试。
- 视觉仓库主车入口测试。

**验证**

- `uv run pytest tests/unit/runtime -q`
- `uv run pytest tests/unit/vision -q`
- `uv run pytest tests/contract/serial_protocol -q`
- `uv run pytest tests/unit tests/contract -q`
- `cd ../SmartCar2026-Vision && uv run pytest tests/unit/test_master_hook_protocol.py tests/contract/test_main_vision_protocol_contract.py -q`
- `cd ../SmartCar2026-Vision && uv run pytest tests -q`

**Review 检查**

- 所有默认开发任务的行为验收点都已覆盖, 包含附属视觉仓库主车入口。
- 没有新增硬件事实假设。
- 没有把文档更新混入默认开发任务。
- 若进入板端联调, 需另行确认设备、上传、模块导入和现场动作验证步骤。

## 5. 手动触发文档任务

本节只在用户明确要求时执行, 不进入默认开发流程。

### Manual Task D1: 开发文档同步

**目标**

将当前正式协议和视觉职责同步到开发文档, 不保留两套主车视觉任务切换说明。

**范围**

- `docs/developer/protocol.md`: 描述主车视觉状态同步、上下文事件、辅车轻量状态同步和二者边界。
- `docs/developer/vision.md`: 描述主车 OpenART 和辅车 OpenART 的任务切换职责。
- `docs/developer/state.md`: 如状态编号或事件说明需要补齐, 只补当前事实。
- 必要时更新相关规则引用, 不新增历史解释。

**检查**

- 文档只描述当前事实。
- 文档不使用历史性口吻。
- 文档不维护双轨说明。
- 文档与行为测试覆盖的协议语义一致。

## 6. 执行顺序

1. Task 0: 协议行为测试基线补全。
2. Task 1: 通信基础能力共享化。
3. Task 2: 主车视觉任务同步重构。
4. Task 3: 视觉仓库主车入口同步调整。
5. Task 4: 辅车通信路径对齐与重复同步幂等修正。
6. Task 5: 集成验证与边界回归。
7. Manual Task D1: 用户手动要求后执行。

Task 0 是所有协议层实现改动的前置任务。Task 1 是车端通信共享化的前置任务。Task 2 和 Task 3 需要在同一轮语义下保持一致。Task 4 可在 Task 1 完成后执行, 但 Task 5 必须最后执行。

## 7. Subagent 执行规则

- 每个默认开发任务由独立 subagent 执行。
- 每个 subagent 只接收当前任务、关联 Spec、相关文件边界和验证命令。
- 每个任务完成后先做 Spec 符合性 Review。
- Spec Review 通过后再做代码质量 Review。
- Review 发现问题时回到当前任务修正, 不直接进入下一任务。
- 所有默认开发任务完成后再做整体 Review。
- commit 只在用户确认 commit message 后执行。

## 8. 完成标准

- 默认开发任务全部完成。
- 协议层实现改动前已完成行为测试基线补全。
- 主车视觉任务切换采用状态同步驱动模型。
- 附属视觉仓库主车入口采用同一任务同步语义。
- 主车上下文编号仍能防止过期事件误触发当前状态。
- 辅车重复同步幂等行为符合协议语义。
- 主车和辅车通信基础能力只有一个正式维护入口。
- `uv run pytest tests/unit tests/contract -q` 通过。
- `cd ../SmartCar2026-Vision && uv run pytest tests -q` 通过。
- 文档任务未被默认执行, 除非用户明确要求。
