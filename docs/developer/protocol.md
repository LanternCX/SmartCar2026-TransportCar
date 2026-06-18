# 串口通信协议

## 文档边界

本文件用于帮助开发者快速理解当前串口通信协议的分层、入口和业务包种类。它不是实现依据, 也不应该作为 agent 修改代码时的唯一上下文。

协议字段、topic 注册、body 长度、方向约束、发送仲裁、缓存处理和异常计数都以真实代码与行为测试为准:

- 通信入口: [src/protocol/](../../src/protocol/)
- 通信配置: [src/config/comm.py](../../src/config/comm.py)
- 主车运行时: [src/vision/master/forward_runtime.py](../../src/vision/master/forward_runtime.py)
- 辅车运行时: [src/vision/assistant/follow_runtime.py](../../src/vision/assistant/follow_runtime.py)
- 协议测试: [tests/unit/protocol/](../../tests/unit/protocol/)
- 运行时行为测试: [tests/unit/runtime/](../../tests/unit/runtime/)

修改协议时, 先改代码和行为测试, 再同步本文件。agent 读取本文件后仍必须继续读取对应代码, 不能只按本文推断实现细节。

## 链路分工

| 串口 | 连接对象 | 主要用途 |
| --- | --- | --- |
| `UART3` | 调试终端 <-> 车端 | REPL、日志和现场调试 |
| `UART6` | 本车 RT1021 <-> 本车 OpenART | 本地视觉速度、视觉观测、视觉任务同步、视觉事件回报 |
| `UART8` | 主车 <-> 辅车 | 主车速度前馈、辅车状态同步、辅车事件回报 |

两台车各自使用本车硬件上的 `UART6`, 主车 `UART6` 与辅车 `UART6` 不是同一条物理链路。`UART3` 不进入正式传输层。

## 分层模型

正式串口通信全部使用固定长度 `bytes` 帧。业务层只处理 topic 与 body bytes, 不直接读写 UART, 不直接清 UART 缓冲, 不直接处理 ACK 或重发。

通信层负责:

- 统一 `UART6` 与 `UART8` 的 RX / TX 调度。
- 限制单次 RX 读取长度, 输入积压时按过载处理清空端口残留输入。
- 在输入 bytes 中扫描可通过 topic、端口、模式和角色方向校验的固定帧, 常规残片跨周期拼帧, 过载残片直接丢弃。
- 校验 topic、端口、模式、角色方向和 body 长度。
- 管理 UDP 最新值槽、TCP 停止等待槽和 ACK 候选。
- 保证一次 `poll_tx()` 最多写出一帧。
- 提供诊断计数, 便于联调观察丢弃、重发和发送数量。

业务层负责:

- 把业务枚举、定点数和状态值编码成固定 body bytes。
- 通过 `udp(port)` / `tcp(port)` 读写 topic。
- 通过 `delivery(topic)` 判断可靠包交付状态。
- 在状态机中处理读到的业务数据。

## 帧结构

物理帧长度由 `src/config/comm.py` 定义。当前帧结构由 `src/protocol/frame.py` 编解码:

```text
HEAD  : 1 byte
MODE  : 1 byte
TOPIC : 1 byte
SEQ   : 1 byte
BODY  : 固定槽位 bytes
CRC8  : 1 byte
```

当前配置:

```text
TRANSPORT_FRAME_HEAD = 0xA5
TRANSPORT_FRAME_BODY_SIZE = 10
TRANSPORT_FRAME_SIZE = 15
```

车端帧头用于在串口字节流中重新定位业务帧。CRC8 覆盖 `MODE/TOPIC/SEQ/BODY`, 用于过滤错位后碰巧像合法 topic 的假帧。无线模块自身仍按模块参数执行空中链路校验和重发, 车端 CRC 只负责业务层分帧安全。

`BODY` 是固定槽位。每个 topic 在注册表中声明有效 body 长度, 写入时必须正好匹配该长度, 组帧时补齐固定槽位, 接收时按注册表裁出有效 body。

## 传输模式

