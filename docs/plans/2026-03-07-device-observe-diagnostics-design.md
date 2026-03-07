# Stage 3 设备观测诊断设计文档

## 背景

当前仓库已经具备 `tests/unit`、`tests/contract` 和文档化 `tests/hil` 三层验证，但 agent 对真车的可观测能力仍然有限：

- 本地 `pytest` 只能覆盖主机侧逻辑。
- `mpy-cli` 可以部署和执行脚本，但缺少一条稳定的“设备状态读取”路径。
- 运行时代码当前只暴露 `?pos` 与 `?lock`，不足以帮助 agent 判断问题位于周期抖动、IMU、编码器、电机输出还是视觉状态机。

用户希望在主机侧 `pytest` 之外增加两个设备阶段：

1. 仅连接 `mpy` 端、不驱动硬件的安全测试。
2. 真实运行硬件并能读出实时状态的观测测试。

本文聚焦第二阶段（Stage 3）设计，同时为第一阶段复用必要的基础设施。

## 目标

1. 让 agent 能通过本地脚本触发一轮“设备观测测试”，并自动拿到结构化实时状态。
2. 提供足够的观测面，帮助 agent 判断问题是控制周期、传感器、执行器还是视觉状态机链路异常。
3. 保持 5ms 控制周期约束，不因为诊断逻辑引入显著抖动。
4. 兼容现有命令路由与 `TransportCar` 架构边界，不将业务逻辑塞进驱动层。
5. 为后续 Stage 2/Stage 3 自动化留出统一的主机侧入口。

## 非目标

- 不把真实硬件测试纳入默认 CI 强制门禁。
- 不将所有状态持续高频刷屏输出到串口。
- 不重写现有控制算法、视觉状态机或串口协议主体。
- 不引入额外第三方 Python 依赖（如 `pyserial`）。

## 设计决策

### 1) 双入口观测模型

Stage 3 使用两条互补入口，但共享同一份运行时快照：

- `UART6` 查询入口：新增 `?health`、`?tick`、`?imu`、`?enc`、`?motor`、`?vision`。
- `mpy-cli` 临时探针入口：主机侧上传并运行一次性观测脚本，通过 USB REPL 打印同一批结构化状态，然后删除远端文件。

这样做的原因：

- 查询入口便于后续与 OpenArt/外部主控联调。
- 临时探针入口便于 agent 直接通过本地 USB + `mpy-cli` 主动发起观测，不依赖额外串口桥。

### 2) 运行时快照集中在 `TransportCar`

不让查询处理器和探针脚本各自拼装内部字段，而是在 `TransportCar` 中集中提供轻量快照方法，例如：

- `build_health_snapshot()`
- `build_tick_snapshot()`
- `build_imu_snapshot()`
- `build_encoder_snapshot()`
- `build_motor_snapshot()`
- `build_vision_snapshot()`

这些方法只读取现有运行状态并做轻量整理，不触发额外控制计算。

### 3) 周期诊断以“摘要”优先，不做日志流

为避免破坏 5ms 周期，Stage 3 默认采用“低频轮询摘要”而不是“高频持续日志”：

- 在 `_handle_tick()` 内维护轻量统计：最近周期、最大周期、累计周期、超预算次数。
- 查询时返回摘要值。
- 观测脚本每次按较低频率（例如 100ms）采样一次，而不是每 tick 输出一次。

### 4) 结构化文本协议而非 JSON

返回格式继续贴合当前查询风格，采用 `?token=k:v,...` 的单行文本：

- `?health=alive:1,uptime_ms:1234,lock:0,rear:0,last_err:none`
- `?tick=last_us:4987,max_us:5301,avg_us:5012,overrun:0,count:280`

原因：

- 避免在 MicroPython 端引入额外 JSON 序列化成本。
- 与现有 `?pos`、`?lock` 风格一致。
- 主机侧解析成本低，agent 也能直接读。

### 5) 主机侧工具链统一为 `tools/run_device_observe.py`

新增一个主机侧入口脚本，负责：

1. 调用 `mpy-cli plan` / `upload` / `run` / `delete`
2. 将版本化的观测探针上传到设备临时路径
3. 读取 `mpy-cli run` 输出
4. 解析结构化观测结果
5. 输出 PASS / FAIL 和失败归因

