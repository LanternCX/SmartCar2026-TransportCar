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

1. 持续从 OpenArt 向 `UART6` 发送 `x=<pixel_x>,y=<pixel_y>`
2. 观察车辆在 `ALIGN_ANGLE -> ALIGN_DIST -> ALIGN_DX` 阶段的连续跟踪
3. 预期现象：车辆控制连续、无明显等待 `?lock` 的停顿；`UART3` 无连续错误输出

## 场景 E：视觉目标丢失恢复

1. 在视觉对正阶段发送若干帧 `x,y`
2. 然后停止发送视觉包超过 `VISION_OBSERVATION_TIMEOUT_MS`
3. 预期现象：状态机回到 `IDLE`，车辆停止继续逼近目标

## 场景 F：视觉推行中的复位中断

1. 让车辆进入 `PUSHING`
2. 在推行中发送 `reset`
3. 预期现象：里程计与航向被复位，视觉内部目标被清空，不再继续沿旧目标推行

## 场景 G：Stage 3 设备观测脚本

1. 确保设备已刷入当前分支代码
2. 在主机执行：`python3 tools/run_device_observe.py --port /dev/cu.usbmodem1101`
3. 预期输出包含：`OBSERVE health ...`、`OBSERVE tick ...`、`OBSERVE imu ...`、`OBSERVE enc ...`、`OBSERVE motor ...`、`OBSERVE vision ...`
4. 预期最终状态为 `status=ok`，且 `tick.overrun=0`
5. 若失败，记录 `status`、`reason` 与完整观测输出

## 证据记录

- Date:
- Firmware commit:
- Operator:
- Result: PASS / FAIL
- Notes:
