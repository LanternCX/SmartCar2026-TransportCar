# 固定帧通信链路实现计划

执行状态: Archive

> 给 Agent 工作者: 使用 `superpowers:subagent-driven-development` 按任务逐项实现。每个任务完成后由主线程 review diff、运行对应验证命令, 再进入下一个任务。

## 目标

按 `docs/superpowers/specs/2026-05-29-fixed-frame-transport-link-design.md` 重构主车、辅车和本地视觉通信链路, 让 UART6 与 UART8 的正式通信全部通过 `src/protocol/` 下的固定长度 bytes 帧、统一 TCP / UDP API、统一 RX / TX 调度和固定槽可靠通信完成。

## 架构边界

通信层只保留在 `src/protocol/`。`src/config/comm.py` 只放参数, 不承载实现。主车 Runtime、辅车 Runtime 和共享底盘 Runtime 不直接读写 UART, 只通过通信服务读取业务 body bytes 或提交待发送 body bytes。

入口主循环按固定顺序执行: 通信 RX -> 低频协调与高频执行 -> 通信 TX。每个通信调度周期全局最多写出一帧, UART6 和 UART8 共享发送闸口。

## 文件结构

- 新建: `src/protocol/frame.py`  
  固定帧编解码, 只处理 MODE、TOPIC、SEQ 和固定 BODY 槽。
- 新建: `src/protocol/topic.py`  
  topic 注册表、body 长度、允许模式、允许端口和角色方向约束。
- 新建: `src/protocol/codec.py`  
  速度、观测、状态同步和事件 body bytes 编解码。
- 新建: `src/protocol/transport.py`  
  `udp(port)`、`tcp(port)`、`diagnostics(port)` 对外入口, 固定槽缓存、RX 限幅、TX 仲裁、ACK、重发和去重。
- 修改: `src/protocol/__init__.py`  
  导出对外 API、topic 编号和固定状态码。
- 修改: `src/config/comm.py`  
  增加固定帧长度、BODY 长度、RX 上限、UDP 发送周期、TCP 发送周期和端口逻辑名。
- 修改: `src/script/remote_control.py`  
  创建独立通信服务, 在主循环中调度 RX / 业务 / TX。
- 修改: `src/vision/master/runtime.py`、`src/vision/assistant/runtime.py`  
  按角色装配通信服务和角色运行时。
- 修改: `src/vision/master/forward_runtime.py`  
  移除 UART 直接读写, 改为消费通信层缓存和提交 topic body bytes。
- 修改: `src/vision/assistant/follow_runtime.py`  
  移除 UART 直接读写, 改为消费通信层缓存和提交 topic body bytes。
- 删除或清空职责: `src/vision/master/uart8_packet.py`、`src/vision/assistant/uart8_packet.py`、`src/vision/assistant/velocity_packet.py`  
  相关文本短包职责迁移到 `src/protocol/codec.py` 与通信层行为测试。
- 修改: `tests/contract/serial_protocol/`  
  协议契约从文本短包切换到固定 bytes 帧。
- 修改: `tests/unit/protocol/`  
  覆盖固定帧、topic、codec、transport 和调度行为。
- 修改: `tests/unit/runtime/`  
  覆盖主车、辅车运行时接入通信层后的行为等价。
- 新建: `tests/unit/runtime/test_dual_vehicle_communication_flow.py`  
  实例化主车和辅车, 覆盖完整状态圈。

## Task 1: 固定帧与 topic 注册表

**目标:** 建立 bytes 帧和 topic 注册表的底层契约, 让后续任务不再依赖文本短包。

**文件:**
- 新建: `src/protocol/frame.py`
- 新建: `src/protocol/topic.py`
- 修改: `src/protocol/__init__.py`
- 修改: `src/config/comm.py`
- 修改: `tests/unit/protocol/test_packet.py`
- 新建: `tests/unit/protocol/test_frame.py`
- 新建: `tests/unit/protocol/test_topic.py`
- 修改: `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`

