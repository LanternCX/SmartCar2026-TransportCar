# 绕行前辅车 Idle 同步 Spec

> 执行状态: Archive
> 创建日期: 2026-05-03  
> 范围: 主车从寻找物体进入绕行前的主辅状态同步

## 目标

主车在 `SEARCH_OBJECT` 中确认目标命中后, 先让辅车进入 `ASSISTANT_IDLE`, 并等待辅车确认处理该同步包。确认到达前主车停止搜索运动, 不开始绕行；确认到达后主车进入 `ORBITING` 并执行绕行动作。辅车进入 idle 后停止线速度, 不新增角度保持接口, 继续依赖共享底盘已有朝向保持机制。

## 范围

### 包含

- 主车与辅车分别在 `vision/` 层维护自己的状态机。
- 主车全局状态机保持 `IDLE -> SEARCH_OBJECT -> ORBITING -> IDLE` 主线, 不新增正式等待状态。
- `SEARCH_OBJECT -> ORBITING` 跳转内部增加辅车 idle 同步确认步骤。
- 辅车新增最小子状态: `ASSISTANT_IDLE` 与 `ASSISTANT_FOLLOW`。
- 辅车状态跳转只由主车 `UART8` 状态同步包驱动。
- 主车通过 `UART8` 发送辅车 idle 同步包并等待 ACK。
- 辅车收到 idle 同步后清空 `UART8` 前馈速度与 `UART6` 视觉速度, 并写入零速度目标。
- 删除 `MASTER_DISABLE_UART8_OUTPUT` 参数, 主辅 `UART8` 链路作为正式协同链路启用。
- 同步更新协议、状态机、控制和视觉开发文档。
- 删除 `src/protocol/state.py`, 业务状态、目标和事件常量只由 `vision/` 层维护。
- 使用主机侧单元测试与契约测试固定行为。

### 不包含

- 不实现辅车从 idle 恢复 follow。
- 不实现搬运态、推车阶段或避障状态。
- 不新增主车正式 `WAIT_ASSISTANT_IDLE` 状态编号。
- 不新增底盘保持角度接口。
- 不修改硬件串口号、引脚、电平或接线事实。
- 不修改 OpenART 视觉识别算法。
- 不执行 git commit、分支或 worktree 操作。

## 模块边界

- `src/protocol/state.py` 删除。
- `src/protocol/` 不暴露 `STATE_*`、`TARGET_*`、`EVENT_*` 业务常量。
- 主车全局状态、目标和视觉事件常量放在 `src/vision/master/state_machine.py`。
- 辅车子状态和辅车目标常量放在 `src/vision/assistant/state_machine.py`。
- 运行时代码和测试不得从 `protocol.state` 导入业务常量。

## 状态所有权

协议层只负责短包字段解析和格式化, 不维护业务状态、目标或事件常量。主车状态、辅车子状态、目标和事件语义由 `vision/` 层维护。

### 主车全局状态

主车在 `vision/master/` 维护全局任务状态。正式全局状态编号保持当前定义:

| 编号 | 名称 | 职责 |
| --- | --- | --- |
| `0` | `IDLE` | 主车空闲安全状态 |
| `1` | `SEARCH_OBJECT` | 主车建立视觉 hook 并使用主车视觉速度搜索物体 |
| `2` | `ORBITING` | 主车使用 rear only 模式绕到上电基准航向 `+90°` |
| `3` | `STOP` | 停止状态机任务并输出停止量 |

主车收到匹配当前 `context_id` 的 `TARGET_FOUND` 后, 不直接进入 `ORBITING`。主车先进入内部等待过程: 本车停止搜索运动, 发出辅车 idle 同步请求, 等待对应 ACK。该过程不占用正式全局状态编号。

### 辅车子状态

辅车在 `vision/assistant/` 维护独立子状态机。子状态编号只用于 `UART8` 主辅状态同步, 不等同于主车全局状态。

