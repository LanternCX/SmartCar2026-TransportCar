# 全局工业级日志系统设计文档

## 背景

当前仓库的日志与调试输出能力处于分散状态：

1. `src/services/transport_car.py` 中存在大量直接 `uart3.write(...)` 的文本输出。
2. `src/services/vision_debug.py` 只覆盖视觉状态迁移日志, 还不是全局日志基础设施。
3. `UART3` 既承担人工调试链路, 也可能看到查询回显和命令回显, 协议输出与业务日志尚未明确分层。

这种实现虽然足以支撑当前调试, 但存在几个明显问题：

- 日志格式不统一, 不同模块输出风格不一致。
- 缺少全局日志等级控制, 无法快速切换 `INFO` / `DEBUG` 等观测粒度。
- 缺少模块过滤能力, 现场排障时无法只看 `vision` 或 `control` 相关日志。
- 低价值日志直接同步写串口, 在 5ms 控制周期约束下存在实时性风险。
- 当前颜色显示能力缺失, 但如果未来引入颜色, 也需要保证无颜色环境下仍然可读。

## 目标

1. 建立一个面向全仓库的统一日志系统, 替代散落的直接串口打印。
2. 支持 `RUN` / `DIAG` 双 profile, 分别面向正式运行和现场诊断。
3. 支持全局日志等级切换: `TRACE / DEBUG / INFO / WARN / ERROR / FATAL`。
4. 支持模块过滤, 且同时支持 `off / whitelist / blacklist` 三种过滤模式。
5. 默认输出到 `UART3`, 并支持有颜色与无颜色两种格式化输出。
6. 不引入时间戳, 但保持单行日志在纯文本串口窗口中依然清晰可读。
7. 将协议查询响应与业务日志严格分离, 避免相互污染职责。

## 非目标

- 不在本次设计中引入文件日志、SD 卡日志或主机侧文件落盘。
- 不在本次设计中引入复杂异步框架或线程模型。
- 不把 `?health`、`?tick`、`?vision` 这类查询响应并入日志系统。
- 不在本次设计中实现日志配置持久化。
- 不把所有调试文本立即改造成结构化事件总线。

## 设计决策

### 1. 采用“全局 Logger + Sink + Formatter + Runtime Config”架构

- 新增独立日志模块, 负责全局日志入口、等级判定、模块过滤和 sink 分发。
- 业务模块不再直接拼接完整串口输出文本, 而是调用统一日志接口。
- formatter 负责把日志记录转成最终文本；sink 负责把文本写到具体输出通道。
- 第一阶段只提供 `UART3 sink`, 后续如有需要可追加内存环形缓冲 sink。

### 2. 采用双 profile 模型

- `RUN` profile: 面向正式运行, 默认强调实时安全。
- `DIAG` profile: 面向人工排障, 默认强调可观测性。
- profile 只是默认配置集合, 并不限制运行时进一步手工调整日志等级和过滤规则。

建议默认值如下：

- `RUN`: `INFO`, `filter_mode=off`
- `DIAG`: `DEBUG`, `filter_mode=off`

### 3. 日志等级统一为六级

- `TRACE`: 极高频、极细粒度诊断
- `DEBUG`: 开发与排障明细
- `INFO`: 关键流程与状态摘要
- `WARN`: 非致命异常与降级路径
- `ERROR`: 明确错误, 需要关注
- `FATAL`: 严重错误, 可能导致流程终止

等级判断统一在 logger 内部完成, 业务模块不再自行写 `if debug_enabled:` 分支。

### 4. 模块过滤支持白名单与黑名单

- 过滤模式支持三态：
  - `off`
  - `whitelist`
  - `blacklist`
- 任一时刻只激活一种过滤模式, 避免同时叠加带来歧义。
- 模块匹配采用“前缀匹配 + 点号边界”规则：
  - `vision` 匹配 `vision.state`、`vision.protocol`
  - `control.pid` 匹配 `control.pid.yaw`
  - 不误匹配 `visionx`

这种规则兼顾了过滤表达力和实现复杂度, 也更适合串口现场快速切换。

### 5. 默认配置集中到 `src/config/params.py`

- 不新增 `json` / `yaml` / `ini` 外部配置文件。
- 默认日志参数集中定义在 `src/config/params.py`。
- 启动时 logger 从默认参数构造运行时配置。
- 运行时允许通过串口命令修改内存态配置, 但本次不做持久化。

建议配置项至少包括：

- `LOG_PROFILE_DEFAULT`
- `LOG_LEVEL_DEFAULT`
- `LOG_FILTER_MODE_DEFAULT`
- `LOG_FILTER_MODULES_DEFAULT`
- `LOG_COLOR_DEFAULT`
- `LOG_UART_CHANNEL_DEFAULT`
- `LOG_QUEUE_SIZE`
- `LOG_DROP_DEBUG_WHEN_BUSY`

### 6. 日志输出与协议响应严格分层

- 查询响应仍走现有查询处理链路, 保持“请求从哪个串口来, 默认回哪个串口”的规则。
- 日志系统默认只负责业务日志和调试日志。
- `cmd_print` 保留为原样打印调试命令, 但不再承担全局日志职责。
- `vision_debug` 这类已有结构化调试模块, 后续接入统一 logger, 而不是继续直接面向 `UART3`。

## 模块划分

### `src/services/logging.py`

- 定义日志等级常量与配置对象。
- 实现全局 logger / logger manager。
- 提供 `get_logger(module_name)`。
- 负责等级判定、模块过滤和 sink 分发。

### `src/services/log_format.py`

- 定义日志记录的文本格式化能力。
- 提供有颜色 formatter 与无颜色 formatter。
- 保证无颜色模式下仍维持固定前缀和足够可读性。