**步骤:**
- [ ] 写固定帧行为测试: 长度固定为 11B, BODY 固定为 8B, MODE / TOPIC / SEQ 位置固定, 未使用 BODY 字节补 0。
- [ ] 写 topic 注册表行为测试: 未注册 topic、错误模式、错误端口、错误角色方向和错误 body 长度都返回非法。
- [ ] 写正式协议拒绝字符串 body 的行为测试。
- [ ] 实现 `frame.py` 与 `topic.py` 的最小功能。
- [ ] 更新 `src/protocol/__init__.py` 的导出。
- [ ] 运行 `uv run --group test python -m pytest tests/unit/protocol tests/contract/serial_protocol -q`。

**Review 要点:**
- topic 总表必须完整覆盖 `0x01`、`0x02`、`0x03`、`0x10`、`0x11`、`0x12`、`0x13`、`0x20`、`0x21`。
- 正式协议不得保留文本行、逗号字段或字符串换行作为传输格式。
- 不新增 `src/comm/`。

## Task 2: 业务 body bytes 编解码

**目标:** 用固定 body bytes 表达速度、观测、状态同步和事件, 保持业务数值语义稳定。

**文件:**
- 新建: `src/protocol/codec.py`
- 修改: `src/protocol/__init__.py`
- 修改: `tests/unit/protocol/test_packet.py`
- 新建: `tests/unit/protocol/test_codec.py`
- 修改: `tests/unit/vision/test_assistant_velocity_packet.py`

**步骤:**
- [ ] 写速度 body 往返测试: `vx`、`vy`、`omega`、`has_omega` 使用小端 i16 与 u8, 比例为 1000。
- [ ] 写观测 body 往返测试: `context_id`、`x`、`y`、`value` 长度为 7B。
- [ ] 写状态同步 body 往返测试: hook 同步、辅车本地视觉任务同步、主辅状态同步。
- [ ] 写事件 body 往返测试: 本地视觉事件与辅车回报事件。
- [ ] 写限幅与饱和测试: 常规速度、修正量和角速度参数处于协议可表达范围内。
- [ ] 实现 `codec.py`。
- [ ] 运行 `uv run --group test python -m pytest tests/unit/protocol tests/unit/vision -q`。

**Review 要点:**
- 编解码函数返回或写入 bytes-like 数据, 不在热路径生成调试字符串。
- UART6 速度只贡献平移量, UART8 前馈可携带 omega, 由业务层决定是否消费。

## Task 3: 通信服务固定槽与公开 API

**目标:** 建立 `udp(port)`、`tcp(port)`、`diagnostics(port)` 的固定槽 API, 不触碰真实 UART。

**文件:**
- 新建: `src/protocol/transport.py`
- 修改: `src/protocol/__init__.py`
- 新建: `tests/unit/protocol/test_transport_api.py`

**步骤:**
- [ ] 写 API 格式行为测试: `udp(port).write(topic, body)`、`udp(port).read(topic, out_body)`、`tcp(port).write(topic, body)`、`tcp(port).read(topic, out_body)`、`tcp(port).delivery(topic)`、`diagnostics(port)`。
- [ ] 写状态码行为测试: `accepted`、`overwritten`、`dropped_priority`、`dropped_busy`、`invalid`、`ok`、`empty`、`idle`、`pending`、`delivered`、`dropped`。
- [ ] 写内存语义测试: 写 API 复制 body 到固定槽, 不保存调用方引用; 读 API 写入调用方提供的 out_body, 不创建业务 bytes。
- [ ] 写 UDP 最新值测试: 同一 port + topic 新 body 覆盖旧 body, 读取不消费。
- [ ] 写 TCP 固定发送槽测试: 槽忙返回 `dropped_busy`, 不缓存新请求, 不分配新序号。
- [ ] 实现固定槽 API。
- [ ] 运行 `uv run --group test python -m pytest tests/unit/protocol/test_transport_api.py -q`。

**Review 要点:**
- 每个 port + topic 的缓存数量固定。
- API 不接受 `str`。
- `tcp_delivery` 和 `diagnostics` 不触发发送。

