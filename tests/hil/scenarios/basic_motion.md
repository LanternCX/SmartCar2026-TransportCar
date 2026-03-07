# Basic Motion HIL Scenario

## Preconditions

- Device flashed with current code
- IMU calibrated (`src/script/calibrate_gyro.py`)
- Motor identification parameters available (`/flash/ident_params.txt`)

## Scenario A: Velocity Command Path

1. Send `vy=10`
2. Expect vehicle forward motion and stable UART output stream
3. Send `vy=0`
4. Expect stop without oscillation

## Scenario B: Position Lock Path

1. Send `dy=0.2`
2. Poll `?lock`
3. Expect `?lock=1` during motion and `?lock=0` after settle

## Scenario C: Reset Safety

1. Send `reset`
2. Query `?pos`
3. Expect near-zero position and heading reset behavior

## Scenario D: UART6 Vision Tracking Path

1. 持续从 OpenArt 向 `UART6` 发送 `x=<pixel_x>,y=<pixel_y>`
2. 观察车辆在 `ALIGN_ANGLE -> ALIGN_DIST -> ALIGN_DX` 阶段的连续跟踪
3. 预期现象：车辆控制连续、无明显等待 `?lock` 的停顿；`UART3` 无连续错误输出

## Scenario E: Vision Target Lost Recovery

1. 在视觉对正阶段发送若干帧 `x,y`
2. 然后停止发送视觉包超过 `VISION_OBSERVATION_TIMEOUT_MS`
3. 预期现象：状态机回到 `IDLE`，车辆停止继续逼近目标

## Scenario F: Vision Push And Reset Interrupt

1. 让车辆进入 `PUSHING`
2. 在推行中发送 `reset`
3. 预期现象：里程计与航向被复位，视觉内部目标被清空，不再继续沿旧目标推行

## Evidence Record

- Date:
- Firmware commit:
- Operator:
- Result: PASS / FAIL
- Notes:
