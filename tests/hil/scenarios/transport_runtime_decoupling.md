# Transport 运行时解耦 HIL 证据

## 背景

- 任务来源: `docs/superpowers/plans/2026-03-12-transport-runtime-decoupling.md` Task 9
- 本轮目标: 为 transport runtime decoupling 提供设备侧最小 smoke 与 HIL 记录
- 用户决定: 明确要求跳过 Stage 3 `uart3` 人工调试

## 设备信息

- Date: 2026-03-13
- Firmware 基线: `b876573` + 当前未提交工作树修改
- Port: `/dev/cu.usbmodem1101`
- Device: `micropython 1.20.0 | mimxrt | RT1021 MicroPython by NXP & SeekFree with CoreBoard-144Pin V2.1.0`
- Operator: OpenCode + 用户在环

## Stage 2 裸片 smoke

### 操作步骤

1. 主机执行 `mpy-cli list`, 确认可用设备端口为 `/dev/cu.usbmodem1101`
2. 主机执行 `python3 tools/run_stage2_smoke.py --port /dev/cu.usbmodem1101`

### 预期行为

- 返回 `status=ok`
- query token 完整, `missing=none`
- 板端最小 query smoke 可执行
- 远端临时 probe 能自动删除

### 实际输出

```text
status=ok reason=ok
status status=ok reason=ok
queries count=9 missing=none
smoke mode=lite init=0 queries=1 step=0 tick_count=0 snapshots=none
```

### 结论

- Stage 2: PASS
- 说明: 当前板端以 `lite` 模式完成最小安全 smoke, 已证明最小 query 链路可执行
- 限制: 本结果不证明 full runtime import/step 在当前板端内存预算下稳定可运行

## Stage 3 `uart3` observe

### 状态

- Result: SKIPPED
- Reason: 用户明确要求跳过 Stage 3

### 因跳过而未验证的内容

- `?health/?tick/?imu/?enc/?motor/?vision/?lock/?pos` 从 `uart3` 的真实回包稳定性
- `uart6` 连续视觉流与 `uart3` 查询并发
- `reset` 打断视觉推行链路
- 5ms 控制周期下的板端 overrun 现场观测
- 视觉链路与命令链路在真实负载下的时序耦合

## HIL 总结

- Result: PARTIAL
- 已完成证据: Stage 2 lite smoke PASS
- 未完成证据: Stage 3 `uart3` observe
- 风险结论: 当前不能宣称 transport runtime decoupling 已获得完整设备侧验证, 只能宣称最小板端 smoke 已通过