```text
MODE_UDP = 0x01
  含义: 最新值数据
  行为: 不确认, 不重发, 不排队

MODE_TCP = 0x02
  含义: 可靠业务数据
  行为: 停止等待, ACK 确认, 到节奏点重发, 接收端按 topic + seq 去重

MODE_ACK = 0x03
  含义: TCP 确认帧
  行为: TOPIC 与 SEQ 指向被确认的 TCP 帧, BODY 槽位补 0
```

ACK 封装在 TCP 可靠传输内部, 不是业务层单独读写的 topic。

## API 形态

正式 API 只接收 bytes-like body, 不把字符串作为传输正文。

```python
transport = create_transport(role, uart6=uart6, uart8=uart8, now_ms=now_ms)

transport.poll_rx()
transport.poll_tx()

transport.udp(UART6).write(topic, body)
transport.udp(UART6).read(topic, out_body)

transport.tcp(UART8).write(topic, body)
transport.tcp(UART8).read(topic, out_body)
transport.tcp(UART8).delivery(topic)

transport.diagnostics(UART6)
transport.diagnostics(UART8)
```

调用约束:

```text
write(topic, body)
  body 必须是 bytes、bytearray 或 memoryview
  body 长度必须等于 topic 注册表中的有效长度
  写入只提交发送意图, 不直接写 UART

read(topic, out_body)
  out_body 必须是 bytearray 或 memoryview
  读取只消费通信层缓存, 不直接读 UART

poll_rx()
  每个调度周期对每个端口执行一轮受限读取

poll_tx()
  每次调用最多写出一帧
```

写入返回值:

```text
accepted
overwritten
dropped_priority
dropped_busy
invalid
```

读取返回值:

```text
ok
empty
invalid
```

可靠交付状态:

```text
idle
pending
delivered
dropped
invalid
```

## 发送仲裁

`poll_tx()` 的全局优先级为:

```text
ACK > TCP > UDP
```

同一次 `poll_tx()` 最多写出一帧。TCP 到期重发时在 `UART6` 与 `UART8` 之间轮转选择, 避免一个端口长期占用发送机会。

UDP 不排队, 只保留当前最新值候选。同 topic 新包覆盖旧包。ACK 或本周期待进入可靠槽的 TCP 意图存在时, UDP 写入会直接返回 `dropped_priority`。

TCP 每个端口只有一个可靠发送槽。发送槽空闲时, 本周期 TCP 写入先进入意图槽; 同一端口意图槽内的新写入覆盖旧写入。意图进入发送槽后才分配 seq。发送槽等待 ACK 时, 新 TCP 写入返回 `dropped_busy`。

ACK 只保留一个全局候选。多个确认对象同时出现时, 尚未写出的 ACK 候选按最新确认对象覆盖, 并记录覆盖计数。

## 可靠业务包的零速度语义

可靠业务包用于建立状态切换边界。业务层收到会触发状态切换的 TCP 事件或状态同步包时, 先把对应速度输入源解释为零速度, 再处理状态机事件。这个语义不适用于 ACK, ACK 只表达传输确认。

当前零速度边界:

```text
MASTER_VISION_EVENT_REPORT
  接收方: 主车
  清理: 主车本地视觉速度输入

ASSISTANT_STATE_SYNC
  接收方: 辅车
  清理: 辅车本地视觉速度输入与主车前馈速度输入

ASSISTANT_VISION_EVENT_REPORT
  接收方: 辅车
  清理: 辅车本地视觉速度输入

ASSISTANT_EVENT_REPORT
  接收方: 主车
  清理: 主车本地视觉速度输入

LOCAL_VISION_CONTROL
  接收方: 主车 / 辅车
  PAUSE: 清理本车本地视觉速度输入并写入零速度
  RESUME: 清理恢复前缓存的本地视觉速度输入, 后续只接收新的 UDP 速度
```

发送方在稳定命中后停止继续发送高频 UDP 速度包, 后续发送机会留给 TCP 事件或状态同步。接收方不依赖最后一帧 UDP 零速度到达来清理运动状态。

