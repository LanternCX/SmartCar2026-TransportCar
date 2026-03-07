# HIL 验证层

本目录记录那些无法被主机侧 `unit/contract` 完全替代的板级验证项。

## 范围

- UART 通信时序与总线冲突
- 电机方向、PWM 输出与模式切换
- 编码器负载噪声与里程计累积误差
- IMU 零漂、航向估计与视觉闭环耦合效果

## 执行规则

以下改动必须补 HIL 证据：

- 任何触及 `hardware/` 的改动
- 任何触及 `src/services/transport_car.py` 的改动
- 任何改变控制周期假设、UART 行为或视觉状态机节拍的改动

## 证据模板

每个场景至少记录：

1. 操作步骤 / 测试命令
2. 预期行为
3. 实际 UART 输出或测量结果
4. 结论（PASS / FAIL）

参考基线场景：`tests/hil/scenarios/basic_motion.md`
