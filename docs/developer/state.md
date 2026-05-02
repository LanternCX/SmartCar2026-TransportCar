# 状态机定义

## 1. 定位

本文件定义全局状态机在串口协议中的编号、事件和同步语义。

串口报文格式见 [串口通信协议](protocol.md)。协议只负责传输 `state`、`target`、`arg`、`event` 等字段，本文件负责说明这些字段的状态机含义。

## 2. 状态所有权

- 全局状态机由主车维护。
- 主车通过串口协议中的 `s` 包同步视觉 hook 上下文。
- 主车视觉端接收上下文后执行本地识别任务并维护主车搜索 P 环。
- 主车视觉端通过 `v,<vx>,<vy>` 输出主车搜索速度，通过可靠 `r` 包回报事件或结果。
- `r` 包不直接改变全局状态，全局状态切换由主车状态机判断后执行。
- 视觉事件只触发主车判断，不直接迁移全局状态。

## 3. 状态同步字段

状态同步包格式：

```text
s,<reliable_seq>,<context_id>,<state>,<target>,<arg>
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `reliable_seq` | 可靠包序号，用于确认、重发和去重 |
| `context_id` | 业务上下文编号，用于 `s/o/r` 匹配 |
| `state` | 全局状态编号 |
| `target` | 状态使用的目标编号 |
| `arg` | 状态短参数 |

确认包 `a,<reliable_seq>` 只确认可靠包，不表达业务上下文。

## 4. 主车物体搜索状态流

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
- 主车确认该事件后，由主车状态机判断并进入 `ORBITING`。
- 上下文不匹配的合法 `r` 包需要确认，但不触发状态跳转。
- 重复 `r` 包幂等处理，不重复迁移状态。

### `ORBITING`

主车使用共享底盘 rear only 模式绕到上电基准航向的绝对 `+90°`。该状态不使用主车视觉搜索速度；绕行完成后回到 `IDLE`。

## 5. 全局状态编号

| `state` | 名称 | 含义 |
| --- | --- | --- |
| `0` | `IDLE` | 空闲，底盘不执行状态机任务 |
| `1` | `SEARCH_OBJECT` | 主车使用 OpenART Vision master 下发的 `v,<vx>,<vy>` 搜索物体 |
| `2` | `ORBITING` | 主车使用 rear only 模式绕到上电基准航向 `+90°` |
| `3` | `STOP` | 停止状态机任务并输出停止量 |

## 6. 目标编号

| `target` | 名称 | 含义 |
| --- | --- | --- |
| `0` | `NONE` | 无目标 |
| `1` | `OBJECT` | 搬运目标物体 |
| `2` | `MASTER_MARKER` | 主车侧标 |
| `3` | `EDGE_LINE` | 边线 |

具体颜色、类别或视觉识别方式由视觉端按状态解释，不写入串口协议字段名。

## 7. 状态参数 `arg`

`arg` 是状态相关短参数，固定为 `i16`。

| `state` | `arg` 含义 |
| --- | --- |
| `IDLE` | 固定为 `0` |
| `SEARCH_OBJECT` | hook 配置编号 |
| `ORBITING` | 固定为 `0` |
| `STOP` | 固定为 `0` |

## 8. 事件编号

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

## 9. 状态跳转原则

- 主车接收事件后判断是否切换全局状态。
- 视觉端只提供速度控制量和事件，不维护全局状态。
- 辅车在本阶段接收 `UART8` 速度前馈和状态上下文同步，并融合本车视觉速度修正。
- 状态切换不能通过 `v`、`o` 或 `r` 包隐式完成。
- 可靠包确认只表示对端已处理该包，不表示状态已切换。
