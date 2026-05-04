# 状态机定义

## 1. 定位

本文件定义主车全局状态、辅车子状态、目标、事件和同步语义。

串口报文格式见 [串口通信协议](protocol.md)。协议只负责传输 `state`、`target`、`arg`、`event` 等字段, 不拥有业务状态机或业务常量。本文件负责说明这些字段在主车和辅车语境中的状态机含义。

## 2. 状态所有权

- 主车全局状态机由 `vision/master/` 维护。
- 辅车子状态机由 `vision/assistant/` 维护。
- 协议层只解析和格式化短包字段, 不维护状态机对象或业务常量。
- 主车通过本车 `UART6` 的 `s` 包同步视觉 hook 上下文。
- 主车通过 `UART8` 的 `s` 包同步辅车子状态。
- 主车视觉端接收上下文后执行本地识别任务并维护主车搜索 P 环。
- 主车视觉端通过 `v,<vx>,<vy>` 输出主车搜索速度，通过可靠 `r` 包回报事件或结果。
- `r` 包不直接改变全局状态，全局状态切换由主车状态机判断后执行。
- 视觉事件只触发主车判断，不直接迁移全局状态。
- 辅车子状态只由主车 `UART8` 同步包驱动, 不由辅车本地视觉包、速度包或底盘状态自行切换。

## 3. 主车视觉 hook 同步字段

主车视觉 hook 同步包格式：

```text
s,<reliable_seq>,<context_id>,<state>,<target>,<arg>
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `reliable_seq` | 可靠包序号，用于确认、重发和去重 |
| `context_id` | 业务上下文编号，用于 `s/o/r` 匹配 |
| `state` | 主车全局状态编号 |
| `target` | 主车状态使用的目标编号 |
| `arg` | 主车状态短参数 |

确认包 `a,<reliable_seq>` 只确认可靠包，不表达业务上下文。

## 4. 辅车子状态同步字段

辅车子状态同步包格式：

```text
s,<seq>,<state>,<target>,<arg>
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `seq` | 状态同步序号, 用于确认、重发和去重 |
| `state` | 辅车子状态编号 |
| `target` | 辅车子状态目标编号 |
| `arg` | 辅车子状态短参数 |

确认包 `a,<seq>` 只确认对应同步包已被辅车处理。该确认不携带主车视觉 `context_id`, 也不表示辅车主动回报业务状态。

## 5. 主车物体搜索状态流

主车物体搜索闭环的状态流为：

```text
IDLE -> SEARCH_OBJECT -> ORBITING -> IDLE
```

### `IDLE`

空闲安全状态，底盘输出为零。主车搜索运行入口进入角色周期后，状态机从该状态进入 `SEARCH_OBJECT`。

### `SEARCH_OBJECT`

主车主动搜索物体。

行为：

- 主车创建新的 `context_id`。
- 主车通过本车 `UART6` 向主车 OpenART 发送 `s,<reliable_seq>,<context_id>,<state>,<target>,<arg>` 建立视觉 hook 上下文。
- 主车状态机不计算视觉 P 环。
- 主车平移速度来源为 OpenART Vision master 通过本车 `UART6` 发送的 `v,<vx>,<vy>`。
- 主车状态机不显式接管 `omega`。
- 主车视觉通过可靠 `r,<reliable_seq>,<context_id>,<event>,<value>` 回报 `TARGET_FOUND`。

跳转条件：

- 主车收到匹配 `context_id` 下的 `TARGET_FOUND`。
- 主车确认该事件后, 由主车状态机判断是否发起辅车 idle 同步。
- 主车等待辅车 idle ACK 期间保持 `SEARCH_OBJECT` 正式状态, 本车停止搜索运动。
- 辅车 idle ACK 到达后, 主车进入 `ORBITING`。
- 上下文不匹配的合法 `r` 包需要确认，但不触发状态跳转。
- 重复 `r` 包幂等处理，不重复迁移状态。

### `ORBITING`

主车使用共享底盘统一绕行模式绕到上电基准航向的绝对 `+90°`。该状态不使用主车视觉搜索速度；主车只有在辅车 idle 同步被确认后进入该状态。绕行完成后回到 `IDLE`，并向辅车同步找物体子状态。

## 6. 主车全局状态编号

