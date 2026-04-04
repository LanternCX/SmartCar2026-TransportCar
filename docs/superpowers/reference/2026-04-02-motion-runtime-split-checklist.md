# 2026-04-02 主辅 motion_runtime 拆分清单

## 说明

- 本文只记录 2026-04-02 当前仓库里实际存在的主辅 `motion_runtime.py` 内容, 作为后续拆分复核基线
- 结论只基于当前工作树与旧 `stability` 历史文件, 不猜测尚未出现的新实现
- “是否暂留 owner” 与 “暂留理由” 栏位已按本轮复核补全, 后续迁移必须逐项对照

## 当前总览结论

- 主车 `src/master/motion_runtime.py` 仍是大对象 owner, 同时承担状态持有、硬件读取、滤波、姿态估计、里程更新、轮速控制和对外主入口
- 辅车 `src/assistant/motion_runtime.py` 已经把一部分长期业务状态收口到 `AssistantState`, 但控制内部状态、滤波链和命令执行仍大量滞留在 runtime owner 中
- 主辅两侧都还没有建立面向过程式主线的公开入口, 现有主线仍依赖大对象方法
- 主辅两侧与旧 `stability` 对应的滤波、姿态、运动学、控制器能力大多还在 runtime 私有实现中, 没有回到清晰的 `ctrl/` 边界

## 主车拆分清单

| 文件 | 现有段落/对象 | 当前职责 | 目标落点 | 是否暂留 owner | 暂留理由 |
| --- | --- | --- | --- | --- | --- |
| `src/master/motion_runtime.py` | `_clamp` | 通用限幅辅助 | `src/master/ctrl/pid.py` 或控制通用辅助入口 | 否 | 属于控制计算辅助, 不应继续挂在 owner 文件顶层 |
| `src/master/motion_runtime.py` | `_load_ident_lookup` | 读取辨识结果文件 | `src/master/ctrl/ident.py` | 否 | 属于辨识数据读取边界 |
| `src/master/motion_runtime.py` | `_load_gyro_offsets` | 读取陀螺仪 offset 文件 | `src/master/ctrl/storage.py` | 否 | 属于存储读取边界 |
| `src/master/motion_runtime.py` | `_heading_chain_ready` / `_encoder_chain_ready` / `base_chain_ready` | 判断底盘基础链路是否可用 | 主车过程式主线入口附近 | 是 | 这是主线装配期的链路可用性判断, 与 owner 调度直接相关 |
| `src/master/motion_runtime.py` | `_LowPassFilter` | 角速度一阶低通 | `src/master/ctrl/filters.py` | 否 | 属于稳定链滤波能力 |
| `src/master/motion_runtime.py` | `_SpikeMedianFilter` | 轮速尖峰抑制 | `src/master/ctrl/filters.py` | 否 | 属于稳定链滤波能力 |
| `src/master/motion_runtime.py` | `_DiffLimitFilter` | 轮速限斜率 | `src/master/ctrl/filters.py` | 否 | 属于稳定链滤波能力 |
| `src/master/motion_runtime.py` | `_DualWindowRegressionFilter` | 轮速回归平滑 | `src/master/ctrl/filters.py` 或单独控制辅助文件 | 否 | 属于控制侧滤波内部实现 |
| `src/master/motion_runtime.py` | `_Quaternion` | 四元数积分与 yaw 估计 | `src/master/ctrl/attitude.py` | 否 | 属于姿态估计能力 |
| `src/master/motion_runtime.py` | `_OmniKinematics` | 三轮底盘正逆运动学与脉冲换算 | `src/master/ctrl/kinematics.py` | 否 | 属于运动学能力 |
| `src/master/motion_runtime.py` | `_Odometry` | 世界系里程累计 | `src/master/ctrl/kinematics.py` | 否 | 属于运动学能力 |
| `src/master/motion_runtime.py` | `_SpeedController` | 轮速控制器与前馈 | `src/master/ctrl/pid.py` | 否 | 属于控制器能力 |
| `src/master/motion_runtime.py` | `MotionRuntime.__init__` 中的依赖装配 | 持有硬件句柄、控制器、滤波器、快照缓存和跨周期变量 | 过程式状态装配入口 + `state/` + `ctrl/` | 部分暂留 | owner 仍需保留硬件句柄、最近快照和最少调度缓存, 其余应拆走 |
| `src/master/motion_runtime.py` | `_imu_port` / `_encoder_bundle` / `_motor_bundle` | 从 `hw_bundle` 取硬件句柄 | owner | 是 | 纯装配态访问入口, 留在 owner 最自然 |
| `src/master/motion_runtime.py` | `_capture_heading_target` / `_ensure_heading_target` | 维护 heading hold 目标 | `src/master/state/` + `src/master/ctrl/pid.py` | 否 | 属于跨周期控制内部状态 |
| `src/master/motion_runtime.py` | `_compute_heading_correction` | 根据 heading 误差算角速度修正 | `src/master/ctrl/pid.py` | 否 | 属于控制器能力 |
| `src/master/motion_runtime.py` | `_apply_motor_output` | 正逆解、轮速闭环、写电机 | 主车过程式主线入口调用 `ctrl/` 能力 | 是 | 这是 owner 驱动硬件的最后一跳, 但内部控制计算应迁出 |
| `src/master/motion_runtime.py` | `_read_imu_sample` / `_read_encoder_ticks` | 读取传感器并做最小归一化 | owner | 是 | 这是 owner 与硬件链路的直接交互, 应继续由 owner 收口 |
| `src/master/motion_runtime.py` | `refresh_base_chain` | 推进 IMU、滤波、姿态、里程并产出快照 | 主车过程式 `run_base_cycle()` | 是 | 这是主线单拍入口本体, 但内部实现应改为调用已拆出的 `ctrl/` 与 `state/` |
| `src/master/motion_runtime.py` | `apply_self_target` / `next_control_seq` / `update_heading_hold` / `execute_control_loop` | 接收目标、维护序号、执行底盘闭环 | 主车过程式主线入口 | 是 | 这些是对外主入口职责, 但不应继续依赖大对象私有堆 |