该脚本不直接访问硬件驱动，只编排 `mpy-cli` 命令。

### 6) Stage 2 与 Stage 3 复用同一基建

虽然本次聚焦 Stage 3，但基础设施需要同时服务 Stage 2：

- Stage 2 的临时探针以“安全初始化、不启动电机”为主。
- Stage 3 的临时探针以“启动控制循环、周期采样快照”为主。

两者共享：

- 远端临时文件上传/执行/删除流程
- 输出解析规则
- 失败分类（连接失败、部署失败、脚本异常、观测失败）

## 模块划分

### `src/services/transport_car.py`

- 新增运行期诊断字段：启动时间、最近周期、最大周期、累计周期、超预算次数、最近异常等。
- 新增快照方法，集中封装运行时状态读取。
- 在关键路径内仅做常数级字段更新。

### `src/services/commands/query_*.py`

- 新增六个查询处理器：`health`、`tick`、`imu`、`enc`、`motor`、`vision`。
- 查询处理器只负责格式化并写回 `uart6`。

### `tests/contract/services/commands/test_diag_queries.py`

- 验证查询格式与关键字段。
- 防止后续改动破坏串口诊断协议。

### `tests/unit/services/test_transport_car_diag_snapshots.py`

- 验证快照方法从 `TransportCar` 状态提取结果的逻辑。
- 使用 `TransportCar.__new__` 与假对象，避免引入真实硬件依赖。

### `tools/device_observe_probe.py`

- 设备侧临时探针脚本。
- 启动 `TransportCar`、注册 ticker、采样若干帧快照、打印结构化观测输出、停止 ticker 后退出。

### `tools/run_device_observe.py`

- 主机侧执行器。
- 负责上传/运行/删除探针、归档输出、给出失败原因和摘要。

## 数据面设计

### `health`

- `alive`
- `uptime_ms`
- `lock`
- `rear`
- `last_err`
- `vision_state`

### `tick`

- `count`
- `last_us`
- `max_us`
- `avg_us`
- `overrun`

### `imu`

- `ok`
- `yaw_deg`
- `yaw_rate_dps`
- `gz_raw`

### `enc`

- `m_raw` / `m_filt`
- `l_raw` / `l_filt`
- `r_raw` / `r_filt`

### `motor`

- `m_target` / `m_duty`
- `l_target` / `l_duty`
- `r_target` / `r_duty`
- `rear`

### `vision`

- `state`
- `obs_age_ms`
- `obs_x`
- `obs_y`
- `target_x`
- `target_y`
- `target_angle`

## 失败分类

主机侧执行器至少区分四类失败：

1. `connect_failed`：串口或 `mpy-cli` 无法连接设备。
2. `deploy_failed`：上传或删除临时探针失败。
3. `probe_failed`：探针脚本运行异常或输出格式错误。
4. `observe_failed`：探针运行成功，但观测断言未满足（如周期超预算、IMU 不更新）。

## 风险与缓解

1. 风险：诊断输出过重，拖慢控制周期。
   - 缓解：快照只读字段；输出频率由探针脚本节流；不在中断里打印。
2. 风险：观测脚本与正式运行脚本初始化逻辑重复，后续漂移。
   - 缓解：尽量复用 `TransportCar` 现有初始化路径，文档中明确探针用途；如重复扩大再抽公共 helper。
3. 风险：查询输出字段过多，解析脆弱。
   - 缓解：保持扁平键值对，字段命名稳定；新增 contract 测试锁定协议。
4. 风险：无车环境无法验证 Stage 3 全流程。
   - 缓解：主机侧命令编排和快照逻辑用 `unit/contract` 锁定；真实板运行留在 HIL 阶段执行。

## 验收标准

1. `tests/unit` 新增诊断快照测试并通过。
2. `tests/contract` 新增诊断查询测试并通过。
3. 仓库新增可复现的 Stage 3 主机侧执行脚本与文档说明。
4. 真实设备上可通过 `mpy-cli` 执行观测探针，并看到结构化状态输出。
5. `tests/hil/` 补充 Stage 3 观测场景与留证模板。