| `state` | 名称 | 含义 |
| --- | --- | --- |
| `0` | `IDLE` | 空闲，底盘不执行状态机任务 |
| `1` | `SEARCH_OBJECT` | 主车使用 OpenART Vision master 下发的 `v,<vx>,<vy>` 搜索物体 |
| `2` | `ORBITING` | 主车使用统一绕行模式绕到上电基准航向 `+90°` |
| `3` | `STOP` | 停止状态机任务并输出停止量 |

## 7. 主车目标编号

| `target` | 名称 | 含义 |
| --- | --- | --- |
| `0` | `NONE` | 无目标 |
| `1` | `OBJECT` | 搬运目标物体 |
| `2` | `MASTER_MARKER` | 主车侧标 |
| `3` | `EDGE_LINE` | 边线 |

具体颜色、类别或视觉识别方式由视觉端按状态解释，不写入串口协议字段名。

## 8. 主车状态参数 `arg`

`arg` 是状态相关短参数，固定为 `i16`。

| `state` | `arg` 含义 |
| --- | --- |
| `IDLE` | 固定为 `0` |
| `SEARCH_OBJECT` | hook 配置编号 |
| `ORBITING` | 固定为 `0` |
| `STOP` | 固定为 `0` |

## 9. 主车事件编号

事件回报包格式：

```text
r,<reliable_seq>,<context_id>,<event>,<value>
```

事件编号：

| `event` | 名称 | 含义 |
| --- | --- | --- |
| `0` | `NONE` | 无事件 |
| `1` | `RUNNING` | 状态执行中 |
| `2` | `DONE` | 状态条件满足 |
| `3` | `FAILED` | 状态失败 |
| `4` | `WAITING_PEER` | 本端正在等待对端 |
| `5` | `TARGET_LOST` | 目标丢失 |
| `6` | `TARGET_FOUND` | 目标发现 |
| `7` | `ALIGNED` | 角度或位置调整完成 |
| `8` | `ARRIVED` | 到位 |

`SEARCH_OBJECT` 中的 `TARGET_FOUND` 表示目标强度达到阈值且目标误差连续稳定进入画面目标窗口。`value` 表示事件附加值，含义由 `state` 和 `event` 共同决定。


## 10. 辅车子状态编号

| `state` | 名称 | 含义 |
| --- | --- | --- |
| `0` | `ASSISTANT_IDLE` | 辅车停止线速度, 忽略速度输入, 保持已有朝向控制语义 |
| `1` | `ASSISTANT_FOLLOW` | 辅车融合 `UART8` 前馈与 `UART6` 视觉修正 |
| `2` | `ASSISTANT_APPROACH_OBJECT` | 辅车使用本地视觉寻找目标物体 |

辅车子状态目标编号：

| `target` | 名称 | 含义 |
| --- | --- | --- |
| `0` | `ASSISTANT_TARGET_NONE` | 无辅车子目标 |
| `1` | `ASSISTANT_TARGET_OBJECT` | 搬运目标物体 |

`ASSISTANT_IDLE` 使用 `ASSISTANT_TARGET_NONE` 和参数 `0`。辅车进入 idle 后清空 `UART8` 前馈速度缓存和 `UART6` 视觉速度缓存, 写入零速度目标, 不写入角度目标。

`ASSISTANT_APPROACH_OBJECT` 使用 `ASSISTANT_TARGET_OBJECT` 和找物体配置编号。辅车进入该状态后清空两路运动输入，向辅车 OpenART 同步找物体任务；本地视觉确认同步后，辅车只使用本地 `UART6` 视觉速度向目标物体靠近，不叠加 `UART8` 速度前馈。辅车本地视觉回报 `TARGET_FOUND` 后，辅车写入零速度并通过 `UART8` 向主车可靠回报结果。

## 11. 状态跳转原则

- 主车接收事件后判断是否切换全局状态。
- 视觉端只提供速度控制量和事件，不维护全局状态。
- 主车等待辅车 idle ACK 是 `SEARCH_OBJECT -> ORBITING` 跳转的内部过程, 不是新的主车全局状态编号。
- 辅车在 `ASSISTANT_FOLLOW` 中接收 `UART8` 速度前馈和本车视觉速度修正。
- 辅车在 `ASSISTANT_IDLE` 中忽略后续速度短包对角色层速度缓存和底盘速度输出的影响。
- 辅车在 `ASSISTANT_APPROACH_OBJECT` 中只使用本地视觉速度寻找目标物体，目标物体找到后停止并回报主车。
- 状态切换不能通过 `v`、`o` 或 `r` 包隐式完成。
- 可靠包确认只表示对端已处理该包，不表示状态已切换。
