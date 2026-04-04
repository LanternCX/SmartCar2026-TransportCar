# 2026-04-02 stability 迁移对表

## 说明

- 本表以删除前提交 `a20c15f228dcde02393bf8eb65c5942faa55abc6^` 中的 `src/master/stability/*.py` 与 `src/assistant/stability/*.py` 为旧基线。
- “现状标签” 统一使用 `已迁入 ctrl`、`当前仍在 runtime 私有实现`、`当前在主线运行`、`已退役` 四类口径；如同时满足“主线运行”和“已迁入 ctrl”，优先记为 `已迁入 ctrl（主线运行）`。
- 本次只补完真实落点、去留结论、依据与验证方式，不扩到任务 9 的大回归或重构。

## 关键结论

- 旧 `stability` 里真正还对当前底座稳定链必要的能力，已经不再主要躲在 runtime 私有实现里；主辅两侧的滤波链、姿态积分、航向保持都已经落到 `ctrl/` 公开入口，并被 runtime 直接导入使用。
- 旧 `build_gyro_filter()` 与 `HeadingController` 这类“旧包装入口”已经退役，但其能力没有丢：前者改为直接使用 `ctrl.filters.LowPassFilter`，后者改为 `ctrl.attitude.compute_heading_correction()`。
- 欧拉角 / 四元数互转辅助函数与 `body_axis_semantics()` 这类说明性接口已退役；当前主线只保留真正被运行链消费的姿态积分、yaw 提取和车体系坐标换算，不再保留单独的旧包装函数。
- 主车侧旧 `rotate_body_delta_to_world()` 已退役，因为当前主车业务链只保留速度目标与底座基线，不再消费 `MOVE` 车体系增量；辅车侧该能力仍在主线运行，并已迁入 `assistant.ctrl.kinematics`。

## 主车对表

| 原文件 | 原能力 | 现状标签 | 当前真实落点 | 去留结论 | 依据 | 验证方式 |
| --- | --- | --- | --- | --- | --- | --- |
| `src/master/stability/filtering.py` | `SpikeMedianFilter` | `已迁入 ctrl（主线运行）` | `master.ctrl.filters.SpikeMedianFilter` | 保留 | runtime 通过 `master.ctrl.filters.build_wheel_filter_bank()` 装配轮速链, 不再使用私有副本 | `tests/unit/master/test_stability_baseline.py` 里的滤波链基线测试 |
| `src/master/stability/filtering.py` | `DiffLimitFilter` | `已迁入 ctrl（主线运行）` | `master.ctrl.filters.DiffLimitFilter` | 保留 | 与尖峰抑制一起由 `SpeedFilterChain` 公开组合, runtime 直接导入 `ctrl.filters` | `tests/unit/master/test_stability_baseline.py` 里的滤波链基线测试 |
| `src/master/stability/filtering.py` | `LowPassFilter` | `已迁入 ctrl（主线运行）` | `master.ctrl.filters.LowPassFilter` | 保留 | `master.motion_runtime.create_runtime_state()` 直接实例化 `LowPassFilter` 作为 `gyro_lpf` | `tests/unit/master/test_stability_baseline.py` 里的低通落点测试 |
| `src/master/stability/filtering.py` | `SpeedFilterChain` | `已迁入 ctrl（主线运行）` | `master.ctrl.filters.SpeedFilterChain` | 保留 | 轮速稳定链已公开承接, 只是当前实现比旧版多了一段回归平滑 | `tests/unit/master/test_stability_baseline.py` 里的滤波链基线测试 |
| `src/master/stability/filtering.py` | `build_speed_filter_chain` | `已迁入 ctrl（主线运行）` | `master.ctrl.filters.build_speed_filter_chain()` | 保留 | 公开构造入口已存在, 不再缺口 | `tests/unit/master/test_stability_baseline.py` 里的滤波链基线测试 |
| `src/master/stability/filtering.py` | `build_gyro_filter` | `已退役` | `master.ctrl.filters.LowPassFilter` 与 `master.motion_runtime.create_runtime_state()` | 退役旧 builder, 保留低通能力 | 当前代码没有任何 `build_gyro_filter` 调用点, runtime 已直接用公开 `LowPassFilter` 构造 `gyro_lpf` | `tests/unit/master/test_stability_baseline.py` 里的低通落点测试 |
| `src/master/stability/attitude.py` | `euler_to_quaternion` | `已退役` | 无单独公开入口; 能力收敛到 `master.ctrl.attitude.HeadingEstimator` 内部四元数积分 | 退役 | 当前主线没有欧拉角转四元数调用点, 运行链只消费航向积分结果 | `tests/unit/master/test_stability_baseline.py` 里的航向估计测试, 外加代码检索无调用点 |
| `src/master/stability/attitude.py` | `quaternion_to_euler` | `已退役` | 无单独公开入口; yaw 提取由 `master.ctrl.attitude.HeadingEstimator.yaw_rad()` 承接 | 退役 | 当前主线没有四元数转欧拉角调用点, 只保留 yaw 提取 | `tests/unit/master/test_stability_baseline.py` 里的航向估计测试, 外加代码检索无调用点 |
| `src/master/stability/attitude.py` | yaw 语义换算 | `已迁入 ctrl（主线运行）` | `master.ctrl.attitude.HeadingEstimator.yaw_rad()` 与 `master.ctrl.attitude.update_heading_from_gyro()` | 保留 | 主线每拍都通过 `ctrl.attitude` 推进四元数并刷新 `heading_deg` | `tests/unit/master/test_stability_baseline.py` 里的航向估计与航向修正测试 |
| `src/master/stability/kinematics.py` | `body_axis_semantics` | `已退役` | 语义分散落在 `master.ctrl.kinematics` 的前逆运动学公式与 `docs/developer/legacy-stability-baseline.md` | 退役说明性函数, 保留语义 | 当前没有代码消费“方向字典”本身, 只消费按 `x 右 y 前` 写死的公式与协议约定 | `tests/unit/master/test_stability_baseline.py` 里的运动学基线测试 |
| `src/master/stability/kinematics.py` | `rotate_body_delta_to_world` | `已退役` | 无主线落点 | 退役 | 当前主车业务决策只输出 `vel/hold`, `master.motion_runtime.apply_motion_target()` 也只接受 `vel/hold`; 旧 `MOVE` 体增量换算未进入主线 | `tests/unit/master/test_stability_baseline.py` 里的 runtime 基线测试, 外加代码检索主车无调用点 |
| `src/master/stability/control.py` | `HeadingController` | `已迁入 ctrl（主线运行）` | `master.ctrl.attitude.compute_heading_correction()` | 保留控制语义, 退役旧类名 | 当前航向保持已升级为带积分与限幅的公开函数, runtime 直接导入该入口, 不在 `pid.py` | `tests/unit/master/test_stability_baseline.py` 里的航向修正测试 |

## 辅车对表

