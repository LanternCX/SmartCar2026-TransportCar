# 视觉状态机解耦设计文档

## 背景

当前视觉状态机调试能力已经可用，但实现上存在两类耦合：

1. `src/services/vision_state_machine.py` 同时负责状态跳转与调试文本拼接。
2. `src/services/transport_car.py` 同时维护串口输出细节和视觉状态名称映射。

这导致状态元信息、日志格式和状态机逻辑混在一起，不利于后续扩展新的调试通道、状态查询和状态机结构维护。

## 目标

1. 将视觉调试日志格式化与输出策略迁移到独立模块。
2. 将视觉状态机的状态元信息与迁移原因元信息迁移到独立定义文件。
3. 引入单独的状态注册管理，避免在多个模块重复维护状态名。
4. 保持 `VisionStateMachine` 只负责状态跳转与控制意图计算。
5. 保持现有主机测试与 Stage 2 smoke 可继续通过。

## 非目标

- 不将当前 if/elif 状态推进逻辑改写为解释器式 DSL。
- 不改变现有视觉状态数量、状态 ID 和控制行为。
- 不引入 CPython 专用依赖或 `typing` 运行时依赖。

## 设计决策

### 1. 日志系统独立

- 新增 `src/services/vision_debug.py`。
- 该模块负责：
  - 构造视觉状态迁移事件。
  - 根据状态注册表将事件格式化为 UART 安全文本。
  - 生成可写入串口的调试 sink。
- `TransportCar` 仅保留一个必要接口，用于把最终文本写到 `uart3`。
- `VisionStateMachine` 不再直接拼接日志字符串，而是只生成事件并交给外部 sink。

### 2. 状态机元信息独立

- 新增 `src/services/vision_state_registry.py`，实现状态注册管理。
- 新增 `src/services/vision_state_defs.py`，定义并注册：
  - 视觉状态 ID 与状态名。
  - 迁移原因 ID 与原因名。
- `VisionStateMachine` 和 `TransportCar` 都通过注册表查询状态名，不再各自维护字典。

### 3. 状态机只负责跳转

- `VisionStateMachine` 内部保留统一跳转入口。
- 跳转入口只做三件事：
  - 更新状态。
  - 生成状态迁移事件。
  - 将事件交给调试 sink。
- 跳转入口不负责解释状态名、原因名，也不负责 UART 文本拼接。

## 模块划分

### `src/services/vision_state_registry.py`

- `VisionStateRegistry`
- `VisionStateDefinition`
- `VisionReasonDefinition`
- 提供注册与查询接口。

### `src/services/vision_state_defs.py`

- 定义 `SMState`。
- 定义 `VisionTransitionReason`。
- 在模块导入时完成默认状态与默认原因注册。

### `src/services/vision_debug.py`

- 定义状态迁移事件结构。
- 提供事件格式化函数。
- 提供 UART sink 构造函数。

### `src/services/vision_state_machine.py`

- 保留控制参数、输入快照、控制意图和状态推进逻辑。
- 从独立模块导入状态 ID、原因 ID、注册表和事件构造能力。

### `src/services/transport_car.py`

- 只负责把调试 sink 注入状态机。
- 通过注册表读取视觉状态名。
- 不再持有 `VISION_STATE_NAMES` 和状态迁移字符串细节。

## 风险与缓解

1. 风险：新增模块后 Stage 2 导入链变长。
   - 缓解：只使用基础 Python 语法和已有 `services` 层依赖，不引入 `typing`。
2. 风险：日志 sink 与测试假对象接口不兼容。
   - 缓解：采用最小 callable 协议，测试继续用 `list.append` 或假 UART。
3. 风险：状态名查询位置变化后 `health`/`vision` 快照回归。
   - 缓解：补充注册表与 `TransportCar` 集成测试。

## 验收标准

- `src/services/transport_car.py` 中不再定义视觉状态名映射。
- `src/services/vision_state_machine.py` 中不再维护状态名常量表。
- 视觉状态迁移日志仍能输出，且文本由独立日志模块负责格式化。
- 视觉状态名查询统一通过注册表完成。
- `tests/unit/services` 相关测试与 Stage 2 smoke 通过。