## 接收与缓存

通信层每轮 RX 对每个端口只主动请求一次读取。若 `uart.any()` 返回的待读长度超过 `TRANSPORT_RX_READ_LIMIT`, 本轮按上限读取一段并清空端口残留输入。可靠同步和高频速度不应在同一链路的同一发送轮次同时写出, 过载清理主要用于丢弃高频最新值积压。

接收 chunk 会逐字节扫描带帧头且 CRC8 正确的固定帧, 不要求本轮读取起点天然对齐到帧头。常规尾部不足一帧的 bytes 保存在端口残片缓存中, 后续 RX 周期先拼接再扫描；过载清理发生时丢弃当前残片并重新对齐。非法 topic、非法端口、非法模式、角色方向不匹配的帧都会丢弃。

UDP 接收槽按 topic 保存最新 body, 并维护版本号。业务层可以用版本号判断状态切换前后的旧输入。

TCP 接收槽每个端口只保留一份已交付给业务层前的可靠包。重复 TCP 帧会重新调度 ACK, 不重复交付 body。

## Topic 注册

topic 注册表在 [src/protocol/topic.py](../../src/protocol/topic.py) 中维护。所有业务包必须预注册 topic、模式、端口、有效 body 长度和角色读写方向。

当前 topic:

```text
0x01 LOCAL_VISION_VELOCITY
  mode: UDP
  port: UART6
  body_size: 7
  direction: OpenART -> 主车 / 辅车
  body: velocity

0x02 ASSISTANT_FEEDFORWARD_VELOCITY
  mode: UDP
  port: UART8
  body_size: 7
  direction: 主车 -> 辅车
  body: velocity

0x03 VISION_OBSERVATION
  mode: UDP
  port: UART6
  body_size: 7
  direction: OpenART -> 主车 / 辅车
  body: vision_observation

0x04 LOCAL_VISION_CONTROL
  mode: TCP
  port: UART6
  body_size: 1
  direction: OpenART -> 主车 / 辅车
  body: local_vision_control
  action: 1=PAUSE, 2=RESUME

0x10 MASTER_VISION_TASK_SYNC
  mode: TCP
  port: UART6
  body_size: 5
  direction: 主车 -> 本车 OpenART
  body: master_vision_task_sync

0x11 ASSISTANT_VISION_TASK_SYNC
  mode: TCP
  port: UART6
  body_size: 10
  direction: 辅车 -> 本车 OpenART
  body: assistant_vision_task_sync

0x12 MASTER_VISION_EVENT_REPORT
  mode: TCP
  port: UART6
  body_size: 10
  direction: OpenART -> 主车
  body: master_vision_event_report

0x13 ASSISTANT_VISION_EVENT_REPORT
  mode: TCP
  port: UART6
  body_size: 3
  direction: OpenART -> 辅车
  body: assistant_vision_event_report

0x20 ASSISTANT_STATE_SYNC
  mode: TCP
  port: UART8
  body_size: 10
  direction: 主车 -> 辅车
  body: assistant_state_sync

0x21 ASSISTANT_EVENT_REPORT
  mode: TCP
  port: UART8
  body_size: 3
  direction: 辅车 -> 主车
  body: assistant_event_report
```

## Body 编码

body 编解码入口在 [src/protocol/codec.py](../../src/protocol/codec.py)。多字节整数使用小端序。有符号整数使用补码。速度和观测浮点量使用定点比例 `1000`, 编码到 `i16` 时做饱和。