## 辅车拆分清单

| 文件 | 现有段落/对象 | 当前职责 | 目标落点 | 是否暂留 owner | 暂留理由 |
| --- | --- | --- | --- | --- | --- |
| `src/assistant/motion_runtime.py` | `_clamp` | 通用限幅辅助 | `src/assistant/ctrl/pid.py` 或控制通用辅助入口 | 否 | 属于控制计算辅助 |
| `src/assistant/motion_runtime.py` | `_load_ident_lookup` | 读取辨识结果文件 | `src/assistant/ctrl/ident.py` | 否 | 属于辨识边界 |
| `src/assistant/motion_runtime.py` | `_load_gyro_offsets` | 读取陀螺仪 offset 文件 | `src/assistant/ctrl/storage.py` | 否 | 属于存储读取边界 |
| `src/assistant/motion_runtime.py` | `_LowPassFilter` | 角速度一阶低通 | `src/assistant/ctrl/filters.py` | 否 | 属于稳定链滤波能力 |
| `src/assistant/motion_runtime.py` | `_SpikeMedianFilter` | 轮速尖峰抑制 | `src/assistant/ctrl/filters.py` | 否 | 属于稳定链滤波能力 |
| `src/assistant/motion_runtime.py` | `_DiffLimitFilter` | 轮速限斜率 | `src/assistant/ctrl/filters.py` | 否 | 属于稳定链滤波能力 |
| `src/assistant/motion_runtime.py` | `_DualWindowRegressionFilter` | 轮速回归平滑 | `src/assistant/ctrl/filters.py` 或控制辅助文件 | 否 | 属于控制侧内部实现 |
| `src/assistant/motion_runtime.py` | `_Quaternion` | 四元数积分与 yaw 估计 | `src/assistant/ctrl/attitude.py` | 否 | 属于姿态估计能力 |
| `src/assistant/motion_runtime.py` | `_OmniKinematics` | 三轮底盘正逆运动学与脉冲换算 | `src/assistant/ctrl/kinematics.py` | 否 | 属于运动学能力 |
| `src/assistant/motion_runtime.py` | `_Odometry` | 世界系里程累计 | `src/assistant/ctrl/kinematics.py` | 否 | 属于运动学能力 |
| `src/assistant/motion_runtime.py` | `_SpeedController` | 轮速控制器与前馈 | `src/assistant/ctrl/pid.py` | 否 | 属于控制器能力 |
| `src/assistant/motion_runtime.py` | `CoreRuntime` | 持有 `hw_bundle`、`AssistantState`、`SafetyGuard` | owner + `state/` | 是 | 这是辅车 owner 的最小装配容器, 目前保留合理 |
| `src/assistant/motion_runtime.py` | `MotionRuntime.__init__` 中的依赖装配 | 装配控制器、滤波器、姿态估计、缓存和跨周期变量 | 过程式状态装配入口 + `state/` + `ctrl/` | 部分暂留 | owner 只需保留硬件句柄、安全对象和最近快照, 其余应拆走 |
| `src/assistant/motion_runtime.py` | `_motor_bundle` / `_imu_bundle` / `_encoder_bundle` | 从 `hw_bundle` 取硬件句柄 | owner | 是 | 纯装配态访问入口, 应继续留在 owner |
| `src/assistant/motion_runtime.py` | `_capture_heading_target` / `_ensure_heading_target` / `_clear_follow_target` / `_capture_follow_target` | 维护跟随目标与 heading hold 目标 | `src/assistant/state/` | 否 | 都是跨周期控制内部状态 |
| `src/assistant/motion_runtime.py` | `_heading_chain_ready` / `_encoder_chain_ready` / `_update_base_ok` | 判断基础链路可用并回写状态 | 主线入口 + `state/` | 部分暂留 | 可用性判断靠近 owner, 结果字段应统一落到状态对象 |
| `src/assistant/motion_runtime.py` | `_resolve_follow_velocity` / `_compute_heading_correction` | 生成跟随速度与 heading 修正 | `src/assistant/ctrl/kinematics.py` + `src/assistant/ctrl/pid.py` | 否 | 属于控制计算 |
| `src/assistant/motion_runtime.py` | `_read_imu_sample` / `_read_encoder_ticks` | 读取传感器并做最小归一化 | owner | 是 | 这是 owner 与硬件链路的直接交互 |
| `src/assistant/motion_runtime.py` | `_refresh_base_chain` | 推进 IMU、滤波、姿态、里程并回写状态对象 | 辅车过程式 `run_base_cycle()` | 是 | 这是辅车主线单拍入口本体, 但内部计算应改为调用拆出的 `ctrl/` |
| `src/assistant/motion_runtime.py` | `_apply_motor_output` / `_reset_speed_loop` / `_stop_motors` | 轮速闭环与电机写出 | 辅车过程式主线入口 | 是 | 这是 owner 驱动硬件的最后一跳, 但控制计算应迁出 |
| `src/assistant/motion_runtime.py` | `_stop` / `_preserve_timeout_stop` / `_reject_unsupported_command` / `_apply_follow` / `_apply_velocity` / `apply_command` / `tick` / `state_line` | 安全收口、命令执行、周期推进和状态回包 | 辅车过程式主线入口 + `state/` | 是 | 对外流程入口与安全编排属于 owner, 但状态写入与控制计算应拆分 |

## 最终暂留 owner 的内容

| 侧别 | 暂留内容 | 暂留理由 |
| --- | --- | --- |
| 主车 | `hw_bundle` 与硬件访问方法 | 装配态与真实硬件访问必须由 owner 收口 |
| 主车 | 最近一次循环 token / base snapshot | 同一拍复用和对外快照缓存属于主线调度职责 |
| 主车 | 过程式单拍入口与电机写出最后一跳 | 运行时 owner 仍要负责驱动真实硬件链路 |
| 辅车 | `CoreRuntime` 中的 `hw_bundle` / `SafetyGuard` / 状态 owner 引用 | 安全门禁和装配态本来就属于 owner 核心职责 |
| 辅车 | 最近一次循环 token / base snapshot / control token | 同一拍复用、防止重复执行属于主线调度职责 |
| 辅车 | 过程式命令入口、周期推进和电机写出最后一跳 | 运行时 owner 仍需承担命令编排与真实硬件驱动 |