## Task 4: RX 限幅、切帧、ACK、重发与 TX 仲裁

**目标:** 完成通信服务的底层收发规则, 保证每个周期只有统一发送闸口写出一帧。

**文件:**
- 修改: `src/protocol/transport.py`
- 新建: `tests/unit/protocol/test_transport_rx_tx.py`
- 新建: `tests/unit/protocol/test_transport_reliable.py`

**步骤:**
- [ ] 写 RX 限幅测试: 单次读取长度受限, 溢出时清空本轮积压, 残缺尾部不进入业务层。
- [ ] 写非法帧测试: 非法 mode、topic、端口、方向和 body 长度都丢弃并计数。
- [ ] 写 ACK 行为测试: ACK 使用被确认帧 TOPIC 与 SEQ, BODY 补 0; 重复确认合并。
- [ ] 写 ACK 覆盖测试: 不同确认对象同时存在时, 新 ACK 覆盖尚未写出的 ACK 候选。
- [ ] 写 TCP 停止等待测试: 每条链路只有一个 active_seq, ACK 匹配后释放, 未确认按 150ms 重发。
- [ ] 写重复帧去重测试: 重复 TCP 帧必须 ACK, 不能重复交付业务层。
- [ ] 写接收交付槽满测试: 新 TCP 帧不确认, 由发送侧重发恢复。
- [ ] 写 TX 仲裁测试: 每周期全局最多写一帧, 优先级为 ACK > TCP > UDP。
- [ ] 写同模式选择测试: TCP 多端口同时到期按轮转选择, UDP 本周期多个意图按最后写入者作为发送候选。
- [ ] 实现 RX / TX / ACK / 重发 / 去重 / 仲裁。
- [ ] 运行 `uv run --group test python -m pytest tests/unit/protocol -q`。

**Review 要点:**
- 不维护可靠消息队列。
- 不在热路径拼接字符串或创建无界列表。
- UART6 和 UART8 共享全局发送额度。

## Task 5: 状态协调层抽出与主车接入

**目标:** 主车角色只处理业务状态, 不直接处理 UART、ACK、重发或文本包。

**文件:**
- 修改: `src/vision/master/forward_runtime.py`
- 修改: `src/vision/master/runtime.py`
- 修改: `src/script/remote_control.py`
- 修改: `tests/unit/runtime/test_master_forward_runtime.py`
- 修改: `tests/unit/entry/test_remote_control_role_dispatch.py`

**步骤:**
- [ ] 写主车运行时通信边界测试: 主车 Runtime 不直接调用 UART `any`、`read`、`write`。
- [ ] 写主循环调度测试: 每个端口每周期只由通信服务执行一轮 RX 请求。
- [ ] 写主车 UART6 视觉速度消费测试: 搜索、绕行、搬运阶段速度融合结果保持一致。
- [ ] 写主车本地视觉 hook 测试: hook 走 `MASTER_VISION_HOOK_SYNC`, ACK 后激活 context_id。
- [ ] 写主车本地视觉事件测试: context_id 不匹配不跳转, ACK 前到达只暂存一次。
- [ ] 写主车 UART8 状态同步测试: `ASSISTANT_STATE_SYNC` 槽忙时返回 `dropped_busy`, 不生成第二个不同 seq。
- [ ] 写主车前馈测试: `ASSISTANT_FEEDFORWARD_VELOCITY` 走 UDP, 与可靠同步同周期时只通过统一 TX 闸口发送一帧。
- [ ] 接入通信服务并移除主车直接 UART 读写路径。
- [ ] 运行 `uv run --group test python -m pytest tests/unit/runtime/test_master_forward_runtime.py tests/unit/entry/test_remote_control_role_dispatch.py -q`。

**Review 要点:**
- 主车不保留第二套发送互斥标志。
- 主车状态协调按 150ms 节奏提交可靠同步。
- 可靠状态同步槽忙时丢弃本次提交, 由协调层下一周期按状态重新提交。

## Task 6: 辅车接入与业务等价

