# 2026-04-02 状态与控制落位对照

## 说明

- 本文按“业务状态 / 控制内部状态 / owner 装配状态”记录主辅当前真实落位
- 只记录当前已经在代码中看到的状态, 不推断未出现的新对象

## 关键结论

- `state/` 的语义边界是跨周期常驻对象, 不仅包括业务状态, 也包括控制内部常驻对象, 例如滤波器、控制器、运动学对象、查表结果、积分量与长期缓存
- 主车 `master.state` 当前承载跨周期状态对象定义, 过程式主线与控制推进仍在 `master.motion_runtime`
- 辅车 `assistant.state` 当前承载跨周期状态对象定义, 跟随流程、控制推进、命令处理与硬件读写已回到 `assistant.motion_runtime`
- 主辅两侧的状态模块都只承载跨周期字段与常驻对象, 不承载过程式主线函数, 也不承载硬件访问逻辑
- `hw_bundle` 和其中的硬件对象仍属于 owner 装配边界, 即使装配后临时挂在 `MotionRuntimeState` 实例上, 也不属于 `state/` 的语义边界

## 主车落位对照

| 变量或状态 | 当前所在处 | 分类 | 说明 |
| --- | --- | --- | --- |
| `heading_deg` | `master.state.MasterRuntimeState` | 业务状态 | 主车朝向跨周期结果 |
| `yaw_rate_deg_s` | `master.state.MasterRuntimeState` | 业务状态 | 跨周期角速度结果 |
| `odom` | `master.state.MasterRuntimeState` | 业务状态 | 跨周期里程结果 |
| `encoder_ticks` | `master.state.MasterRuntimeState` | 业务状态 | 最近一拍编码器结果 |
| `imu_raw` / `imu_calibrated` | `master.state.MasterRuntimeState` | 业务状态 | 最近一拍 IMU 结果 |
| `last_target` / `last_applied_target` | `master.state.MasterRuntimeState` | 业务状态 | 主车当前目标与最近一次执行目标 |
| `target_heading_deg` / `yaw_integral` / `heading_target_ready` | `master.state.MasterControlState` | 控制内部状态 | 由 `MotionRuntimeState.control` 唯一承载的 heading hold 跨周期状态 |
| `wheel_speeds` / `target_wheel_speeds` / `motor_duties` | `master.state.MasterControlState` | 控制内部状态 | 由 `MotionRuntimeState.control` 唯一承载的控制链中间结果和输出缓存 |
| `q_est` / `odometry` / `gyro_lpf` / `wheel_filters` / `wheel_controllers` / `last_yaw_rad` | `master.state.MasterControlState` | 控制内部状态 | 由 `MotionRuntimeState.control` 唯一承载的姿态、里程、滤波与控制器内部缓存 |
| `_control_seq` | `master.state.MotionRuntimeState` | 控制内部状态 | 主车对辅车发包序号仍挂在运行时状态对象上 |
| `hw_bundle` / `pid_map` / `ident_lookup` / `imu_offsets` | `master.state.MotionRuntimeState` 实例 | owner 装配状态 | 由 `master.motion_runtime` 在装配时写入运行时状态对象, 其中 `hw_bundle` 仍按 owner 语义理解, 不视为 `state/` 状态 |
| `_last_cycle_token` / `_last_base_snapshot` | `master.state.MotionRuntimeState` | owner 装配状态 | 单拍复用与最近快照缓存 |
| 主线推进函数 | `master.motion_runtime` | 过程式流程 | 包括 base cycle、目标应用、heading hold 更新与控制推进 |
| `_last_self_base_state` / `_last_self_target` / `_last_assistant_feedback` | `master.app.MasterApp` | 业务状态 | app 侧仍保留额外缓存 |

## 辅车落位对照

| 变量或状态 | 当前所在处 | 分类 | 说明 |
| --- | --- | --- | --- |
| `follow_active` / `state_label` / `last_seq` | `assistant.state.AssistantState` | 业务状态 | 辅车跟随最小业务状态 |
| `odom` / `heading_deg` / `target_heading_deg` / `yaw_rate_deg_s` / `base_ok` | `assistant.state.AssistantState` | 业务状态 | 对外状态回传所需的跨周期结果 |
| `velocity_command` / `timeout` / `last_error` | `assistant.state.AssistantState` | 业务状态 | 运行时当前控制结果与故障标签 |
| `yaw_integral` / `heading_target_ready` / `follow_target_world` | `assistant.state.AssistantControlState` | 控制内部状态 | 由 `MotionRuntimeState.control` 唯一承载的跟随与 heading hold 跨周期内部状态 |
| `wheel_speeds` / `target_wheel_speeds` / `motor_duties` | `assistant.state.AssistantControlState` | 控制内部状态 | 由 `MotionRuntimeState.control` 唯一承载的控制链中间结果和输出缓存 |
| `encoder_ticks` / `imu_raw` / `imu_calibrated` | `assistant.state.MotionRuntimeState` | 业务状态 | 最近一拍底座观测结果 |
| `q_est` / `odometry` / `gyro_lpf` / `wheel_filters` / `wheel_controllers` / `last_yaw_rad` | `assistant.state.AssistantControlState` | 控制内部状态 | 由 `MotionRuntimeState.control` 唯一承载的姿态、里程、滤波与控制器内部缓存 |
| `hw_bundle` / `safety` / `pid_map` / `ident_lookup` / `imu_offsets` | `assistant.state.MotionRuntimeState` 实例 | owner 装配状态 | 由 `assistant.motion_runtime.create_runtime_state` 在装配时写入, 其中 `hw_bundle` 仍按 owner 语义理解, 不视为 `state/` 状态 |
| `_last_cycle_token` / `_last_base_snapshot` / `_last_control_cycle_token` | `assistant.state.MotionRuntimeState` | owner 装配状态 | 单拍复用与重复执行保护 |
| `state_line` | `assistant.motion_runtime` 在装配时绑定到 `MotionRuntimeState` 实例 | owner 装配状态 | 由 owner 在装配阶段挂接, 状态模块本身不定义流程方法 |
| 跟随命令处理 / 周期推进 / 电机输出 / IMU 编码器读取 | `assistant.motion_runtime` | 过程式流程 | 当前已从 `assistant.state` 收回到运行时主线文件 |

## 当前边界说明

| 项目 | 当前表现 | 说明 |
| --- | --- | --- |
| app 侧还有额外缓存状态 | 主车 app 还缓存 `_last_self_base_state`、`_last_self_target`、`_last_assistant_feedback` | 状态 owner 仍未完全唯一, 这部分不在本轮任务5边界内 |
| 运行时状态对象带 owner 装配字段 | 主辅 `MotionRuntimeState` 实例上仍挂 `hw_bundle`、配置查表、安全门禁和快照缓存 | 这是当前允许的实现形态; 需要区分“实例挂接位置”和“`state/` 语义边界”, 不把硬件句柄误判为迁入 `state/` |
