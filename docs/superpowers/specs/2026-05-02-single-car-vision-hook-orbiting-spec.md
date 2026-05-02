# 单车视觉 Hook 与绕行状态机 Spec

> 执行状态: Active  
> 创建日期: 2026-05-02  
> 范围: 主车单车调试链路, 不控制辅车状态

## 目标

主车进入寻找态后向本车 OpenART Vision master 发送视觉 hook。视觉判断目标达到条件后，通过可靠事件回报 hook 命中。主车确认该事件属于当前上下文后，进入 `ORBITING`，使用 rear only 模式绕到上电基准航向的绝对 `+90°`。绕行完成后主车回到 `IDLE`。

## 范围

### 包含

- 主车单车状态链路：`IDLE -> SEARCH_OBJECT -> ORBITING -> IDLE`。
- 主车通过本车 `UART6` 发送视觉 hook 同步包。
- 主车通过本车 `UART6` 接收并确认视觉事件回报包。
- 主车只在当前上下文匹配且事件为 `TARGET_FOUND` 时进入 `ORBITING`。
- 主车 `ORBITING` 复用共享底盘现有 rear only 模式。
- 主车 `ORBITING` 的目标角度为上电基准航向的绝对 `+90°`。
- 主车绕行完成后进入 `IDLE` 并输出零量。
- 主机侧测试覆盖状态跳转、可靠确认和绕行命令。

### 不包含

- 辅车 idle 控制。
- 辅车子状态机。
- 主车通过 `UART8` 同步辅车状态。
- 搬运态完整流程。
- OpenART 视觉识别算法实现。
- 复杂路径规划、位置闭环或视觉绕行闭环。
- 开发文档同步。
- git commit、分支或 worktree 操作。

## 状态定义

| 编号 | 名称 | 职责 |
| --- | --- | --- |
| `0` | `IDLE` | 主车空闲安全状态, 底盘输出零 |
| `1` | `SEARCH_OBJECT` | 主车建立视觉 hook, 并使用主车视觉速度搜索物体 |
| `2` | `ORBITING` | 主车使用 rear only 模式绕到上电基准航向 `+90°` |
| `3` | `STOP` | 停止状态机任务并输出停止量 |

目标编号保留 `NONE = 0`、`OBJECT = 1`。事件编号使用现有 `TARGET_FOUND = 6` 表示视觉 hook 命中。

## 状态流

```text
IDLE -> SEARCH_OBJECT -> ORBITING -> IDLE
```

- 主车运行入口进入角色周期后，从 `IDLE` 进入 `SEARCH_OBJECT`。
- `SEARCH_OBJECT` 创建新的 `context_id`，并通过主车本车 `UART6` 发送 `s,<reliable_seq>,<context_id>,<state>,<target>,<arg>`。
- OpenART Vision master 接收 hook 后回 `a,<reliable_seq>`。
- OpenART Vision master 在 hook 命中时发送 `r,<reliable_seq>,<context_id>,TARGET_FOUND,<value>`。
- 主车收到合法 `r` 包后返回 `a,<reliable_seq>`。
- 上下文匹配且事件为 `TARGET_FOUND` 时，主车进入 `ORBITING`。
- 上下文不匹配的合法 `r` 包只确认，不触发状态变化。
- 重复 `r` 包幂等处理，不重复触发绕行进入动作。
- `ORBITING` 完成后主车进入 `IDLE`。

## 角度与运动语义

- 上电基准航向由主车运行时创建时记录。
- `ORBITING` 的目标角度为上电基准航向 `+90°`。
- 该角度是绝对角度，不使用进入绕行态瞬间的航向作为基准。
- 绕行不使用视觉闭环，也不使用位置闭环。
- 绕行依赖共享底盘现有陀螺仪航向估计与角度锁定机制判断完成。
- 绕行执行时启用共享底盘现有 rear only 模式，不重新实现轮速分配逻辑。
- 绕行完成后关闭 rear only 模式，底盘输出零。

## 主车职责

- 作为本任务状态机唯一拥有者。
- 维护搜索上下文编号和可靠包序号。
- 在 `SEARCH_OBJECT` 中向视觉发送 hook。
- 在 `SEARCH_OBJECT` 中消费主车视觉 `v,<vx>,<vy>` 搜索速度。
- 对视觉 `r` 包执行可靠确认。
- 根据当前上下文和事件类型决定是否进入 `ORBITING`。
- 进入 `ORBITING` 后不再使用主车视觉搜索速度控制底盘。
- 进入 `IDLE` 后保持底盘零输出。

## 协议语义

主车本地视觉链路使用本车 `UART6`：

- hook 同步包：`s,<reliable_seq>,<context_id>,<state>,<target>,<arg>`。
- 确认包：`a,<reliable_seq>`。
- 事件回报包：`r,<reliable_seq>,<context_id>,<event>,<value>`。
- 搜索速度包：`v,<vx>,<vy>`。
- `s/a/r` 走可靠处理，`v` 走数据流处理。
- `TARGET_FOUND` 只作为事件输入，由主车状态机判断状态迁移。

## 参数

| 参数 | 含义 |
| --- | --- |
| `MASTER_SEARCH_HOOK_CONFIG_ID` | 主车搜索 hook 配置编号 |
| `MASTER_ORBIT_TARGET_DEG` | 主车绕行绝对目标角度增量, 固定为 `90` |

## 验收标准

- 主车启动角色周期后进入 `SEARCH_OBJECT`，并向主车本车 `UART6` 写出视觉 hook 同步包。
- 主车收到 hook 确认后停止重复发送对应 hook 同步包。
- 主车收到上下文匹配的 `TARGET_FOUND` 后进入 `ORBITING`。
- 主车收到上下文不匹配的合法事件时发送确认，但状态不变。
- 主车收到重复 `TARGET_FOUND` 时发送确认，但不会重复触发绕行进入动作。
- 主车进入 `ORBITING` 时通过状态机调用边界启用现有 rear only 模式和绝对角度目标。
- 主车 `ORBITING` 的目标角度为上电基准航向 `+90°`。
- 主车进入 `ORBITING` 后不再使用主车视觉搜索速度。
- 主车绕行完成后进入 `IDLE`，底盘输出零。
- 主机侧相关测试通过。

## 风险与约束

- 本任务不触碰辅车状态控制，避免扩大当前单车调试改动面。
- 主车状态机不得阻塞等待视觉确认。
- 可靠包重发按低频节奏执行，不放大高频速度路径开销。
- 新增常驻对象只放在主车角色运行时中，避免模块级可变运行时全局状态。
- 文档和注释只描述当前事实，不写迁移说明。