**目标:** 辅车角色只通过通信层消费本地视觉、主车同步和主车前馈, 并通过通信层回报事件。

**文件:**
- 修改: `src/vision/assistant/follow_runtime.py`
- 修改: `src/vision/assistant/runtime.py`
- 修改: `src/vision/assistant/diagnostics.py`
- 修改: `tests/unit/runtime/test_assistant_follow_runtime_public_api.py`
- 修改: `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`
- 修改: `tests/unit/runtime/test_assistant_follow_runtime_error_handling.py`
- 修改: `tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py`

**步骤:**
- [ ] 写辅车运行时通信边界测试: 辅车 Runtime 不直接调用 UART `any`、`read`、`write`。
- [ ] 写辅车主辅状态同步测试: 重复 `ASSISTANT_STATE_SYNC` 只 ACK, 不重复清空速度或重复下发本地视觉任务。
- [ ] 写辅车本地视觉任务同步测试: `ASSISTANT_VISION_TASK_SYNC` 槽忙返回 `dropped_busy`, 不生成第二个不同 seq。
- [ ] 写辅车本地视觉事件测试: 事件只在当前子状态接受时生成待回报事件。
- [ ] 写辅车回报测试: `ASSISTANT_EVENT_REPORT` 走 TCP, 重复帧或 ACK 丢失时不重复推进状态。
- [ ] 写辅车速度融合测试: follow、approach、orbit、transport、clear 阶段保持业务语义一致。
- [ ] 接入通信服务并移除辅车直接 UART 读写路径。
- [ ] 运行 `uv run --group test python -m pytest tests/unit/runtime/test_assistant_follow_runtime_public_api.py tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py tests/unit/runtime/test_assistant_follow_runtime_error_handling.py tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py -q`。

**Review 要点:**
- 辅车子状态只由 `ASSISTANT_STATE_SYNC` 驱动。
- UART6 omega 不贡献控制, UART8 omega 只在消费前馈时使用。
- 收尾阶段不消费速度流。

## Task 7: 双车完整状态圈行为测试

**目标:** 用主车和辅车两个实例约束完整业务流程, 防止协议重构改变车辆行为。

**文件:**
- 新建: `tests/unit/runtime/test_dual_vehicle_communication_flow.py`
- 修改: `tests/unit/runtime/assistant_follow_runtime_support.py`
- 修改: `tests/unit/runtime/test_master_forward_runtime.py`
- 修改: `tests/unit/runtime/test_assistant_follow_runtime_velocity_flow.py`

**步骤:**
- [ ] 建立内存串口桩, 让两个通信服务通过 bytes 帧互连 UART8。
- [ ] 建立本地视觉桩, 分别向主车和辅车 UART6 注入 UDP 速度、TCP ACK 和 TCP 事件。
- [ ] 写完整状态圈测试: 主车搜索物体、主车绕行、辅车找物体、辅车绕行、双方对正、搬运、退到边线、进入下一次搜索。
- [ ] 写丢包与重发测试: ACK 丢失、业务帧重发和重复帧不导致重复状态跳转。
- [ ] 写单周期访问测试: 每个通信调度周期每个端口只执行一次 RX, 每周期全局最多实际写一帧。
- [ ] 运行 `uv run --group test python -m pytest tests/unit/runtime/test_dual_vehicle_communication_flow.py -q`。

**Review 要点:**
- 测试断言业务状态和关键动作, 不断言实现内部临时变量。
- 不为测试保留文本短包兼容入口。

## Task 8: 清理文本协议入口和过期测试

**目标:** 删除正式链路上的文本短包入口, 只保留固定 bytes 帧协议。

**文件:**
- 修改或删除: `src/protocol/packet.py`
- 修改或删除: `src/protocol/link.py`
- 修改或删除: `src/vision/master/uart8_packet.py`
- 修改或删除: `src/vision/assistant/uart8_packet.py`
- 修改或删除: `src/vision/assistant/velocity_packet.py`
- 修改: `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`
- 修改: `tests/contract/serial_protocol/test_assistant_velocity_protocol_contract.py`
- 修改: `tests/unit/script/test_wireless_contention_test.py`

**步骤:**
- [ ] 删除正式运行链不再使用的文本短包解析与格式化测试。
- [ ] 删除 UART8 轮转短包相关测试, 用统一 TX 闸口和 TCP 停止等待测试覆盖发送互斥。
- [ ] 删除或收窄文本协议模块职责, 避免代码中同时存在两套正式协议。
- [ ] 更新无线竞争脚本测试, 明确它是压力观察工具, 不作为正式协议入口。
- [ ] 运行 `uv run --group test python -m pytest tests/contract/serial_protocol tests/unit/script -q`。

**Review 要点:**
- 正式运行链不能导入文本短包模块。
- 不保留兼容层。
- 仓库内只剩 `src/protocol/` 作为通信实现目录。

## Task 9: 全量回归与板端联调准备

**目标:** 收口本地行为测试, 准备板端验证所需的最小诊断面。

**文件:**
- 修改: `src/vision/master/forward_runtime.py`
- 修改: `src/vision/assistant/diagnostics.py`
- 修改: `src/protocol/transport.py`
- 修改: `tests/unit/core/test_diagnostics.py`
- 修改: `tests/unit/runtime/test_master_forward_runtime.py`
- 修改: `tests/unit/runtime/test_assistant_follow_runtime_diagnostics.py`

**步骤:**
- [ ] 写诊断快照测试: 只返回小整数计数、固定槽状态和最后错误码, 不返回业务 body。
- [ ] 写内存边界 review 记录: owner、加载阶段、常驻槽数量、触发条件和必要性。
- [ ] 运行 `uv run --group test python -m pytest tests/unit tests/contract/serial_protocol -q`。
- [ ] 运行 `uv run --group type pyright src tests`。
- [ ] 准备板端检查清单: 导入通信层、启动主车、启动辅车、观察两车同时运行、观察丢包恢复、观察 UDP 不积压、观察诊断计数。

**Review 要点:**
- 本地验证通过后才能进入板端路径。
- 板端验证需要用户确认设备连接和现场现象。
- 不把板端观察结论写成已完成状态, 除非有实际反馈。

## Task 10: 文档同步待触发任务

**目标:** 保留文档同步入口, 不在本实现计划中修改 `docs/developer/protocol.md`。

**文件:**
- 暂不修改: `docs/developer/protocol.md`

**步骤:**
- [ ] 实现完成并通过 review 后, 等待用户手动触发开发文档同步。
- [ ] 触发后只写当前事实、阅读入口和职责边界, 不镜像代码字段表。
- [ ] 触发后把对应 spec 和 plan 标记为 `Archive`。

**Review 要点:**
- 本计划执行期间不得主动修改 `docs/developer/protocol.md`。
- 文档不得使用历史性口吻。

## 全局验证命令

- 协议层: `uv run --group test python -m pytest tests/unit/protocol tests/contract/serial_protocol -q`
- 运行时: `uv run --group test python -m pytest tests/unit/runtime -q`
- 入口层: `uv run --group test python -m pytest tests/unit/entry -q`
- 全量本地: `uv run --group test python -m pytest tests/unit tests/contract/serial_protocol -q`
- 类型检查: `uv run --group type pyright src tests`

## 完成条件

- 四个正式 API 与 spec 固定格式一致。
- UART6 和 UART8 都通过同一通信服务完成 RX / TX。
- 主车、辅车和共享底盘 Runtime 不直接读写 UART。
- 每个通信调度周期全局最多实际写出一帧。
- 每个通信调度周期内每个端口只执行一次 RX。
- TCP 单链路同一时刻只有一个 active_seq。
- 不同种类按 ACK > TCP > UDP 覆盖, 同种类按新包覆盖旧包。
- UDP 不排队, 只保留最新值。
- ACK 封装在 TCP 可靠通信内部, 不暴露业务 API。
- 双车完整状态圈行为测试通过。
- 本地全量测试和类型检查通过。
- 板端验证清单得到用户现场反馈。
