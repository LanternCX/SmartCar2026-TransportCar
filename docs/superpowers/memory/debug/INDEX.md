# debug Index

## Type
debug

## Global TOC

| Page ID | Date | Title | Path | Related Change Unit | Keywords |
| --- | --- | --- | --- | --- | --- |
| 2026-04-08-2 | 2026-04-08 | 上调辅车位置式固定平移速度上限以扩大单窗口位移 | `docs/superpowers/memory/debug/entries/2026-04/2026-04-08-2.md` | 把辅车位置式默认平移速度上限从 1.5 上调到 3.0，并用主机侧回归固定住“只改固定上限、不扩协议与模式语义”的边界。 | assistant, follow-position, speed-cap, motion-runtime, runtime-params, regression, debug |
| 2026-04-08-1 | 2026-04-08 | 修复辅车速度模式后续周期退回普通路径的问题 | `docs/superpowers/memory/debug/entries/2026-04/2026-04-08-1.md` | 收敛辅车速度模式只在收包当拍生效的问题，并把默认朝向保持与显式角速度例外规则收口到统一周期分发。 | assistant, follow-velocity, heading-hold, motion-runtime, mode-state, regression, debug |
| 2026-04-06-1 | 2026-04-06 | 主车视觉状态机后的内存恶化主因是串口收发而不是双窗口滤波 | `docs/superpowers/memory/debug/entries/2026-04/2026-04-06-1.md` | 记录主车视觉状态机接入后内存恶化的根因收敛结果, 结论是串口收发热路径才是主因, 双窗口滤波不是这轮主故障源。 | master, memory, uart, vision-state-machine, micropython, filter, debug |
| 2026-04-04-3 | 2026-04-04 | 参数辨识脚本中速度除以3的设计原理澄清 | `docs/superpowers/memory/debug/entries/2026-04/2026-04-04-3.md` | 记录三轮全向底盘参数辨识时速度除以3的设计原理，防止未来误解为bug。 | pid-identify, omni-wheel, coupling, design-rationale, plant-gain |
| 2026-04-04-2 | 2026-04-04 | 主车轮子方向与控制手感会被映射冲突和固定 dt 一起带偏 | `docs/superpowers/memory/debug/entries/2026-04/2026-04-04-2.md` | 收敛主车姿态量级恢复后暴露出的轮子方向反转和打印扰动问题, 最终修正运行时硬件映射并统一全链路动态 dt。 | master, heading-control, mapping, encoder, motor, dynamic-dt, feedforward |
| 2026-04-04-1 | 2026-04-04 | 主车运行时姿态口径必须对齐 inspect_attitude 的 yaw_deg | `docs/superpowers/memory/debug/entries/2026-04/2026-04-04-1.md` | 收敛主车 30 度手动旋转场景量级异常的问题, 通过对齐 `inspect_attitude.py` 的 `yaw_deg` 链路恢复可用朝向观测。 | master, attitude, yaw, inspect-attitude, imu, dt, heading-control |
| 2026-04-03-1 | 2026-04-03 | 梳理主车板端导入链、采样链与朝向保持链的关键坑点 | `docs/superpowers/memory/debug/entries/2026-04/2026-04-03-1.md` | 沉淀主车板端调试中已确认的导入失败、采样方式、目标锁定与诊断脚本问题，供上下文重置后继续接续。 | board, micropython, import, ticker, imu, heading-hold, inspect-attitude, calibrate-gyro |
| 2026-03-24-1 | 2026-03-24 | 修复视觉运行时装配与调试回包导致的回归失败 | `docs/superpowers/memory/debug/entries/2026-03/2026-03-24-1.md` | 修复主车视觉运行时未及时挂出协调器对象和查询测试误吃 trace 文本的问题，并以完整测试集验证收口。 | vision-runtime, uart, trace, tests, regression, transport-car |
| 2026-03-08-1 | 2026-03-08 | 为低内存板端补齐 Stage 2 full/lite 回退 | `docs/superpowers/memory/debug/entries/2026-03/2026-03-08-1.md` | 定位并修复低内存板端在 Stage 2 smoke 中无法完成 full 路径初始化的问题，补齐 full/lite 回退。 | stage2, lite, memory, mpy-cli, transport-car |
| 2026-03-09-1 | 2026-03-09 | 将视觉对正从单点观测切换为完整识别框 | `docs/superpowers/memory/debug/entries/2026-03/2026-03-09-1.md` | 修复视觉对正仍使用单点观测的问题，将状态机输入切换为完整识别框语义。 | vision, bbox, uart6, state-machine, diagnostics |
| 2026-03-11-1 | 2026-03-11 | 修复 ORBITING 切出后的残留旋转与航向跨圈语义 | `docs/superpowers/memory/debug/entries/2026-03/2026-03-11-1.md` | 定位 ORBITING 切出后的残留旋转与跨圈航向语义问题，并补齐回归验证。 | vision, orbiting, rear-only, heading, transport-car |
| 2026-03-13-1 | 2026-03-13 | 修复 remote_control 启动脚本对旧 wheel_states 接口的依赖 | `docs/superpowers/memory/debug/entries/2026-03/2026-03-13-1.md` | 修复 remote_control 启动脚本仍依赖旧 wheel_states 接口导致 ticker 无法真正启动的问题。 | remote-control, boot, ticker, transport-car, regression |
| 2026-03-15-1 | 2026-03-15 | 确认板端仍在运行旧版错误日志路径并阻塞 deploy | `docs/superpowers/memory/debug/entries/2026-03/2026-03-15-1.md` | 确认板端仍在运行旧版错误日志路径，并把问题进一步收敛到 deploy 握手与导入链峰值。 | oom, deploy, board, repl, remote-control, transport-car, logger |
| 2026-03-16-1 | 2026-03-16 | 修复 services.car.vision 对 types 模块的板端兼容问题 | `docs/superpowers/memory/debug/entries/2026-03/2026-03-16-1.md` | 修复 services.car.vision 顶层依赖 types 模块导致的 MicroPython 板端导入失败。 | micropython, types, vision, lazy-load, board, compatibility |
