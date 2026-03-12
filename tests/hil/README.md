# HIL 验证层

本目录记录那些无法被主机侧 `unit/contract` 完全替代的板级验证项。

## 范围

- UART 通信时序与总线冲突
- 电机方向、PWM 输出与模式切换
- 编码器负载噪声与里程计累积误差
- IMU 零漂、航向估计与视觉闭环耦合效果
- Stage 2 裸片 smoke 输出与失败归因
- Stage 3 `uart3` 人工调试日志与结论

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

## Stage 2 自动化入口

当前仓库提供一个主机侧 Stage 2 裸片 smoke 脚本：

```bash
python3 tools/run_stage2_smoke.py --port /dev/cu.usbmodem1101
```

其职责是：

1. 通过 `mpy-cli` 上传临时探针 `tools/stage2_smoke_probe.py`
2. 在 `diagnostic_mode=True` 下验证最小安全初始化与短时运行
3. 采集 `STAGE2 ...` 结构化输出
4. 自动删除远端临时探针

当 `status != ok` 时，需将完整输出附到 HIL 记录中。

当前 Stage 2 裸片 smoke 允许两类通过结果：

1. `mode=full`：说明板端完成了完整 runtime 导入与最小 step
2. `mode=lite`：说明板端至少完成了最小 query smoke, query token 完整且结构化输出正常

若结果为 `mode=lite`, 只能证明最小安全 smoke 可执行, 不能替代 Stage 3 `uart3` observe。

## Stage 3 人工调试

Stage 3 不再依赖自动脚本，而是要求操作者通过 `uart3` 进行人工调试：

1. 保持 `uart6` 继续与 OpenArt 通信
2. 通过 `uart3` 查询 `?health/?tick/?imu/?enc/?motor/?vision/?lock/?pos`
3. 记录关键串口回显、现场现象与 AI 给出的归因建议

参考基线场景：`tests/hil/scenarios/basic_motion.md`

若用户明确要求跳过 Stage 3, 必须在对应 HIL 记录中显式写明 `Stage 3 skipped by user` 以及剩余风险, 不得将该轮结果表述为完整设备验证通过
