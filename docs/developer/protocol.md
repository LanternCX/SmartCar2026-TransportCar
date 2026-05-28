# 串口通信协议

## 文档边界

本文件只维护链路分工和协议阅读入口。短包字段、解析规则、格式化规则、序号边界和异常输入处理以代码与契约测试为准。

## 链路分工

| 串口 | 连接对象 | 主要用途 |
| --- | --- | --- |
| `UART3` | 调试终端 <-> 车端 | REPL、日志和现场调试 |
| `UART8` | 主车 <-> 辅车 | 速度前馈、辅车子状态同步、辅车结果回报 |
| `UART6` | 本车 RT1021 <-> 本车 OpenART | 本地视觉速度、视觉 hook 同步、视觉事件回报 |

两台车各自使用本车硬件上的 `UART6`，主车 `UART6` 与辅车 `UART6` 不是同一条物理链路。

## 协议分层

- 高频数据流使用短包承载速度或观测信息，允许丢包，接收端按最近有效输入理解。
- 低频同步和结果回报使用可靠短包，发送端等待确认，接收端对重复包做幂等处理。
- `UART8` 半双工轮转使用 `t` 短包，由主车发起，只表达辅车可以回传待发送可靠事件。
- 辅车收到主车 `UART8` 状态同步后在下一拍回 ACK，避免接收后立刻反向写导致链路竞争。
- 可靠传输序号只表达传输身份，业务上下文编号只表达当前视觉或状态上下文。
- 状态切换由角色状态机判断，协议解析层不拥有业务状态机。

## 代码阅读顺序

1. 主车本车视觉通用短包: [src/protocol/packet.py](../../src/protocol/packet.py)
2. 辅车 `UART8` 状态同步短包: [src/vision/assistant/uart8_packet.py](../../src/vision/assistant/uart8_packet.py)
3. 主车 `UART8` 回报短包: [src/vision/master/uart8_packet.py](../../src/vision/master/uart8_packet.py)
4. 辅车速度输入拆分: [src/vision/assistant/velocity_packet.py](../../src/vision/assistant/velocity_packet.py)
5. 通信参数: [src/config/comm.py](../../src/config/comm.py)

## 行为事实入口

- 协议格式与字段契约: [tests/contract/serial_protocol/test_serial_packet_protocol_contract.py](../../tests/contract/serial_protocol/test_serial_packet_protocol_contract.py)
- 辅车速度协议契约: [tests/contract/serial_protocol/test_assistant_velocity_protocol_contract.py](../../tests/contract/serial_protocol/test_assistant_velocity_protocol_contract.py)
- 主车运行时通信行为: [tests/unit/runtime/test_master_forward_runtime.py](../../tests/unit/runtime/test_master_forward_runtime.py)
- 辅车运行时通信行为: [tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py](../../tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py)

## 变更入口

新增字段、包类型或链路前，先确认它是高频数据流还是可靠同步，再修改解析/格式化代码和契约测试。需要追溯协议设计背景时查 [docs/superpowers/memory/milestone/INDEX.md](../superpowers/memory/milestone/INDEX.md)。
