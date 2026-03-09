# 基础运动 HIL 场景

## 前置条件

- 设备已刷入当前代码
- IMU 已校准（`src/script/calibrate_gyro.py`）
- 电机辨识参数已存在（`/flash/ident_params.txt`）

## 场景 A：速度指令链路

1. 发送 `vy=10`
2. 预期车辆前进，且 UART 输出稳定
3. 发送 `vy=0`
4. 预期车辆停止且无明显振荡

## 场景 B：位置锁定链路

1. 发送 `dy=0.2`
2. 轮询 `?lock`
3. 预期运动中返回 `?lock=1`，稳定后返回 `?lock=0`

## 场景 C：复位安全性

1. 发送 `reset`
2. 查询 `?pos`
3. 预期位置与航向接近零点

## 场景 D：UART6 视觉跟踪链路

1. 持续从 OpenArt 向 `UART6` 发送 `left=<pixel_left>,top=<pixel_top>,right=<pixel_right>,bottom=<pixel_bottom>`
2. 观察车辆在 `ALIGN_ANGLE -> ALIGN_DIST -> ALIGN_DX` 阶段的连续跟踪
3. 预期现象：车辆控制连续、无明显等待 `?lock` 的停顿；`UART3` 无连续错误输出

## 场景 E：视觉目标丢失恢复

1. 在视觉对正阶段发送若干帧完整框 `left,top,right,bottom`
2. 然后停止发送视觉包超过 `VISION_OBSERVATION_TIMEOUT_MS`
3. 预期现象：状态机回到 `IDLE`，车辆停止继续逼近目标

## 场景 F：视觉推行中的复位中断

1. 让车辆进入 `PUSHING`
2. 在推行中发送 `reset`
3. 预期现象：里程计与航向被复位，视觉内部目标被清空，不再继续沿旧目标推行

## 场景 G：Stage 2 裸片 smoke

1. 确保设备已刷入当前分支代码
2. 在主机执行：`python3 tools/run_stage2_smoke.py --port /dev/cu.usbmodem1101`
3. 预期输出包含：`status=ok reason=ok`、`status status=ok`、`queries ...`、`smoke init=1 step=1 ...`
4. 若失败，记录 `status`、`reason` 与完整 smoke 输出

## 场景 H：Stage 3 `uart3` 人工调试

1. 保持 OpenArt 继续连接 `UART6`
2. 将调试串口接到 `UART3`
3. 人工发送 `?health`、`?tick`、`?imu`、`?enc`、`?motor`、`?vision`、`?lock`、`?pos`
4. 预期这些查询都从 `UART3` 收到结构化回包
5. 如需进一步排查，再结合动作命令、现场现象和 AI 建议记录结论

## 证据记录

- Date:
- Firmware commit:
- Operator:
- Result: PASS / FAIL
- Notes:
