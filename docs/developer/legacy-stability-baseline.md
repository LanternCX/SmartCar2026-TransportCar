# legacy 稳定性基线抽取

## 1. 说明

- `src/legacy` 现在是旧系统代码的实际归档位置, 本文从该归档实现中抽取稳定性语义, 作为 `master` / `assistant` 最小系统的迁移基线
- 本文关注控制真义、方向语义、关键参数与验证点, 不要求复刻旧目录结构

## 2. 底盘控制语义

- 底盘控制链 owner 参考 `src/legacy/services/runtime/motion_runtime.py`
- 稳定性内核至少包含: 轮速链、偏航控制、姿态更新、里程计更新
- `master` / `assistant` 第一版不重建完整旧闭环外壳, 但保留以下语义:
  - `ARM` 后才允许执行 `VEL` / `MOVE`
  - `STOP` / 超时必须把速度命令清零并退出忙碌态
  - `HOLD` 表示停止推进并保持当前姿态/位置结果不再继续累积

## 3. 滤波链语义

- 轮速输入链基线来自 `src/legacy/services/runtime/motion_runtime.py`
- 每个轮速状态先经过 `SpikeMedianFilter(window=5)`, 再经过 `DiffLimitFilter(max_delta=5.0)`
- 角速度链使用 `LowPassFilter(alpha=0.2)` 做一阶低通, 用于平滑 yaw rate
- `master` / `assistant` 最小系统保留两类语义:
  - 速度输入链保留“先去尖峰, 再限斜率”
  - 角速度链保留“一阶低通平滑”

## 4. 运动学语义

- 车体系方向按当前协议统一为: `x+ = 右`, `y+ = 前`, `omega+ = 顺时针`
- `MOVE dx dy dtheta` 表示车体系相对增量, 不是世界系绝对目标
- `master` / `assistant` 最小系统中:
  - `MOVE` 先按当前 heading 把车体系增量旋转到世界系
  - 再累积到最小 `odom`
  - `RESET_ODOM` 把 `odom` 与 `heading` 一起归零

## 5. 陀螺仪 / 四元数 / 欧拉角语义

- 姿态解算基线参考 `src/legacy/control/attitude_estimator.py` 与 `src/legacy/utils/quaternion.py`
- 陀螺仪原始角速度按 deg/s 比例缩放后积分进四元数
- 四元数采用 `(w, x, y, z)`
- 欧拉角采用 Z-Y-X 顺序, 返回 `(roll, pitch, yaw)`
- `yaw` 语义需要保持和最小协议一致, 即顺时针为正

## 6. 关键方向 / 符号约定

- 参考系统一使用车体系 `x 右 y 前`
- `heading+` / `dtheta+` / `omega+` 都表示顺时针
- `odom` 在最小系统中保存世界系位置, 字段顺序固定为 `(x, y)`
- 汇报文本 `STATE` 必须至少覆盖 `armed`、`busy`、`last_cmd`、`odom`、`heading`

## 7. 关键参数语义

- `SpikeMedianFilter.window = 5`: 抑制单点异常值
- `DiffLimitFilter.max_delta = 5.0`: 限制单步速度突变
- `LowPassFilter.alpha = 0.2`: 平衡响应与平滑
- `HeadingController.kp = 0.16`: 保留最小偏航误差比例控制语义
- `HeadingController.omega_limit = 15.0`: 保留自动角速度限幅语义
- `SafetyGuard.timeout_ms`: 表示主车命令超时后必须进入停机保护的阈值

## 8. 最小系统验证点

- 协议解析:
  - `ARM` / `DISARM` / `STOP` / `PING` / `STATE?`
  - `VEL` / `MOVE` / `HOLD` / `RESET_ODOM`
- 稳定性基线:
  - 车体系方向约定保持 `x 右 y 前`
  - 四元数 / 欧拉角互转保持 yaw 语义不漂移
  - 速度滤波链保持“尖峰抑制 + 限斜率”顺序
- 安全保护:
  - 超时停机
  - 急停锁定与清除
- 最小状态:
  - `STATE` 可返回 `armed` / `busy` / `last_cmd` / `odom` / `heading`

## 9. 验证命令

- 主机侧单元验证:
  - `python3 -m pytest tests/unit/assistant/test_stability_baseline.py tests/unit/assistant/test_protocol.py tests/unit/assistant/test_safety.py tests/unit/assistant/test_motion_runtime.py tests/unit/assistant/test_app.py -q`
  - `python3 -m pytest tests/unit/master/test_stability_baseline.py tests/unit/master/test_vision_ingress.py tests/unit/master/test_vision_state_machine.py tests/unit/master/test_decision.py tests/unit/master/test_motion_runtime.py tests/unit/master/test_app.py -q`