| 原文件 | 原能力 | 现状标签 | 当前真实落点 | 去留结论 | 依据 | 验证方式 |
| --- | --- | --- | --- | --- | --- | --- |
| `src/assistant/stability/filtering.py` | `SpikeMedianFilter` | `已迁入 ctrl（主线运行）` | `assistant.ctrl.filters.SpikeMedianFilter` | 保留 | runtime 通过 `assistant.ctrl.filters.build_wheel_filter_bank()` 装配轮速链, 不再使用私有副本 | `tests/unit/assistant/test_stability_baseline.py` 里的滤波链基线测试 |
| `src/assistant/stability/filtering.py` | `DiffLimitFilter` | `已迁入 ctrl（主线运行）` | `assistant.ctrl.filters.DiffLimitFilter` | 保留 | 与尖峰抑制一起由 `SpeedFilterChain` 公开组合, runtime 直接导入 `ctrl.filters` | `tests/unit/assistant/test_stability_baseline.py` 里的滤波链基线测试 |
| `src/assistant/stability/filtering.py` | `LowPassFilter` | `已迁入 ctrl（主线运行）` | `assistant.ctrl.filters.LowPassFilter` | 保留 | `assistant.motion_runtime.create_runtime_state()` 直接实例化 `LowPassFilter` 作为 `gyro_lpf` | `tests/unit/assistant/test_stability_baseline.py` 里的低通落点测试 |
| `src/assistant/stability/filtering.py` | `SpeedFilterChain` | `已迁入 ctrl（主线运行）` | `assistant.ctrl.filters.SpeedFilterChain` | 保留 | 轮速稳定链已公开承接, 当前同样追加了回归平滑段 | `tests/unit/assistant/test_stability_baseline.py` 里的滤波链基线测试 |
| `src/assistant/stability/filtering.py` | `build_speed_filter_chain` | `已迁入 ctrl（主线运行）` | `assistant.ctrl.filters.build_speed_filter_chain()` | 保留 | 公开构造入口已存在, 不再缺口 | `tests/unit/assistant/test_stability_baseline.py` 里的滤波链基线测试 |
| `src/assistant/stability/filtering.py` | `build_gyro_filter` | `已退役` | `assistant.ctrl.filters.LowPassFilter` 与 `assistant.motion_runtime.create_runtime_state()` | 退役旧 builder, 保留低通能力 | 当前代码没有任何 `build_gyro_filter` 调用点, runtime 已直接用公开 `LowPassFilter` 构造 `gyro_lpf` | `tests/unit/assistant/test_stability_baseline.py` 里的低通落点测试 |
| `src/assistant/stability/attitude.py` | `euler_to_quaternion` | `已退役` | 无单独公开入口; 能力收敛到 `assistant.ctrl.attitude.HeadingEstimator` 内部四元数积分 | 退役 | 当前主线没有欧拉角转四元数调用点, 运行链只消费航向积分结果 | `tests/unit/assistant/test_stability_baseline.py` 里的航向估计测试, 外加代码检索无调用点 |
| `src/assistant/stability/attitude.py` | `quaternion_to_euler` | `已退役` | 无单独公开入口; yaw 提取由 `assistant.ctrl.attitude.HeadingEstimator.yaw_rad()` 承接 | 退役 | 当前主线没有四元数转欧拉角调用点, 只保留 yaw 提取 | `tests/unit/assistant/test_stability_baseline.py` 里的航向估计测试, 外加代码检索无调用点 |
| `src/assistant/stability/attitude.py` | yaw 语义换算 | `已迁入 ctrl（主线运行）` | `assistant.ctrl.attitude.HeadingEstimator.yaw_rad()` 与 `assistant.ctrl.attitude.update_heading_from_gyro()` | 保留 | 主线每拍都通过 `ctrl.attitude` 推进四元数并刷新 `heading_deg` | `tests/unit/assistant/test_stability_baseline.py` 里的航向估计与航向修正测试 |
| `src/assistant/stability/kinematics.py` | `body_axis_semantics` | `已退役` | 语义分散落在 `assistant.ctrl.kinematics.rotate_body_delta_to_world()`、`assistant.ctrl.kinematics.resolve_follow_velocity()` 与 `docs/developer/legacy-stability-baseline.md` | 退役说明性函数, 保留语义 | 当前没有代码消费“方向字典”本身, 但跟随链仍直接依赖 `x 右 y 前` 语义做世界系/车体系换算 | `tests/unit/assistant/test_stability_baseline.py` 里的随动旋转与运动学基线测试 |
| `src/assistant/stability/kinematics.py` | `rotate_body_delta_to_world` | `已迁入 ctrl（主线运行）` | `assistant.ctrl.kinematics.rotate_body_delta_to_world()` | 保留 | 辅车随动目标捕获 `_capture_follow_target()` 仍直接调用该入口 | `tests/unit/assistant/test_stability_baseline.py` 里的随动旋转测试 |
| `src/assistant/stability/control.py` | `HeadingController` | `已迁入 ctrl（主线运行）` | `assistant.ctrl.attitude.compute_heading_correction()` | 保留控制语义, 退役旧类名 | 当前航向保持已升级为带积分与限幅的公开函数, runtime 直接导入该入口, 不在 `pid.py` | `tests/unit/assistant/test_stability_baseline.py` 里的航向修正测试 |

## 本次核对后的结论

- 本次没有发现“对车自身状态稳定或滤波链通畅仍必要, 但当前完全没有真实落点”的项, 因此不需要补新的运行时代码。
- 本次补充了一条最小单元测试, 只为把“角速度低通已经由公开 `LowPassFilter` 承接并被主辅 runtime 直接使用”这件事钉成可回归事实。
- 后续若要恢复主车 `MOVE` 体增量语义, 应作为新任务显式重建主车公开坐标换算入口, 不在本任务范围内顺手扩展。
