# 主车寻找与绕行状态机 Spec

> 执行状态: Archive  
> 创建日期: 2026-05-02  
> 范围: 主车寻找态 hook、命中后绕行、辅车 idle 子状态
> 归档原因: 当前阶段按单车调试收窄范围

## 目标

主车维护寻找到绕行的全局状态链路。主车进入寻找态时建立视觉 hook；视觉 hook 命中后回报事件；主车确认事件属于当前上下文后进入 `ORBITING`；主车使用 rear only 模式绕行到上电基准航向的 `+90°` 绝对角度；主车进入绕行时让辅车进入 `IDLE` 并停止跟随；主车绕行完成后回到 `IDLE`。

## 范围

### 包含

- 主车全局状态集合收口为本任务需要的最小链路。
- 主车通过本车 `UART6` 向 OpenART Vision master 发送视觉 hook 同步包。
- 主车通过本车 `UART6` 接收并确认视觉事件回报包。
- 主车收到匹配当前上下文的 `TARGET_FOUND` 后进入 `ORBITING`。
- 主车进入 `ORBITING` 时清空视觉搜索速度影响，并停止向辅车提供跟随前馈。
- 主车进入 `ORBITING` 时通过 `UART8` 同步辅车进入 `IDLE`。
- 辅车维护由主车状态同步驱动的子状态；`IDLE` 中底盘输出零。
- 主车 `ORBITING` 使用 rear only 模式和陀螺仪航向目标完成动作。
- 主机侧行为测试和协议契约测试覆盖状态跳转、可靠确认和辅车 idle 行为。
- 开发文档同步状态编号、协议语义、控制职责和视觉职责。

### 不包含

- OpenART 视觉仓库中的识别算法实现。
- 搬运态完整状态机。
- 复杂路径规划或绕行轨迹闭环。
- 场地坐标定位闭环。
- Web 可视化方案。
- git commit、分支或 worktree 操作。

## 状态定义

| 编号 | 名称 | 职责 |
| --- | --- | --- |
| `0` | `IDLE` | 主车或辅车空闲安全状态，底盘输出零 |
| `1` | `SEARCH_OBJECT` | 主车建立视觉 hook，并使用主车视觉速度搜索物体；辅车在该状态下跟随主车 |
| `2` | `ORBITING` | 主车使用 rear only 模式绕行到上电基准航向 `+90°`；辅车保持 `IDLE` |
| `3` | `STOP` | 停止状态机任务并输出停止量 |

目标编号保留最小集合：`NONE = 0`、`OBJECT = 1`。事件编号保留 `TARGET_FOUND = 6`，并保留通用运行、完成和失败事件用于可靠回报边界。

## 状态流

```text
IDLE -> SEARCH_OBJECT -> ORBITING -> IDLE
```

- 主车运行入口进入角色周期后，从 `IDLE` 进入 `SEARCH_OBJECT`。
- `SEARCH_OBJECT` 创建新的 `context_id`，并通过主车本车 `UART6` 发送 `s,<reliable_seq>,<context_id>,<state>,<target>,<arg>`。
- OpenART Vision master 接收 hook 后回 `a,<reliable_seq>`，并在 hook 命中时发送 `r,<reliable_seq>,<context_id>,TARGET_FOUND,<value>`。
- 主车收到合法 `r` 包后返回 `a,<reliable_seq>`。
- 只有 `context_id` 匹配当前搜索上下文且事件为 `TARGET_FOUND` 时，主车进入 `ORBITING`。
- `ORBITING` 进入动作只执行一次；目标角度为上电基准航向 `+90°`。
- `ORBITING` 完成后主车进入 `IDLE`。

## 角度与运动语义

- 上电基准航向由主车运行时创建时记录。
- `ORBITING` 的目标角度是上电基准航向加 `90°`。
- 该角度是绝对角度，不使用进入 `ORBITING` 瞬间的航向作为基准。
- 绕行不设计视觉闭环，也不设计位置闭环。
- 绕行依赖共享底盘现有陀螺仪航向估计和角度锁定机制判断完成。
- 绕行执行时启用 rear only 模式。
- 绕行完成后关闭 rear only 模式，底盘输出零。