### `src/services/log_sink.py`

- 定义 sink 协议。
- 实现 `UART3 sink`。
- 视实现复杂度决定是否一并加入小型环形缓冲 sink。

### `src/config/params.py`

- 新增默认日志配置常量。
- 存放 profile 默认值和限流相关参数。

### `src/services/transport_car.py`

- 在初始化阶段构造全局日志系统并绑定 `UART3 sink`。
- 将启动、错误、调试提示、命令回显等输出逐步迁移到 logger。
- 不再在业务路径中散落大量原始 `uart3.write(...)`。

### `src/services/vision_debug.py`

- 保留视觉迁移事件构造能力。
- 文本输出改为委托全局 logger 或复用通用 formatter 规则。

## 运行时控制接口

沿用当前仓库的 `key=value` 命令风格, 不额外发明嵌套子协议。

建议新增命令：

- `log_profile=run|diag`
- `log_level=trace|debug|info|warn|error|fatal`
- `log_filter=off|whitelist|blacklist`
- `log_modules=vision|control.pid|hardware.imu`
- `log_color=0|1`
- `log_reset=1`

建议新增查询：

- `?log`

建议返回格式：

```text
?log=profile:diag,level:debug,filter:whitelist,color:1,modules:vision|control.pid
```

说明：

- `log_modules` 使用 `|` 作为模块分隔符, 避免与现有聚合命令的逗号分隔冲突。
- `log_reset=1` 用于回到 `src/config/params.py` 中定义的默认配置。
- 现有命令路由器需要从“除 `print` 外一律按 float 解析”升级为“命令可声明自己的 value 解析方式”, 以便更自然支持日志字符串配置。

## 模块命名建议

建议采用分层前缀命名, 便于过滤：

- `system.boot`
- `system.health`
- `services.command`
- `services.route`
- `vision.protocol`
- `vision.state`
- `control.yaw`
- `control.position`
- `hardware.imu`
- `hardware.encoder`
- `hardware.motor`

命名目标是：

- 既能表达职责边界
- 又能支撑前缀过滤
- 避免一个超大杂项模块名承载全部日志

## 格式化策略

### 1. 无颜色模式

- 单行格式保持简洁：`<L> [module] message`
- 例如：

```text
I [system.boot   ] init ok
W [vision.state  ] observation timeout, fallback to idle
E [hardware.imu  ] read failed: timeout
D [control.yaw   ] err=12.5 out=18.0
```

- 不依赖颜色传达语义。
- 模块名建议固定宽度左对齐, 以提升串口窗口可扫读性。

### 2. 颜色模式

- `TRACE`: 灰色
- `DEBUG`: 青色
- `INFO`: 绿色
- `WARN`: 黄色
- `ERROR` / `FATAL`: 红色

颜色仅作为增强层, 不改变文本主体结构。若终端不支持 ANSI, 应退回无颜色 formatter。

### 3. 不带时间戳

- 本次默认不输出时间戳。
- 如后续确有需要, 优先考虑“可选 tick 序号”而不是 wall-clock 时间。

## 实时性保护策略

### 1. 优先级原则

- `ERROR` / `FATAL` 优先保证可见。
- `WARN` / `INFO` / `DEBUG` / `TRACE` 可受 profile、限流和缓冲策略影响。

### 2. RUN 模式

- 默认仅输出 `INFO+`。
- 高频模块不默认开启详细日志。
- 当输出通道繁忙或缓冲满时, 优先丢弃低等级日志。

### 3. DIAG 模式

- 默认输出 `DEBUG+`。
- 允许更高观测密度。
- 仍保留“忙时丢弃 `TRACE` / `DEBUG`”的兜底机制, 防止串口流量反向破坏调试对象本身。

### 4. 中断约束

- 中断回调中不直接打印日志。
- 中断只置位标志或记录最小状态。
- 真正日志输出放在主循环安全点执行。

## 风险与缓解

1. 风险：日志系统抽象过重, 导致板端开销增加。
   - 缓解：第一阶段只做最小必要抽象, 不引入复杂运行时反射或重型依赖。
2. 风险：模块过滤语义不清, 导致现场调试误判“为什么没日志”。
   - 缓解：`?log` 明确回显当前 profile、等级、过滤模式和模块列表。
3. 风险：字符串命令配置接入后, 现有命令解析器约束不够。
   - 缓解：补充 command router 的 unit / contract 测试, 明确每类命令的 value 解析策略。
4. 风险：日志与查询输出边界处理不好, 继续污染人工调试串口。
   - 缓解：在设计上明确区分“查询响应”和“业务日志”, 不复用同一套职责入口。
5. 风险：颜色序列影响不支持 ANSI 的终端可读性。
   - 缓解：颜色作为可关闭能力, 默认保留纯文本等价格式。

## 验收标准

- 仓库中存在统一的全局日志入口, 新增业务日志不再直接散落 `uart3.write(...)`。
- 日志系统支持六级日志等级与 `RUN` / `DIAG` 双 profile。
- 日志系统支持 `off / whitelist / blacklist` 三种过滤模式。
- 模块过滤支持前缀匹配且不发生明显误匹配。
- 日志支持颜色与无颜色两种 formatter, 且无颜色模式可读性良好。
- 运行时可通过串口命令切换日志等级、过滤模式、模块列表和颜色开关。
- `?log` 能返回当前日志运行配置摘要。
- 查询响应与业务日志职责分层保持清晰。
- 对应 `tests/unit` 与 `tests/contract` 覆盖通过；若最终接入真实板端路径, 额外补 Stage 2 / Stage 3 / HIL 证据。
