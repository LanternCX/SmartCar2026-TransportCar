# 主车物体搜索视觉闭环实施计划

> 状态: Archive
> 面向执行者: 使用 `superpowers:subagent-driven-development` 逐任务执行。本计划只作为编排入口, 不包含实现代码。
> 设计依据: `docs/superpowers/specs/2026-05-01-master-object-search-vision-design.md`

**目标:** 实现主车固定 `vx / vy` 搜索物体, 通过视觉 hook 确认物体稳定进入画面目标窗口后输出零平移速度。

**架构:** 主车 RT1021 与主车 OpenART 的本地 `UART6` 视觉链路采用对等可靠语义, `s` 同步包和需要可靠到达的 `r` 事件包都通过重复发送与 `a` 确认闭环。可靠确认使用 `reliable_seq`, 业务匹配使用 `context_id`, 避免同步确认和事件确认混淆。主车 RT1021 向 OpenART 建立视觉 hook 上下文, OpenART 在该上下文中持续发送观测, 并在 hook 条件满足时可靠回报事件。主车 RT1021 维护状态机并输出底盘速度, 搜索只使用车体系 `vx / vy`, 不显式接管角速度。

**技术栈:** MicroPython、OpenART、RT1021、ASCII 短包协议、pytest、`src/vision/master/`、`../SmartCar2026-Vision/master/`

---

## 文件范围与职责

### 车端仓库

- 修改: `docs/developer/protocol.md`
  - 登记主车本地视觉可靠 hook、`reliable_seq` 与 `context_id` 分离、主车视觉上下文同步、观测包和 hook 事件确认语义。
- 修改: `docs/developer/state.md`
  - 登记搜索状态流、hook 事件和状态跳转语义。
- 修改: `docs/developer/vision.md`
  - 区分主车视觉 hook 观测与辅车视觉速度修正。
- 修改: `docs/developer/control.md`
  - 说明主车搜索阶段只输出车体系 `vx / vy`。
- 修改: `src/config/params.py`
  - 增加搜索速度和 hook 配置参数。
- 修改: `src/hardware/uart_bus.py`
  - 将 `UART6` 说明扩展为本车本地视觉链路, 主车和辅车各自使用本车 `UART6`。
- 修改: `src/protocol/packet.py`
  - 支持 `s/a/o/r` 的可靠包序号和业务上下文字段。
- 修改: `src/protocol/link.py`
  - 承载数据流写出、可靠包写出和可靠重发时间判断。
- 修改: `src/vision/master/forward_runtime.py`
  - 接入主车视觉输入和输出, 建立 hook 上下文, 确认视觉事件, 调度主车搜索状态机。
- 新增或修改: `src/vision/master/` 下主车搜索纯逻辑模块
  - 承载状态推进、上下文编号、可靠包序号、事件匹配和底盘速度决策。
- 修改: `tests/unit/runtime/test_master_forward_runtime.py`
  - 覆盖主车搜索状态运行行为、hook 同步和事件跳转。
- 新增或修改: `tests/unit/vision/` 下主车搜索逻辑测试
  - 覆盖上下文匹配、事件过滤和状态推进。
- 新增或修改: `tests/unit/protocol/` 下协议工具测试
  - 覆盖短包解析、格式化和可靠写出工具。
- 修改: `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`
  - 覆盖主车视觉同步、观测和事件契约。

### Vision 仓库

- 修改: `../SmartCar2026-Vision/master/main.py`
  - 接收主车视觉上下文, 回确认, 输出观测短包, 在 hook 条件满足时输出事件。
- 边界: `../SmartCar2026-Vision/assistant/main.py`
  - 辅车视觉只发送 `v,<vx>,<vy>` 数据流, 不接入 hook、可靠包、可靠确认和状态同步。
- 修改: `../SmartCar2026-Vision/tests/contract/`
  - 覆盖主车视觉同步确认、观测短包和事件短包契约。
- 修改: `../SmartCar2026-Vision/tests/unit/`
  - 覆盖目标点误差、无目标零观测、目标面积上报、hook 稳定判断。
- 修改: `../SmartCar2026-Vision/README.md`
  - 说明 master 与 assistant 的输出职责和 master 的 hook 输入职责。

## Task 1: 扩充协议与开发文档

**目标:** 定义视觉端协议、主车本地视觉可靠通信、编号分层和串口发送节流规则。

**文件:**

- 修改: `docs/developer/protocol.md`
- 修改: `docs/developer/state.md`
- 修改: `docs/developer/vision.md`
- 修改: `docs/developer/control.md`

**步骤:**

- [ ] 登记 `UART6` 为本车 RT1021 与本车 OpenART 的本地视觉链路。
- [ ] 登记 Vision 端 master 与 assistant 的协议职责。
- [ ] 写清 `reliable_seq` 用于 `s/r` 可靠包确认、重发和去重。
- [ ] 写清 `context_id` 用于 `s/o/r` 的业务上下文匹配。
- [ ] 写清 `a,<reliable_seq>` 只确认可靠包, 不表达业务上下文。
- [ ] 写清每条链路每个发送方向同一时刻只维护一个待确认可靠包。
- [ ] 写清主车视觉使用 `s,<reliable_seq>,<context_id>,<state>,<target>,<arg>` 建立 hook 上下文。
- [ ] 写清主车视觉使用 `o,<context_id>,<x>,<y>,<value>` 发送观测。
- [ ] 写清主车视觉使用 `r,<reliable_seq>,<context_id>,<event>,<value>` 可靠回报 `TARGET_FOUND`。
- [ ] 写清重复 `s/r` 必须幂等处理并重新确认。
- [ ] 写清上下文不匹配的合法 `r` 包需要确认但不触发状态跳转。
- [ ] 写清 `s/a/r` 可靠包发送前后使用固定 1 ms 短延时。
- [ ] 写清 `v/o` 数据流包不做发送前后延时。
- [ ] 写清可靠包重复发送由可靠通信层低频调度, 不在高频数据流路径中累积阻塞。
- [ ] 写清状态流为 `IDLE -> SEARCH_OBJECT -> OBJECT_FOUND`。
- [ ] 写清 `SEARCH_OBJECT` 只输出车体系 `vx / vy`。
- [ ] 写清视觉事件只触发主车判断, 不直接迁移全局状态。
- [ ] 做文档规则检查。

## Task 2: 实现 Vision 端 hook 与通信协议

**目标:** 让 Vision 仓库的主车入口具备 hook 上下文、观测输出、可靠事件回报和按包类型节流的发送能力。

**文件:**

- 修改: `../SmartCar2026-Vision/master/main.py`
- 修改: `../SmartCar2026-Vision/tests/contract/`
- 修改: `../SmartCar2026-Vision/tests/unit/`
- 修改: `../SmartCar2026-Vision/README.md`

**步骤:**

- [ ] 补 Vision master 同步包解析与确认契约测试。
- [ ] 补 Vision master 重复同步包幂等确认测试。
- [ ] 补 Vision master 较早上下文同步包不覆盖当前上下文测试。
- [ ] 补 Vision master `reliable_seq` 与 `context_id` 分离测试。
- [ ] 补 Vision master 目标点误差测试。
- [ ] 补 Vision master 无目标输出零观测测试。
- [ ] 补 Vision master 目标面积上报到目标强度字段测试。
- [ ] 补 Vision master hook 条件未满足时不发 `TARGET_FOUND` 测试。
- [ ] 补 Vision master hook 条件连续满足后发送 `TARGET_FOUND` 测试。
- [ ] 补 Vision master 同一上下文只创建一次 `TARGET_FOUND` 测试。
- [ ] 补 Vision master 未收到 `TARGET_FOUND` 确认前按低频节奏重复发送同一事件测试。
- [ ] 补 Vision master 收到 `TARGET_FOUND` 确认后停止重复发送测试。
- [ ] 补 Vision master 未支持 hook 配置不触发事件测试。
- [ ] 补 Vision master 串口输入解码失败不中断主循环测试。
- [ ] 补 Vision master `o` 数据流包写出不 sleep 的测试。
- [ ] 补 Vision master `s/a/r` 可靠包写出前后固定 1 ms sleep 的测试。
- [ ] 在 `master/main.py` 接收 `s` 包并记录当前上下文。
- [ ] 在 `master/main.py` 收到有效上下文后输出 `a` 包。
- [ ] 将 `master/main.py` 输出改为 `o` 观测短包和 `r` 事件短包。
- [ ] 将 Vision master 发送函数拆为数据流发送和可靠发送, 可靠发送前后固定 sleep 1 ms。
- [ ] 检查 Vision assistant 入口只保留 `v` 数据流职责, 不接入 hook 或可靠包。
- [ ] 更新 Vision README。
- [ ] 运行 Vision 主机侧测试。

## Task 3: 实现车端主车视觉可靠通信识别与发送边界

**目标:** 让 RT1021 侧能识别 `s/a/o/r` 并按本地视觉可靠语义处理主车视觉通信。

**文件:**

- 修改: `src/protocol/packet.py`
- 修改: `src/protocol/link.py`
- 修改: `src/vision/master/forward_runtime.py`
- 修改: `src/config/params.py`
- 修改: `src/hardware/uart_bus.py`
- 修改: `tests/contract/serial_protocol/test_serial_packet_protocol_contract.py`
- 修改: `tests/unit/runtime/test_master_forward_runtime.py`

**步骤:**

- [ ] 补 `a,<reliable_seq>` 同时作为同步确认和可靠事件确认的协议契约测试。
- [ ] 补 `s/a/o/r` 解析与格式化契约测试。
- [ ] 补 `s/r` 可靠包序号与 `o/r` 业务上下文编号分离测试。
- [ ] 补同一发送方向只存在一个待确认可靠包测试。
- [ ] 补主车本地视觉可靠包发送前后固定 1 ms sleep 测试。
- [ ] 补主车本地视觉数据流包写出不 sleep 测试。
- [ ] 增加主车本地视觉可靠包固定 1 ms 发送短延时。
- [ ] 将主车本地视觉串口发送拆分为数据流发送和可靠发送, 可靠发送前后固定 sleep 1 ms。
- [ ] 保持 UART8 前馈和辅车 UART6 视觉速度融合行为不接入可靠通信。

## Task 4: 实现主车搜索状态机与主车视觉通信链路

**目标:** 主车 RT1021 能建立视觉 hook 上下文, 根据可靠事件进入已找到状态并输出零平移速度。

**文件:**

- 修改: `src/vision/master/forward_runtime.py`
- 新增或修改: `src/vision/master/` 下主车搜索纯逻辑模块
- 修改: `tests/unit/runtime/test_master_forward_runtime.py`
- 新增或修改: `tests/unit/vision/` 下主车搜索逻辑测试

**步骤:**

- [ ] 增加主车搜索 `vx` 参数。
- [ ] 增加主车搜索 `vy` 参数。
- [ ] 增加 hook 配置编号参数。
- [ ] 补进入搜索状态后创建视觉 `context_id` 测试。
- [ ] 补主车角色周期主动进入搜索状态测试。
- [ ] 补进入搜索状态后创建同步包 `reliable_seq` 测试。
- [ ] 补未收到确认时重复发送同一同步包测试。
- [ ] 补收到匹配确认后停止重复发送测试。
- [ ] 补非匹配确认不会结束当前同步测试。
- [ ] 补搜索态输出固定 `vx / vy` 和零 `omega` 测试。
- [ ] 补当前上下文 `TARGET_FOUND` 事件会被确认测试。
- [ ] 补当前上下文 `TARGET_FOUND` 事件触发已找到状态测试。
- [ ] 补非当前上下文 `TARGET_FOUND` 事件不触发状态跳转测试。
- [ ] 补重复 `TARGET_FOUND` 事件不重复迁移状态测试。
- [ ] 补已找到态输出零平移速度测试。
- [ ] 补主车视觉观测包不转发到 UART8 测试。
- [ ] 接入 UART6 本地视觉输入与输出。
- [ ] 在主车角色周期中处理视觉确认、观测和事件, 再输出当前状态速度。
- [ ] 保持 UART3 与 UART8 既有行为不变。

## Task 5: 联合验证与收口

**目标:** 确认两个仓库的搜索闭环行为一致。

**文件:**

- 验证车端仓库与 Vision 仓库。

**步骤:**

- [ ] 运行车端单元测试。
- [ ] 运行车端契约测试。
- [ ] 运行 Vision 单元测试与契约测试。
- [ ] 检查文档中没有历史性口吻。
- [ ] 检查实现没有引入反向切换目标、对齐和辅车跟进。
- [ ] 检查主车搜索状态没有显式接管角速度。
- [ ] 检查 `v/o` 数据流发送路径没有发送前后 sleep。
- [ ] 检查主车本地视觉链路和 Vision master 的 `s/a/r` 可靠发送路径都具备发送前后固定 1 ms 短延时。
- [ ] 检查 UART8 和 Vision assistant 不承载本阶段主车视觉 hook 或可靠事件。
- [ ] 检查 `reliable_seq` 与 `context_id` 不混用。
- [ ] 准备板端联调步骤。
- [ ] 完成后将 spec 和 plan 状态更新为 `Archive`。

## 验证命令

- 车端单元测试: `python3 -m pytest tests/unit -q`
- 车端契约测试: `python3 -m pytest tests/contract -q`
- 车端联合测试: `python3 -m pytest tests/unit tests/contract -q`
- Vision 测试: 在 `../SmartCar2026-Vision` 运行 `python3 -m pytest tests/unit tests/contract -q`

## 风险与约束

- 固定 `vx / vy` 斜向搜索依赖车体系方向定义, 联调时必须记录实际运动方向。
- 画面目标点和容差需要现场标定。
- 目标面积阈值受光照和距离影响。
- hook 事件必须绑定当前上下文编号, 避免非当前事件触发状态跳转。
- 可靠事件回报必须有确认和幂等处理, 避免事件丢失或重复迁移状态。
- 可靠包固定 1 ms 短延时只允许作用于 `s/a/r`, 不允许放到 `v/o` 高频数据流路径。
- 可靠重发属于低频调度, 不作为控制周期优化重点。
- 误差闭环修正不属于当前阶段边界。
- 任何显式角速度接管都属于本阶段边界之外。
