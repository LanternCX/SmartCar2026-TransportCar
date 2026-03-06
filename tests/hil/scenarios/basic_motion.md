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

## Evidence Record

- Date:
- Firmware commit:
- Operator:
- Result: PASS / FAIL
- Notes:
