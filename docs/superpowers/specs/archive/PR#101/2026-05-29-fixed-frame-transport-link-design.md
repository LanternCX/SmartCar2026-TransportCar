# 固定帧通信链路设计

执行状态: Archive

## 目标

建立统一通信层, 让主车、辅车和本地视觉链路通过同一套 TCP / UDP 读写接口交换固定长度二进制帧。通信层、业务层和测试入口都以 bytes 作为正式数据形态, 不在正式协议中传输字符串。业务层只处理 topic 与 body bytes, 不直接接触 UART 读写、缓存清理、ACK、重发和发送仲裁。

设计优先级为:

1. 可观测: 每个物理帧长度固定, topic 和模式字段位置固定。
2. 低内存: 不在热路径拼接文本, 不保留无上界缓存, UDP 不排队。
3. 稳定: 丢包、重复包、半包和积压输入不会让业务层失控。
4. 解耦: 通信调度独立于主车、辅车和共享底盘 Runtime。

## 范围

本设计覆盖 UART6 本地视觉链路和 UART8 主辅车链路的统一传输层、业务 topic、固定 body bytes 布局、低频状态协调和行为测试边界。UART3 调试终端不纳入正式传输层。

主车、辅车和本地视觉的正式通信行为都通过本设计定义的 bytes 帧表达。车辆状态流、速度融合、可靠事件、确认去重和缓存清理语义必须与既定业务行为一致。

## 帧结构

正式传输帧采用固定长度 bytes 格式。UART 写入、UART 读取、通信层缓存、topic body 和测试断言都以 bytes 表达。正式协议禁止把文本行、逗号分隔字段或字符串换行作为传输格式。

| 字段 | 长度 | 说明 |
| --- | --- | --- |
| MODE | 1 字节 | 传输模式, 表达 UDP、TCP 或 ACK |
| TOPIC | 1 字节 | 业务主题编号, 必须在 topic 注册表中定义 |
| SEQ | 1 字节 | 序号, 用于 TCP 确认、去重和联调观测 |
| BODY | 固定字节数 | 业务正文 bytes 槽位, 未使用字节补 0 |

不在帧中携带固定帧头、协议版本、链路编号、预留控制位、正文长度和软件 CRC。无线串口链路自身承担底层帧同步与校验, 车端协议只表达点对点业务传输所需的最小字段。

物理帧长度全局固定。topic 注册表记录每个 topic 的有效 body bytes 长度, 通信层按该长度校验业务写入, 并在组帧时补齐到固定 BODY 槽位。接收时通信层按 topic 的有效 body 长度裁出业务正文 bytes, 交给业务层。

## Topic 注册表

所有 topic 必须预注册。每个 topic 至少定义:

- topic 编号。
- topic 名称。
- 有效 body bytes 长度。
- 允许的传输模式。
- 允许的逻辑链路。
- 业务层读写方向。
- body bytes 布局。

topic 注册表是通信层唯一的包格式入口。业务层不能临时创建 topic, 也不能发送长度与注册表不一致的 body bytes。

业务数值使用固定字节布局表达, 优先使用定点整数和枚举值, 不使用浮点文本。正文解释由业务层负责, 通信层只负责 bytes 长度、链路、模式和序号规则。

## 传输模式

| 编号 | 名称 | 说明 |
| --- | --- | --- |
| 0x01 | UDP | 最新值数据, 不确认、不重发、不排队 |
| 0x02 | TCP | 可靠业务数据, 使用停止等待、ACK、重发和去重 |
| 0x03 | ACK | 确认帧, TOPIC 与 SEQ 指向被确认的 TCP 帧 |

ACK 不作为独立业务 topic。ACK 帧的 BODY 槽位全 0, TOPIC 使用被确认的业务 topic, SEQ 使用被确认的可靠序号。

## 业务 Topic 总表

全局 BODY 槽位长度为 8 字节, 物理帧总长度为 11 字节。每个 topic 的有效 body bytes 长度由注册表限定, 剩余槽位补 0。所有多字节整数使用小端序。所有有符号整数使用补码表达。

| Topic | 名称 | 模式 | 链路 | 方向 | 有效长度 | 业务语义 |
| --- | --- | --- | --- | --- | --- | --- |
| 0x01 | LOCAL_VISION_VELOCITY | UDP | UART6 | OpenART -> 车端 | 7 | 本车视觉速度或速度修正 |
| 0x02 | ASSISTANT_FEEDFORWARD_VELOCITY | UDP | UART8 | 主车 -> 辅车 | 7 | 主车发给辅车的速度前馈 |
| 0x03 | VISION_OBSERVATION | UDP | UART6 | OpenART -> 车端 | 7 | 视觉观测量, 不直接驱动状态跳转 |
| 0x10 | MASTER_VISION_HOOK_SYNC | TCP | UART6 | 主车 -> 本车 OpenART | 5 | 主车本地视觉 hook 状态同步 |
| 0x11 | ASSISTANT_VISION_TASK_SYNC | TCP | UART6 | 辅车 -> 本车 OpenART | 4 | 辅车本地视觉任务状态同步 |
| 0x12 | MASTER_VISION_EVENT_REPORT | TCP | UART6 | OpenART -> 主车 | 4 | 主车本地视觉事件回报 |
| 0x13 | ASSISTANT_VISION_EVENT_REPORT | TCP | UART6 | OpenART -> 辅车 | 3 | 辅车本地视觉事件回报 |
| 0x20 | ASSISTANT_STATE_SYNC | TCP | UART8 | 主车 -> 辅车 | 4 | 主车下发辅车子状态 |
| 0x21 | ASSISTANT_EVENT_REPORT | TCP | UART8 | 辅车 -> 主车 | 3 | 辅车向主车回报目标、对正和收尾事件 |

每个 topic 的允许方向是硬约束。通信层收到方向不匹配的帧时丢弃, 并增加非法帧计数。UART6 上的主车 topic 和辅车 topic 由角色配置决定, 不通过帧内字段区分角色。

通信服务初始化时绑定当前车辆角色配置。角色配置只用于判断本端对每个 topic 是允许写入、允许读取还是必须丢弃; 该配置不进入传输帧, 也不改变对外 API 的 `udp(port)` 与 `tcp(port)` 调用格式。主车服务只能写入主车方向的 topic 并读取发往主车的 topic, 辅车服务只能写入辅车方向的 topic 并读取发往辅车的 topic。

## Body Bytes 布局

LOCAL_VISION_VELOCITY 和 ASSISTANT_FEEDFORWARD_VELOCITY:

| 偏移 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| 0 | vx | i16 | 车体系 x 方向速度或修正量, 定点比例 1000 |
| 2 | vy | i16 | 车体系 y 方向速度或修正量, 定点比例 1000 |
| 4 | omega | i16 | 车体系角速度, 定点比例 1000 |
| 6 | has_omega | u8 | 0 表示不携带角速度, 1 表示携带角速度 |

速度编码前先做业务限幅, 再按 i16 可表达范围饱和。定点比例 1000 对应的可表达范围为 -32.768 到 32.767。配置测试必须约束常规速度、修正量和角速度参数处于协议可表达范围内。UART6 的速度输入在主车和辅车侧都只贡献平移分量。UART8 的速度前馈在辅车侧可以贡献角速度, 是否贡献由 has_omega 决定。

UDP 业务 topic 固定为:

```text
TOPIC_LOCAL_VISION_VELOCITY = 0x01
  mode: UDP
  port: UART6
  direction: OpenART -> 车端
  body: vx, vy, omega, has_omega
  api: udp(UART6).read(TOPIC_LOCAL_VISION_VELOCITY, out_body)
  semantic: 本车视觉速度或速度修正, 车端消费时忽略 omega

TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY = 0x02
  mode: UDP
  port: UART8
  direction: 主车 -> 辅车
  body: vx, vy, omega, has_omega
  api:
    主车 udp(UART8).write(TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY, body)
    辅车 udp(UART8).read(TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY, out_body)
  semantic: 主车当前底盘速度前馈, 辅车按状态决定是否使用 omega

TOPIC_VISION_OBSERVATION = 0x03
  mode: UDP
  port: UART6
  direction: OpenART -> 车端
  body: context_id, x, y, value
  api: udp(UART6).read(TOPIC_VISION_OBSERVATION, out_body)
  semantic: 视觉观测量, 不直接驱动状态跳转
```

VISION_OBSERVATION:

| 偏移 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| 0 | context_id | u8 | 视觉上下文编号 |
| 1 | x | i16 | 观测 x 分量, 定点比例 1000 |
| 3 | y | i16 | 观测 y 分量, 定点比例 1000 |
| 5 | value | i16 | 观测附加值, 定点比例 1000 |

MASTER_VISION_HOOK_SYNC:

| 偏移 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| 0 | context_id | u8 | 主车视觉 hook 上下文编号 |
| 1 | state | u8 | 主车状态编号 |
| 2 | target | u8 | 主车视觉目标编号 |
| 3 | arg | i16 | hook 配置编号或状态参数 |

ASSISTANT_VISION_TASK_SYNC:

| 偏移 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| 0 | state | u8 | 辅车本地视觉任务状态编号 |
| 1 | target | u8 | 辅车视觉目标编号 |
| 2 | arg | i16 | 视觉配置编号或状态参数 |

MASTER_VISION_EVENT_REPORT:

| 偏移 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| 0 | context_id | u8 | 视觉上下文编号 |
| 1 | event | u8 | 事件编号 |
| 2 | value | i16 | 事件附加值 |

ASSISTANT_VISION_EVENT_REPORT 和 ASSISTANT_EVENT_REPORT:

| 偏移 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| 0 | event | u8 | 事件编号 |
| 1 | value | i16 | 事件附加值 |

ASSISTANT_STATE_SYNC:

| 偏移 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| 0 | state | u8 | 辅车子状态编号 |
| 1 | target | u8 | 辅车子目标编号 |
| 2 | arg | i16 | 辅车状态参数、视觉配置编号或收尾阶段编号 |

## 业务编号

主车全局状态编号:

| 编号 | 名称 |
| --- | --- |
| 0 | IDLE |
| 1 | SEARCH_OBJECT |
| 2 | ORBITING |
| 3 | STOP |
| 4 | TRANSPORT_OBJECT |
| 5 | CLEAR_OBJECT |

辅车子状态编号:

| 编号 | 名称 |
| --- | --- |
| 0 | IDLE |
| 1 | FOLLOW |
| 2 | APPROACH_OBJECT |
| 3 | ORBIT |
| 4 | TRANSPORT_OBJECT |
| 5 | CLEAR_OBJECT |

目标编号:

| 编号 | 名称 | 适用范围 |
| --- | --- | --- |
| 0 | NONE | 主车、辅车 |
| 1 | OBJECT | 主车、辅车 |
| 3 | EDGE_LINE | 主车本地视觉 |

事件编号:

| 编号 | 名称 | 方向 |
| --- | --- | --- |
| 6 | TARGET_FOUND | 本地视觉 -> 车端; 辅车 -> 主车 |
| 7 | ALIGNED | 本地视觉 -> 车端; 辅车 -> 主车 |
| 8 | ARRIVED | 主车本地视觉 -> 主车 |
| 9 | CLEARED | 辅车 -> 主车 |

收尾阶段编号:

| 编号 | 名称 |
| --- | --- |
| 0 | NONE |
| 1 | RETREAT |
| 2 | FORWARD |

## 业务 API

通信层提供通用 bytes API, 业务适配层在 topic 注册表之上提供命名写入、读取和可靠交付状态入口。业务适配层只做枚举、定点数和 body bytes 的相互转换, 不直接访问 UART, 也不处理裸 ACK 帧。

业务适配层必须覆盖以下入口:

- 读取本车视觉 UDP 速度或速度修正。
- 写入主车到辅车 UDP 速度前馈。
- 读取主车到辅车 UDP 速度前馈。
- 读取本车视觉 UDP 观测。
- 写入主车本地视觉 hook 同步。
- 查询主车本地视觉 hook 同步交付状态。
- 读取主车本地视觉事件。
- 写入辅车本地视觉任务同步。
- 查询辅车本地视觉任务同步交付状态。
- 读取辅车本地视觉事件。
- 写入主车到辅车状态同步。
- 查询主车到辅车状态同步交付状态。
- 写入辅车到主车事件回报。
- 查询辅车到主车事件回报交付状态。

## API

业务层面对四类操作:

- UDP 写: 向指定逻辑链路提交某个 topic 的最新 body bytes。
- UDP 读: 从指定逻辑链路读取某个 topic 的最新 body bytes。
- TCP 写: 向指定逻辑链路提交某个 topic 的可靠 body bytes。
- TCP 读: 从指定逻辑链路读取某个 topic 的可靠 body bytes。

API 使用逻辑链路, 不暴露裸 UART 对象。逻辑链路包括 UART6 本地视觉链路和 UART8 主辅车链路。

写操作只提交发送意图, 不直接写串口。读操作只读取通信层缓存, 不直接读串口。主车 Runtime、辅车 Runtime 和共享底盘 Runtime 都不维护 UART 缓冲、ACK 或重发状态。

API 不接受字符串作为正式 body。若业务状态来自数值或枚举, 必须先编码成固定布局 bytes; 若联调需要可读输出, 通过诊断接口单独输出, 不混入正式传输帧。

写 API 返回固定状态码, 表达 accepted、overwritten、dropped_priority、dropped_busy 或 invalid。通信层不为 API 调用创建动态队列。调用被更高优先级发送意图覆盖时直接丢弃并计数, 由业务协调层在下一次协调周期按状态重新提交。UDP 只允许覆盖最新值槽。TCP 只允许进入固定可靠发送槽, 槽忙时直接返回 dropped_busy。TCP 序号只在消息进入空闲发送槽时分配; 写入失败、槽忙或被优先级覆盖时不分配新序号。

## API 固定格式

对外通信入口只保留在 `src/protocol/` 包内, 不新增 `src/comm/` 或其他并列通信包。`protocol` 同时承载固定帧、topic 注册、传输调度和业务适配入口, 避免出现两套通信文件结构。`src/config/comm.py` 只作为通信参数配置文件, 不承载通信实现。

建议文件结构:

```text
src/protocol/
  __init__.py
  frame.py        固定帧编解码
  topic.py        topic 注册表、body 长度和方向约束
  transport.py    udp/tcp/diagnostics 对外入口和调度服务
  codec.py        业务枚举与 body bytes 编解码
```

正式数据 API 采用链路绑定句柄格式, 业务层先选择模式与端口, 再读写 topic 和 body。对外入口由 `protocol.transport` 暴露, 调用侧不引入 `comm` 包名。

业务层调用格式固定为:

```text
udp(port).write(topic, body) -> WriteStatus
udp(port).read(topic, out_body) -> ReadStatus

tcp(port).write(topic, body) -> WriteStatus
tcp(port).read(topic, out_body) -> ReadStatus
tcp(port).delivery(topic) -> DeliveryStatus

diagnostics(port) -> DiagnosticsSnapshot
```

参数格式固定为:

```text
port:
  UART6 | UART8

topic:
  Topic 注册表中的 u8 编号

body:
  bytes-like
  允许 bytes、bytearray、memoryview
  长度必须等于 topic 有效 body bytes 长度
  不允许 str

out_body:
  bytearray | memoryview
  调用方提供
  长度必须不小于 topic 有效 body bytes 长度
  只写入 topic 有效 body bytes 长度范围内的数据
```

返回状态固定为:

```text
WriteStatus:
  accepted         写入固定槽成功
  overwritten      UDP 最新值槽被同一 port + topic 的新 body 覆盖
  dropped_priority 本周期发送意图被更高优先级意图覆盖并丢弃
  dropped_busy     固定槽忙, 新请求被丢弃
  invalid          port、topic、模式、方向、body 类型或 body 长度非法

ReadStatus:
  ok       out_body 已写入有效 body bytes
  empty    没有可读业务 body
  invalid  port、topic、模式、方向或 out_body 非法

DeliveryStatus:
  idle       TCP 发送槽为空
  pending    TCP 发送槽等待 ACK
  delivered  TCP 发送槽收到匹配 ACK 并释放
  dropped    写入请求被覆盖或槽忙丢弃
  invalid    port 或 topic 非法
```

数据 API 行为固定为:

```text
udp(port).write(topic, body):
  校验 port、topic、模式、方向和 body 长度
  写入 UDP 最新值槽
  同一 port + topic 只保留最新 body

udp(port).read(topic, out_body):
  将最近一次合法 UDP body 复制到 out_body
  不消费该最新值

tcp(port).write(topic, body):
  校验 port、topic、模式、方向和 body 长度
  TCP 发送槽空闲时写入固定发送槽并分配 active_seq
  TCP 发送槽忙时返回 dropped_busy

tcp(port).read(topic, out_body):
  将 TCP 接收交付槽中的 body 复制到 out_body
  成功读取后释放接收交付槽

tcp(port).delivery(topic):
  查询当前 TCP 发送槽交付状态
  不改变 TCP 发送槽

diagnostics(port):
  返回小整数计数和固定槽状态
  不返回业务 body
```

API 内存约束:

- 写 API 在校验通过后把 body 复制到预分配固定槽, 不保存调用方对象引用。
- 读 API 只写调用方提供的 out_body, 不创建新的 bytes 对象。
- out_body 只写 topic 有效 body bytes 长度范围内的数据。
- body 与 out_body 允许是 bytearray 或 memoryview, 但不允许是字符串。
- 每个 port + topic 的 UDP 接收缓存、UDP 发送缓存、TCP 发送槽、TCP 接收交付槽和 ACK 槽都是固定数量。

## 通信调度

入口层创建独立通信服务。主循环按固定顺序运行:

1. 通信层 RX: 读取 UART6 和 UART8, 限幅、切帧、分发到 TCP / UDP 接收缓存。
2. 低频协调层与高频执行层: 从通信层读取业务输入, 并提交本周期要发送的 TCP / UDP 消息。
3. 通信层 TX: 通过统一发送仲裁器选择一帧写出。

通信层与 Runtime 并行存在, 不作为 Runtime 的内部工具函数。通信层拥有 UART 读写权, Runtime 只拥有业务读写权。

每个主循环周期内, 每个 UART 端口只允许通信服务执行一轮 RX 请求。TCP、UDP 和 ACK 的发送请求都只能进入同一个 TX 仲裁入口, 不允许在 Runtime、状态协调层或业务适配层中出现第二个端口写入口。该约束用行为测试绑定, 避免重构后重新出现多处端口访问。

## RX 规则

每条链路的 RX 都有固定读取上限和固定积压处理规则:

- 单次读取长度受限。
- 不保留无上界半包缓存。
- 输入积压超过上限时清空本轮积压。
- 没有完整固定帧时丢弃本轮残缺输入。
- 存在多帧积压时, 按固定帧长度切分可处理帧, 其余残缺尾部丢弃。
- topic、mode 或链路不合法时丢弃该帧。

该规则让缓存占用稳定有界。UDP 依赖最新值语义承受丢包; TCP 依赖 ACK 与重发恢复丢包。

## TX 仲裁

通信层维护全局发送闸口。每个通信调度周期最多写出一帧, UART6 和 UART8 共享该发送额度。

发送优先级为:

1. ACK。
2. TCP 业务帧。
3. UDP 最新帧。

TCP 和 UDP 即使在同一周期都被业务层提交, TX 仲裁器也只放行一个帧。业务层不承担发送互斥职责。

同一周期发生优先级覆盖时, 被覆盖的本周期 API 发送意图直接丢弃, 不进入队列。ACK 覆盖 TCP 与 UDP, TCP 覆盖 UDP。已进入 TCP 固定可靠发送槽且正在等待 ACK 的帧不属于本周期 API 发送意图集合, 只保留在单个重发槽中等待下一次发送机会。

覆盖规则固定为: 不同种类的包按发送优先级覆盖, 同种类的包按新包覆盖旧包。覆盖只发生在本周期发送意图层、ACK 固定槽和 UDP 最新值槽。已经进入 TCP 固定发送槽并等待 ACK 的可靠帧不能被新 TCP 覆盖。

同种类覆盖规则:

```text
UDP:
  同一 port + topic 的新 body 覆盖旧 body
  不同 topic 各自保留一个最新值槽

TCP:
  发送槽空闲且同周期提交多个 TCP 意图时, 最后一个合法 TCP 意图覆盖前面的 TCP 意图
  TCP 意图进入固定发送槽并分配 active_seq 后, 不再被覆盖

ACK:
  同一确认对象重复写入时合并为一份 ACK
  ACK 槽中确认对象不同时, 新 ACK 意图覆盖尚未写出的 ACK 候选, 被覆盖对象由对端重发恢复
```

同模式跨端口和跨 topic 的发送选择规则:

```text
ACK:
  全局只保留一个待发送 ACK 候选
  同周期重复确认同一对象时合并
  同周期确认对象不同时, 后写入的 ACK 覆盖尚未进入 UART 写出的 ACK 候选

TCP:
  每条逻辑链路最多保留一个正在等待 ACK 的 TCP 固定发送槽
  全局 TX 闸口在每周期只选择一个到达发送时间的 TCP 固定发送槽
  多个 TCP 固定发送槽同时到达发送时间时, 按上次放行链路轮转选择, 避免长期偏向某个端口
  本周期 API 层尚未进入固定发送槽的多个 TCP 意图按最后写入者保留

UDP:
  每个 port + topic 的接收缓存独立保留最新值
  本周期 API 层多个 UDP 发送意图按最后写入者作为本周期发送候选
  未被选为本周期发送候选的 UDP 最新值槽不排队, 只保留各自最新 body 供下一次业务写入覆盖
```

UDP 每 20ms 最多发送一次。每个 port + topic 只保留最新 body bytes, 新 body bytes 覆盖已缓存 body bytes。

TCP 业务帧每 150ms 最多发送一次。未确认的 TCP 帧按 150ms 周期重发。ACK 不占用 TCP 业务重发节奏, 但必须经过同一个全局发送闸口。

## TCP 可靠通信

TCP 使用停止等待模型。每条链路同一时刻最多有一个正在等待 ACK 的 TCP 业务帧。每条链路只维护一个固定发送槽、一个固定接收交付槽和一个 active_seq, 不维护可靠消息队列。

同一条逻辑链路上, active_seq 清空前不能创建第二个 TCP 可靠序号。状态同步 topic 也必须遵守该约束: ASSISTANT_STATE_SYNC、MASTER_VISION_HOOK_SYNC 和 ASSISTANT_VISION_TASK_SYNC 在发送槽忙时直接返回 dropped_busy, 不替换槽内 body, 不分配新 seq, 不产生第二个不同 seq 的同步帧。状态协调层不得同时维护同一链路的两份待确认状态同步。

发送流程:

1. 业务层提交 topic 与 body bytes。
2. 通信层检查 topic、链路、模式和 body bytes 长度。
3. 合法消息在发送槽空闲时进入固定可靠发送槽。
4. 发送槽忙或本周期被更高优先级 API 调用覆盖时, 新提交直接丢弃并返回状态码。
5. 消息进入发送槽时分配本链路唯一 active_seq。
6. TX 仲裁器按 150ms 节奏发送发送槽中的消息。
7. 消息发出后保持等待 ACK 状态。
8. 收到匹配的 ACK 后移除该消息并清空 active_seq。
9. 未收到 ACK 时按 150ms 节奏重发同一 seq 的同一帧。

接收流程:

1. RX 收到 TCP 帧后检查 topic、链路和 body bytes 长度。
2. 新 seq 的合法帧在接收交付槽空闲时进入 TCP 接收交付槽。
3. 重复 seq 的帧不重复交给业务层。
4. 进入接收交付槽的帧和重复帧都会尝试写入固定 ACK 槽。
5. ACK 槽空闲或确认对象相同时保留确认对象; ACK 槽确认对象不同时, 新 ACK 意图覆盖尚未写出的 ACK 候选并计数, 被覆盖对象由发送侧重发恢复。
6. 接收交付槽满时不确认新帧, 由发送侧重发恢复。

ACK 帧使用 MODE、TOPIC 和 SEQ 表达确认对象, BODY 槽位补 0。

## UDP 最新值通信

UDP 用于高频速度和视觉修正等最新值数据。

发送流程:

1. 业务层提交 topic 与 body bytes。
2. 通信层检查 topic、链路、模式和 body bytes 长度。
3. 同一 port + topic 只保留最新 body bytes。
4. TX 仲裁器按 20ms 节奏发送可用 UDP 帧。

接收流程:

1. RX 收到 UDP 帧后检查 topic、链路和 body bytes 长度。
2. 合法帧覆盖同一 port + topic 的接收缓存。
3. 业务层读取最新 body bytes。

UDP 不确认、不重发、不排队。

## 多链路语义

UART6 和 UART8 复用同一套固定帧、topic 注册表、RX 保护、TX 仲裁和 TCP / UDP API。链路差异由 port 配置和 topic 注册表约束。

UART6 用于本车与本地视觉之间的低频同步、视觉事件和高频速度修正。UART8 用于主车与辅车之间的状态同步、事件回报和速度前馈。

包内不携带链路编号。收到帧的 UART 即为该帧所属链路。

## 状态协调边界

完整重构将业务节奏拆成三层:

- 通信服务: 独立维护 UART6 和 UART8 的 RX、TX、ACK、重发、去重、缓存清理和发送仲裁。
- 高频执行层: 底盘控制、速度融合、传感器采样和 UDP 最新值消费。
- 低频协调层: 状态跳转、视觉 hook 同步、车车状态同步和可靠事件处理。

通信服务在每个主循环周期执行 RX 和 TX。低频协调层按 150ms 节奏运行, 与 TCP 可靠通信节奏一致。高频执行层继续保持控制响应, 不在控制热路径判断 150ms 可靠状态节奏。

主车 Runtime、辅车 Runtime 和共享底盘 Runtime 都不直接读写 UART, 也不维护可靠包发送状态。状态机相关逻辑由低频协调层消费通信服务提供的业务输入, 并向通信服务提交下一次可靠同步或可靠事件。

## 业务行为保持约束

状态流必须保持一致:

1. 主车进入搜索物体, 下发本车视觉 hook, 并保持或同步辅车进入跟随。
2. 主车本地视觉命中目标后, 主车让辅车进入 idle, 自身进入绕行。
3. 主车绕行结束后, 主车继续搜索同一轮搬运目标, 并让辅车进入找物体。
4. 辅车本地视觉命中目标后, 辅车向主车回报 TARGET_FOUND。
5. 主车收到辅车命中后, 让辅车进入绕行。
6. 主车和辅车都完成对正后, 主车下发辅车搬运同步, 并下发本车搬运 hook。
7. 主车进入搬运, 使用本车视觉修正与搬运基础速度。
8. 主车本地视觉回报 ARRIVED 后进入收尾, 主车和辅车按 RETREAT、FORWARD 阶段同步完成。
9. 收尾完成后主车回到搜索物体, 辅车回到跟随。

辅车子状态只由主车通过 ASSISTANT_STATE_SYNC 驱动。辅车不能因为本地视觉速度、本地视觉事件或底盘状态自行切换子状态。辅车本地视觉事件只能生成待回报事件或影响当前子状态内部动作。

可靠业务必须幂等:

- TCP 重复帧必须 ACK, 但不能重复交给状态机。
- ACK 丢失导致的重发不能重复触发状态跳转、运动指令或事件回报。
- 主车本地视觉事件必须匹配 active context_id 才能进入状态机。
- 主车本地视觉事件如果匹配已发送但尚未确认的 hook context_id, 只能暂存为一次 pending 事件。
- 辅车本地视觉事件在当前子状态不接受该事件时不能改变状态。

UDP 最新值语义必须保持一致:

- 通信层保存每个 port + topic 的最后一个合法 UDP body bytes。
- 没有新 UDP 帧时, 最新值缓存保持不变。
- 非法帧、残缺帧和溢出清理不能覆盖最后一个合法 UDP 值。
- 业务状态发生切换时, 状态协调层按对应状态清空相关 UDP 缓存。

速度融合必须保持一致:

- 主车搜索阶段使用 UART6 的 LOCAL_VISION_VELOCITY, 并忽略 omega。
- 主车绕行阶段使用 UART6 的 vx、vy 作为绕行修正, 不使用 omega。
- 主车搬运阶段使用搬运基础速度叠加 UART6 的 vx、vy, 不使用 omega。
- 主车完成对正等待搬运入口时输出 0 速度。
- 主车通过 UART8 向辅车发送本车当前速度前馈, 有 omega 时 has_omega 为 1。
- 辅车跟随阶段叠加 UART6 本地视觉平移量和 UART8 主车前馈平移量。
- 辅车只有在消费 UART8 前馈时使用 omega, UART6 的 omega 不贡献。
- 辅车找物体阶段只使用 UART6 平移量。
- 辅车绕行阶段只使用 UART6 平移量作为绕行修正。
- 辅车搬运阶段使用 UART6 平移修正, 并叠加按配置缩放和取反后的 UART8 前馈平移量, omega 为 0。
- 辅车收尾阶段不消费速度流。

可靠同步必须保持一致:

- MASTER_VISION_HOOK_SYNC 的 SEQ 表达可靠传输身份, context_id 表达视觉业务上下文。
- ASSISTANT_STATE_SYNC 的 SEQ 表达主辅可靠同步身份, body 不携带 context_id。
- ASSISTANT_EVENT_REPORT 的 SEQ 表达辅车可靠回报身份, body 不携带 context_id。
- ASSISTANT_VISION_TASK_SYNC 的 SEQ 表达辅车与本地视觉之间的可靠同步身份。
- UART8 上 ACK、TCP 业务帧和 UDP 速度帧都必须经过同一个发送闸口。

## 错误处理与观测

通信层保留轻量诊断计数:

- 每条链路 RX 读取次数。
- 丢弃残缺帧数量。
- 丢弃非法 topic 数量。
- TCP 重发次数。
- ACK 收发次数。
- UDP 覆盖次数。
- API 优先级丢弃次数。
- API 槽忙丢弃次数。
- ACK 覆盖次数。
- 发送闸口放行帧数量。
- 固定发送槽和接收交付槽占用状态。

诊断只记录小整数、固定槽状态和最后错误码, 不在热路径输出长文本。运行时不得因通信帧创建动态消息列表、无界缓存或字符串拼接链路。

## 验收标准

主机侧测试至少覆盖通信契约:

- 固定帧编码与解码。
- 所有 topic 的固定 body bytes 长度。
- topic 注册表拒绝未注册 topic、错误模式、错误链路、错误方向和错误 body 长度。
- UDP 业务 topic 固定为 LOCAL_VISION_VELOCITY、ASSISTANT_FEEDFORWARD_VELOCITY 和 VISION_OBSERVATION。
- LOCAL_VISION_VELOCITY 只允许 UART6 的 OpenART -> 车端方向。
- ASSISTANT_FEEDFORWARD_VELOCITY 只允许 UART8 的主车 -> 辅车方向。
- VISION_OBSERVATION 只允许 UART6 的 OpenART -> 车端方向。
- 所有正式 API 只接受 bytes body。
- 四个数据 API 的名称、参数、返回状态和副作用与固定格式一致。
- 写 API 不保存调用方 body 引用, 读 API 不创建新的业务 bytes 对象。
- udp_read 不消费最新值, tcp_read 成功后释放接收交付槽。
- tcp_delivery 和 diagnostics 不发送通信帧。
- 速度、状态、事件和观测帧的 body bytes 编解码往返。
- 多字节整数小端序和定点比例。
- 常规速度、修正量和角速度配置处于协议可表达范围内。
- ACK 使用被确认帧的 TOPIC 和 SEQ, BODY 槽位补 0。
- UDP 最新值覆盖。
- 不同种类发送意图按 ACK、TCP、UDP 优先级覆盖。
- 同种类发送意图按新包覆盖旧包。
- 已进入 TCP 固定发送槽并等待 ACK 的可靠帧不能被新 TCP 覆盖。
- TCP ACK、重发和去重。
- TCP 接收交付槽满时不确认新帧。
- TCP 发送槽忙时写 API 返回 dropped_busy, 不缓存新请求。
- 同一链路 active_seq 清空前不能分配第二个 TCP 序号。
- 同一链路存在待确认状态同步时, 再次提交状态同步返回 dropped_busy, 不生成不同 seq 的同步帧。
- 低优先级 API 调用被高优先级发送意图覆盖时返回 dropped_priority, 不由通信层补发。
- ACK 槽确认对象不同时, 新 ACK 覆盖尚未写出的 ACK 候选, 被覆盖对象由对端重发恢复。
- 全局发送闸口每周期最多放行一帧。
- ACK 优先级高于 TCP 业务帧。
- TCP 业务帧优先级高于 UDP。
- RX 读取限幅和积压清理。
- 残缺帧、非法 topic、非法方向和溢出输入不进入业务层。
- Runtime 和状态协调层不直接调用 UART 读写。
- 单个主循环周期内, 每个 UART 端口只执行一轮通信服务 RX 请求。
- TCP、UDP 和 ACK 在同一周期只能通过统一 TX 仲裁入口请求写出, 每个端口不存在第二个发送入口。

主机侧测试至少覆盖业务等价:

- 主车搜索、绕行、搬运、收尾、回到搜索的完整状态流。
- 辅车 follow、idle、approach、orbit、transport、clear 的完整状态流。
- 双车实例联动完成完整状态圈: 主车搜索物体、主车绕行、辅车找物体、辅车绕行、双方对正、搬运、退到边线、进入下一次搜索。
- 主车本地视觉 hook ACK 后才激活对应 context_id。
- 主车本地视觉事件 context_id 不匹配时不触发状态跳转。
- 主车本地视觉事件早于 hook ACK 到达时只暂存一次, hook ACK 后再消费。
- 辅车收到重复 ASSISTANT_STATE_SYNC 时只 ACK, 不重复清空速度或重复下发本地视觉任务。
- 主车收到重复 ASSISTANT_EVENT_REPORT 时只 ACK, 不重复推进状态。
- 辅车收到重复本地视觉事件时只 ACK, 不重复生成主辅回报。
- UART6 速度和 UART8 速度的融合结果与既定业务语义一致。
- UDP 没有新帧时保持最后一次合法输入, 状态切换时由状态协调层清空对应缓存。
- TCP ACK 丢失、业务帧重发和重复帧场景下车辆行为不重复执行。
- 每个通信调度周期最多实际写出一帧, UART6 和 UART8 共享该约束。
- 同一周期同时存在 TCP 与 UDP 发送意图时只发送一帧。
- 状态协调层按 150ms 节奏推进可靠同步, 高频执行层按控制周期继续消费最新 UDP。

板端联调至少观察:

- 两车同时运行时不死机。
- 丢包场景下 TCP 状态同步可恢复。
- UDP 高频数据不积压。
- 通信诊断计数可解释现场现象。