| 编号 | 名称 | 职责 |
| --- | --- | --- |
| `0` | `ASSISTANT_IDLE` | 辅车停止线速度, 忽略速度输入, 保持已有朝向控制语义 |
| `1` | `ASSISTANT_FOLLOW` | 辅车按现有规则融合 `UART8` 前馈与 `UART6` 视觉修正 |

辅车子状态只能被主车同步包改变。辅车不会根据本地视觉包、速度包或底盘状态自行跳转。

## 协议语义

`UART8` 状态同步继续使用当前短包形态: `s,<seq>,<state>,<target>,<arg>`。

在 `UART8` 辅车同步语境中:

- `seq` 是状态同步序号。
- `state` 表示辅车子状态编号。
- `target` 表示辅车子状态使用的目标编号；idle 使用辅车侧 `ASSISTANT_TARGET_NONE`。
- `arg` 表示辅车子状态短参数；idle 固定为 `0`。
- 辅车收到合法同步包后回复 `a,<seq>`。
- 重复同步包必须重复 ACK, 但不重复应用状态副作用。
- 较早同步包必须 ACK, 但不能回退辅车子状态。

协议层只负责解析字段, 不提供业务状态、目标或事件常量, 不维护主车或辅车业务状态机。

## 主车行为

1. 主车进入 `SEARCH_OBJECT` 后维持现有视觉 hook 与搜索速度链路。
2. 主车收到匹配当前 `context_id` 的 `TARGET_FOUND` 后, 清除主车搜索速度并写入零速度目标。
3. 主车生成辅车 idle 同步请求, 通过 `UART8` 可靠发送。
4. 在 idle ACK 到达前:
   - 主车不进入 `ORBITING`。
   - 主车不应用新的 `UART6` 搜索速度。
   - 主车保持本车零速度目标。
   - 主车按可靠重发间隔继续发送同一个 idle 同步包。
5. 收到匹配 idle 同步序号的 ACK 后, 主车进入 `ORBITING` 并只触发一次绕行动作。
6. `ORBITING` 期间继续保持现有行为: 不使用主车视觉搜索速度, 不允许 `UART3` 上游速度覆盖绕行控制。

## 辅车行为

1. 辅车启动后默认处于 `ASSISTANT_FOLLOW`, 保持现有跟随融合行为。
2. 辅车收到 `ASSISTANT_IDLE` 同步包后:
   - 记录当前子状态为 idle。
   - 清空 `UART8` 前馈速度缓存。
   - 清空 `UART6` 视觉速度缓存。
   - 写入零速度目标, 使 `vx=0`、`vy=0`、`omega=0`。
   - 不写入 `angle` 目标, 不新增角度保持接口。
   - 回复对应 ACK。
3. 辅车处于 idle 后继续读取串口, 但速度短包不再更新角色层速度缓存, 也不再写入底盘速度。
4. 后续恢复 follow 不属于本轮任务。

## 诊断与文档口径

- 主车调试输出应能区分当前全局状态、是否等待辅车 idle ACK、是否存在待同步包。
- 辅车诊断快照应能暴露当前子状态和两路速度缓存清空后的结果。
- `docs/developer/protocol.md` 明确 `UART8` 同步包中的 `state` 是辅车子状态, 协议层不拥有状态机。
- `docs/developer/state.md` 明确主车全局状态与辅车子状态由 `vision/` 层维护。
- `docs/developer/control.md` 与 `docs/developer/vision.md` 明确绕行前辅车 idle 同步和 idle 时速度处理。

## 验收标准

- 主车发现目标后, ACK 到达前不会开始绕行。
- 主车等待 ACK 时本车停止搜索运动。
- ACK 到达后主车只进入一次 `ORBITING`。
- 辅车收到 idle 后线速度停止, 两路速度缓存清空。
- 辅车 idle 后不因后续速度包重新移动。
- `src/protocol/state.py` 不存在, 且没有代码从 `protocol.state` 导入业务常量。
- 主机侧 `tests/unit` 与 `tests/contract` 全部通过。
