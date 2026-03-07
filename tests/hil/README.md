# HIL 验证层

本目录记录那些无法被主机侧 `unit/contract` 完全替代的板级验证项。

## 范围

- UART 通信时序与总线冲突
- 电机方向、PWM 输出与模式切换
- 编码器负载噪声与里程计累积误差
- IMU 零漂、航向估计与视觉闭环耦合效果
- Stage 3 设备观测脚本输出与失败归因

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

## 可脚本化观测入口

当前仓库提供一个主机侧 Stage 3 观测脚本：

```bash
python3 tools/run_device_observe.py --port /dev/cu.usbmodem1101
```

其职责是：

1. 通过 `mpy-cli` 上传临时探针 `tools/device_observe_probe.py`
2. 在设备侧短时运行控制循环并采样诊断快照
3. 回收 `OBSERVE health/tick/imu/enc/motor/vision` 输出
4. 自动删除远端临时探针

当 `status != ok` 时，需将完整输出附到 HIL 记录中。

参考基线场景：`tests/hil/scenarios/basic_motion.md`
