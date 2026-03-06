# HIL Validation Layer

This layer documents board-level validation that cannot be fully replaced by host-side unit tests.

## Scope

- UART communication timing and conflicts
- Motor direction and PWM behavior
- Encoder noise behavior under load
- IMU drift and calibration effects

## Execution Rule

Run HIL checks for:

- any change touching `hardware/`
- any change touching `services/transport_car.py`
- any change altering control-loop timing assumptions

## Evidence Template

For each scenario, record:

1. test command / action
2. expected behavior
3. observed UART output or measurement
4. pass/fail decision

See `tests/hil/scenarios/basic_motion.md` for baseline scenarios.