## 主车职责

- 作为全局状态机唯一拥有者。
- 维护搜索上下文编号和可靠包序号。
- 在 `SEARCH_OBJECT` 中向视觉发送 hook，并消费视觉搜索速度。
- 对视觉 `r` 包执行可靠确认。
- 对重复 `r` 包幂等处理，不重复进入 `ORBITING`。
- 对上下文不匹配的合法 `r` 包只确认，不触发状态变化。
- 进入 `ORBITING` 时让辅车进入 `IDLE`。
- 进入 `ORBITING` 后不使用主车视觉 `v` 搜索速度控制底盘。
- 进入 `IDLE` 时保持底盘零输出。

## 辅车职责

- 维护受主车同步控制的子状态。
- `IDLE` 中继续读取串口并确认状态同步包，避免输入堆积。
- `IDLE` 中不融合 `UART8` 前馈和 `UART6` 视觉修正，底盘输出零。
- `SEARCH_OBJECT` 中按既定规则融合 `UART8` 前馈和 `UART6` 视觉修正。
- 不根据本车视觉结果自行切换全局状态。

## 协议语义

### 主车本地视觉链路 `UART6`

- hook 同步包：`s,<reliable_seq>,<context_id>,<state>,<target>,<arg>`。
- 确认包：`a,<reliable_seq>`。
- 事件回报包：`r,<reliable_seq>,<context_id>,<event>,<value>`。
- 搜索速度包：`v,<vx>,<vy>`。
- `s/a/r` 可靠处理，`v` 数据流处理。
- `TARGET_FOUND` 只作为事件输入，由主车状态机判断状态迁移。

### 主辅链路 `UART8`

- 速度前馈包：`v,<vx>,<vy>[,<omega>]`。
- 辅车状态同步包：`s,<seq>,<state>,<target>,<arg>`。
- 确认包：`a,<seq>`。
- 主车进入 `SEARCH_OBJECT` 时同步辅车进入跟随语义。
- 主车进入 `ORBITING` 时同步辅车进入 `IDLE`。
- 主车处于 `ORBITING` 和 `IDLE` 时向辅车输出零前馈。

## 参数

| 参数 | 建议名称 | 含义 |
| --- | --- | --- |
| `MASTER_SEARCH_HOOK_CONFIG_ID` | 已存在 | 主车搜索 hook 配置编号 |
| `MASTER_ORBIT_TARGET_DEG` | 新参数 | 主车绕行绝对目标角度增量，固定为 `90` |

## 验收标准

- 主车启动角色周期后进入 `SEARCH_OBJECT`，并向主车本车 `UART6` 写出视觉 hook 同步包。
- 主车收到 hook 确认后停止重复发送该 hook 同步包。
- 主车收到上下文匹配的 `TARGET_FOUND` 后进入 `ORBITING`。
- 主车收到上下文不匹配的合法事件时发送确认，但状态不变。
- 主车收到重复 `TARGET_FOUND` 时发送确认，但不会重复触发绕行进入动作。
- 主车进入 `ORBITING` 时同步辅车 `IDLE`。
- 辅车进入 `IDLE` 后底盘输出零，不融合前馈和视觉修正。
- 主车 `ORBITING` 的角度目标为上电基准航向 `+90°`。
- 主车绕行完成后进入 `IDLE`，底盘输出零。
- 主机侧单元测试和协议契约测试通过。

## 风险与约束

- 本任务触及主车角色运行入口、辅车角色运行入口和共享底盘控制入口，需要保持 5ms 控制周期边界。
- 新增常驻对象只允许放在主车角色运行时或辅车角色运行时中，避免模块级可变运行时状态。
- 主车状态机不得阻塞等待视觉确认或辅车确认。
- 可靠包重发按低频节奏执行，不放大高频速度路径开销。
- 文档和注释只描述当前事实，不写迁移说明。