```text
velocity, 7 bytes
  0..1: vx, i16, scale 1000
  2..3: vy, i16, scale 1000
  4..5: omega, i16, scale 1000
  6   : has_omega, u8

vision_observation, 7 bytes
  0   : context_id, u8
  1..2: x, i16, scale 1000
  3..4: y, i16, scale 1000
  5..6: value, i16, scale 1000

master_vision_task_sync, 5 bytes
  0   : context_id, u8
  1   : state, u8
  2   : target, u8
  3..4: arg, i16

assistant_vision_task_sync, 10 bytes
  0   : state, u8
  1   : target, u8
  2..3: arg, i16
  4..9: threshold, i8[6]

master_vision_event_report, 10 bytes
  0   : context_id, u8
  1   : event, u8
  2..3: value, i16
  4..9: threshold, i8[6]

assistant_vision_event_report, 3 bytes
  0   : event, u8
  1..2: value, i16

assistant_state_sync, 10 bytes
  0   : state, u8
  1   : target, u8
  2..3: arg, i16
  4..9: threshold, i8[6]

assistant_event_report, 3 bytes
  0   : event, u8
  1..2: value, i16

其中 `assistant_vision_task_sync.arg` 与 `assistant_state_sync.arg` 在找物体、绕行修正和搬运对正阶段共用同一打包语义：

```text
arg low byte  : 本地视觉配置编号
arg high byte : 物体编号
```

主车搜索阶段的 `MASTER_VISION_EVENT_REPORT / EVENT_TARGET_FOUND` 在正式主线中使用 `value` 回传主车当前选中的物体编号, 并使用 `threshold` 回传当前动态阈值。车端把物体编号和阈值同步到辅车与辅车本地视觉。
```

## 业务读写入口

主车和辅车运行时只通过通信服务读写协议包。统一主循环在每拍执行:

```text
poll_rx()
runtime.step()
poll_tx()
```

主车主要读写:

```text
UART6 UDP read  LOCAL_VISION_VELOCITY
UART6 TCP write MASTER_VISION_TASK_SYNC
UART6 TCP read  MASTER_VISION_EVENT_REPORT

UART8 UDP write ASSISTANT_FEEDFORWARD_VELOCITY
UART8 TCP write ASSISTANT_STATE_SYNC
UART8 TCP read  ASSISTANT_EVENT_REPORT
```

辅车主要读写:

```text
UART6 UDP read  LOCAL_VISION_VELOCITY
UART6 TCP write ASSISTANT_VISION_TASK_SYNC
UART6 TCP read  ASSISTANT_VISION_EVENT_REPORT

UART8 UDP read  ASSISTANT_FEEDFORWARD_VELOCITY
UART8 TCP read  ASSISTANT_STATE_SYNC
UART8 TCP write ASSISTANT_EVENT_REPORT
```

## 行为约束入口

协议和运行时行为由测试约束。阅读或修改协议时优先查看:

```text
tests/unit/protocol/test_frame.py
  固定帧编解码、bytes 类型约束、body 槽位约束

tests/unit/protocol/test_topic.py
  topic 注册、端口约束、角色方向约束、body 长度约束

tests/unit/protocol/test_codec.py
  业务 body 编解码和定点数饱和

tests/unit/protocol/test_transport_api.py
  udp/tcp API 返回值、优先级丢弃、delivery 与 diagnostics

tests/unit/protocol/test_transport_reliable.py
  TCP 停止等待、ACK、重发、去重和槽位约束

tests/unit/protocol/test_transport_rx_tx.py
  单轮 RX、溢出清理、单次 TX 只发一帧、ACK 优先级

tests/unit/runtime/test_transport_runtime_surface.py
  主车 / 辅车 runtime 对通信层的调用边界

tests/unit/runtime/test_dual_vehicle_communication_flow.py
  主辅车从寻找目标到收尾再回到寻找目标的通信流程
```

## 变更规则

新增或修改业务包时, 需要同步检查:

```text
1. src/protocol/topic.py
   注册 topic、模式、端口、body_size 和角色读写方向

2. src/protocol/codec.py
   定义 body bytes 编解码

3. src/protocol/transport.py
   仅在调度语义变化时修改

4. 主车 / 辅车 runtime
   调整业务读写位置和状态机消费逻辑

5. tests/unit/protocol/ 与 tests/unit/runtime/
   补齐协议行为和整车通信行为约束

6. docs/developer/protocol.md
   在代码和测试稳定后同步开发者阅读入口
```

正式协议不维护兼容层。任何协议正文、topic 编号或 body 布局变化都必须让行为测试表达清楚, 避免文档和实现各说各话。
