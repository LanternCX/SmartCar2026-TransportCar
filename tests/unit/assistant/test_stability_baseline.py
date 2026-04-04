def test_assistant_follow_offset_rotation_belongs_to_control_math() -> None:
    from assistant.ctrl.kinematics import rotate_body_delta_to_world

    world_x, world_y = rotate_body_delta_to_world(10.0, 0.0, 90.0)

    assert abs(world_x) < 1e-6
    assert abs(world_y + 10.0) < 1e-6


def test_assistant_ctrl_kinematics_exposes_motion_and_odometry_entrypoints() -> None:
    import types

    from assistant.ctrl.kinematics import (
        OmniKinematics,
        Odometry,
        resolve_follow_velocity,
        update_odometry_from_wheels,
    )

    state = types.SimpleNamespace(
        kinematics=OmniKinematics(),
        odometry=Odometry(),
        wheel_speeds={"m": 0.0, "l": 10.0, "r": 10.0},
        tick_s=0.1,
        heading_deg=0.0,
        odom=[0.0, 0.0],
        follow_target_world=(1.0, 0.0),
        follow_position_kp=2.0,
        follow_position_max_speed=0.5,
    )

    odom_x, odom_y = update_odometry_from_wheels(state)
    body_dx, body_dy = resolve_follow_velocity(state)

    assert isinstance(odom_x, float)
    assert isinstance(odom_y, float)
    assert odom_x > 0.0
    assert body_dx == 0.5
    assert body_dy == 0.0


def test_assistant_ctrl_pid_exposes_wheel_speed_controller_entrypoint() -> None:
    import types

    from assistant.ctrl.pid import (
        apply_wheel_speed_control,
        build_wheel_speed_controllers,
    )

    state = types.SimpleNamespace(
        wheel_controllers=build_wheel_speed_controllers(
            {"m": (1.0, 0.0, 0.0), "l": (1.0, 0.0, 0.0), "r": (1.0, 0.0, 0.0)},
            {},
            output_limit=100.0,
        ),
        target_wheel_speeds={"m": 0.0, "l": 0.0, "r": 0.0},
        wheel_speeds={"m": 1.0, "l": -1.0, "r": 0.5},
        motor_duties={"m": 0, "l": 0, "r": 0},
        tick_s=0.1,
    )

    outputs = apply_wheel_speed_control(
        state,
        {"m": 5.0, "l": -5.0, "r": 2.0},
        limit=20.0,
    )

    assert outputs["m"] == 4.0
    assert outputs["l"] == -4.0
    assert outputs["r"] == 1.5
    assert state.target_wheel_speeds == {"m": 5.0, "l": -5.0, "r": 2.0}
    assert state.motor_duties == {"m": 4, "l": -4, "r": 1}


def test_assistant_heading_estimator_updates_yaw() -> None:
    import importlib

    attitude_module = importlib.import_module("assistant.ctrl.attitude")
    heading_estimator = getattr(attitude_module, "HeadingEstimator")
    estimator = heading_estimator()
    estimator.update(0.0, 0.0, 90.0, 1.0)

    assert isinstance(estimator.yaw_rad(), float)
    assert estimator.yaw_rad() > 0.0


def test_assistant_update_heading_from_gyro_uses_real_elapsed_time() -> None:
    import math
    import types

    import pytest

    from legacy.utils.quaternion import Quaternion
    from assistant.ctrl.attitude import HeadingEstimator, update_heading_from_gyro

    state = types.SimpleNamespace(
        imu_calibrated=(0.0, 0.0, 0.0, 34.4064, -16.384, 50.7904),
        gyro_scale=16.384,
        q_est=HeadingEstimator(),
        tick_s=0.02,
        last_yaw_rad=0.0,
        heading_deg=0.0,
        yaw_rate_deg_s=0.0,
        gyro_lpf=types.SimpleNamespace(update=lambda value: value),
        heading_target_ready=True,
        target_heading_deg=0.0,
        yaw_integral=0.0,
        last_attitude_time_us=1_000_000,
    )

    update_heading_from_gyro(state, now_us=1_012_345)

    legacy_estimator = Quaternion()
    legacy_estimator.update(
        math.radians(2.1),
        math.radians(-1.0),
        math.radians(3.1),
        0.012345,
    )
    legacy_yaw = legacy_estimator.to_euler_yaw()

    assert state.last_attitude_time_us == 1_012_345
    assert state.tick_s == pytest.approx(0.012345)
    assert state.last_yaw_rad == pytest.approx(legacy_yaw)
    assert state.heading_deg == pytest.approx(math.degrees(legacy_yaw))
    assert state.yaw_rate_deg_s == 3.1


def test_assistant_update_heading_from_gyro_does_not_fallback_to_fixed_tick_without_real_dt() -> (
    None
):
    import types

    import pytest

    from assistant.ctrl.attitude import HeadingEstimator, update_heading_from_gyro

    captured = []

    state = types.SimpleNamespace(
        imu_calibrated=(0.0, 0.0, 0.0, 32.768, 0.0, 49.152),
        gyro_scale=16.384,
        q_est=HeadingEstimator(),
        tick_s=0.02,
        last_yaw_rad=0.0,
        heading_deg=0.0,
        yaw_rate_deg_s=7.5,
        gyro_lpf=types.SimpleNamespace(
            update=lambda value: captured.append(value) or value
        ),
        heading_target_ready=True,
        target_heading_deg=0.0,
        yaw_integral=0.0,
        last_attitude_time_us=None,
    )

    update_heading_from_gyro(state, now_us=1_000_000)

    assert state.last_attitude_time_us == 1_000_000
    assert state.tick_s == 0.0
    assert state.last_yaw_rad == pytest.approx(0.0)
    assert state.heading_deg == pytest.approx(0.0)
    assert state.yaw_rate_deg_s == 7.5
    assert captured == []


def test_assistant_update_heading_from_gyro_does_not_advance_on_non_positive_dt() -> (
    None
):
    import types

    import pytest

    from assistant.ctrl.attitude import HeadingEstimator, update_heading_from_gyro

    state = types.SimpleNamespace(
        imu_calibrated=(0.0, 0.0, 0.0, 32.768, 0.0, 49.152),
        gyro_scale=16.384,
        q_est=HeadingEstimator(),
        tick_s=0.02,
        last_yaw_rad=0.0,
        heading_deg=0.0,
        yaw_rate_deg_s=0.0,
        gyro_lpf=types.SimpleNamespace(update=lambda value: value),
        heading_target_ready=True,
        target_heading_deg=0.0,
        yaw_integral=0.0,
        last_attitude_time_us=1_000_000,
    )

    update_heading_from_gyro(state, now_us=999_000)

    assert state.last_attitude_time_us == 1_000_000
    assert state.tick_s == 0.0
    assert state.last_yaw_rad == pytest.approx(0.0)
    assert state.heading_deg == pytest.approx(0.0)
    assert state.yaw_rate_deg_s == 0.0


def test_assistant_update_heading_from_gyro_ignores_invalid_timestamp_before_next_valid_dt() -> (
    None
):
    import types

    import pytest

    from assistant.ctrl.attitude import HeadingEstimator, update_heading_from_gyro

    state = types.SimpleNamespace(
        imu_calibrated=(0.0, 0.0, 0.0, 32.768, 0.0, 49.152),
        gyro_scale=16.384,
        q_est=HeadingEstimator(),
        tick_s=0.02,
        last_yaw_rad=0.0,
        heading_deg=0.0,
        yaw_rate_deg_s=0.0,
        gyro_lpf=types.SimpleNamespace(update=lambda value: value),
        heading_target_ready=True,
        target_heading_deg=0.0,
        yaw_integral=0.0,
        last_attitude_time_us=1_000_000,
    )

    update_heading_from_gyro(state, now_us=999_000)

    assert state.last_attitude_time_us == 1_000_000
    assert state.tick_s == 0.0

    update_heading_from_gyro(state, now_us=1_001_000)

    assert state.last_attitude_time_us == 1_001_000
    assert state.tick_s == pytest.approx(0.001)


def test_assistant_filter_chain_filters_speed_samples() -> None:
    import importlib

    filters_module = importlib.import_module("assistant.ctrl.filters")
    build_speed_filter_chain = getattr(filters_module, "build_speed_filter_chain")
    chain = build_speed_filter_chain()
    outputs = [chain.update(value) for value in (0.0, 100.0, 0.0)]

    assert all(isinstance(value, float) for value in outputs)
    assert outputs[1] != 100.0


def test_assistant_heading_correction_uses_shortest_turn_across_wrap() -> None:
    import types

    from assistant.ctrl.attitude import compute_heading_correction

    state = types.SimpleNamespace(
        heading_hold_enabled=True,
        target_heading_deg=1.0,
        heading_deg=359.0,
        yaw_integral=0.0,
        yaw_kp=0.1,
        yaw_ki=0.0,
        yaw_i_max=20.0,
        auto_omega_max=5.0,
    )

    assert compute_heading_correction(state) == 0.2


def test_assistant_heading_correction_matches_tick_scaled_pi_and_yaw_rate_damping() -> (
    None
):
    import types

    from assistant.ctrl.attitude import compute_heading_correction

    state = types.SimpleNamespace(
        heading_hold_enabled=True,
        target_heading_deg=15.0,
        heading_deg=10.0,
        yaw_integral=0.0,
        yaw_kp=0.2,
        yaw_ki=0.1,
        yaw_kd=0.05,
        yaw_i_max=20.0,
        yaw_rate_deg_s=3.0,
        tick_s=0.02,
        auto_omega_max=5.0,
    )

    assert compute_heading_correction(state) == 0.86


def test_assistant_update_heading_from_gyro_keeps_raw_yaw_rate_for_correction() -> None:
    import types

    import pytest

    from assistant.ctrl.attitude import HeadingEstimator, update_heading_from_gyro

    state = types.SimpleNamespace(
        imu_calibrated=(0.0, 0.0, 0.0, 32.768, 0.0, 49.152),
        gyro_scale=16.384,
        q_est=HeadingEstimator(),
        tick_s=0.02,
        last_yaw_rad=0.0,
        heading_deg=0.0,
        yaw_rate_deg_s=0.0,
        gyro_lpf=types.SimpleNamespace(update=lambda value: 1.25),
        heading_target_ready=True,
        target_heading_deg=0.0,
        yaw_integral=0.0,
        last_attitude_time_us=1_000_000,
    )

    update_heading_from_gyro(state, now_us=1_020_000)

    assert state.tick_s == pytest.approx(0.02)
    assert state.yaw_rate_deg_s == 3.0


def test_assistant_heading_correction_accumulates_integral_by_tick_s() -> None:
    import types

    import pytest

    from assistant.ctrl.attitude import compute_heading_correction

    state = types.SimpleNamespace(
        heading_hold_enabled=True,
        target_heading_deg=15.0,
        heading_deg=10.0,
        yaw_integral=0.0,
        yaw_kp=0.0,
        yaw_ki=1.0,
        yaw_kd=0.0,
        yaw_i_max=20.0,
        yaw_rate_deg_s=0.0,
        tick_s=0.02,
        auto_omega_max=5.0,
    )

    compute_heading_correction(state)

    assert state.yaw_integral == pytest.approx(0.1)


def test_assistant_runtime_uses_ctrl_attitude_and_filter_entrypoints(
    monkeypatch,
) -> None:
    import types

    import assistant.motion_runtime as runtime

    captured = {"heading": 0, "filters": 0, "kinematics": 0, "odometry": 0, "pid": 0}

    def _fake_build_kinematics():
        captured["kinematics"] += 1
        return types.SimpleNamespace(
            inverse_kinematics=lambda vx, vy, omega: {"m": 0.0, "l": 0.0, "r": 0.0}
        )

    def _fake_build_odometry():
        captured["odometry"] += 1
        return object()

    def _fake_build_wheel_speed_controllers(pid_map, ident_lookup, output_limit):
        captured["pid"] += 1
        return {}

    def _fake_update_odometry(state):
        state.odom[0] = 2.0
        state.odom[1] = -1.0
        return (2.0, -1.0)

    def _fake_apply_wheel_speed_control(state, wheel_targets, limit, motors=None):
        return {"m": 0.0, "l": 0.0, "r": 0.0}

    def _fake_update_heading(state, heading_override=None):
        captured["heading"] += 1
        state.heading_deg = 8.0
        state.tick_s = 0.005

    def _fake_update_wheel_speeds(filter_bank, raw_ticks, wheel_names):
        captured["filters"] += 1
        return {name: 0.0 for name in wheel_names}

    monkeypatch.setattr(runtime, "build_kinematics", _fake_build_kinematics)
    monkeypatch.setattr(runtime, "build_odometry", _fake_build_odometry)
    monkeypatch.setattr(
        runtime,
        "build_wheel_speed_controllers",
        _fake_build_wheel_speed_controllers,
    )
    monkeypatch.setattr(runtime, "update_odometry_from_wheels", _fake_update_odometry)
    monkeypatch.setattr(
        runtime, "apply_wheel_speed_control", _fake_apply_wheel_speed_control
    )
    monkeypatch.setattr(runtime, "update_heading_from_gyro", _fake_update_heading)
    monkeypatch.setattr(runtime, "update_wheel_speeds", _fake_update_wheel_speeds)

    state = runtime.create_runtime_state(timeout_ms=50, hw_bundle=None)
    runtime.run_base_cycle(state, now_ms=0, hw_bundle=None)

    assert captured == {
        "heading": 1,
        "filters": 1,
        "kinematics": 1,
        "odometry": 1,
        "pid": 1,
    }
    assert state.heading_deg == 8.0
    assert tuple(state.odom) == (2.0, -1.0)


def test_assistant_runtime_dedupes_equal_cycle_tokens(monkeypatch) -> None:
    import assistant.motion_runtime as runtime

    captured = {"heading": 0, "filters": 0, "motor": 0}

    class CycleToken:
        def __init__(self, value):
            self.value = value

        def __eq__(self, other):
            return isinstance(other, CycleToken) and self.value == other.value

    def _fake_update_heading(state, heading_override=None):
        captured["heading"] += 1
        state.tick_s = 0.005

    def _fake_update_wheel_speeds(filter_bank, raw_ticks, wheel_names):
        captured["filters"] += 1
        return {name: 0.0 for name in wheel_names}

    def _fake_apply_motor_output(state, dx, dy, omega):
        captured["motor"] += 1

    monkeypatch.setattr(runtime, "update_heading_from_gyro", _fake_update_heading)
    monkeypatch.setattr(runtime, "update_wheel_speeds", _fake_update_wheel_speeds)
    monkeypatch.setattr(runtime, "_apply_motor_output", _fake_apply_motor_output)

    state = runtime.create_runtime_state(timeout_ms=50, hw_bundle=None)
    first_reply = runtime.run_base_cycle(
        state, now_ms=0, hw_bundle=None, cycle_token=CycleToken(9)
    )
    second_reply = runtime.run_base_cycle(
        state,
        now_ms=0,
        hw_bundle=None,
        cycle_token=CycleToken(9),
    )

    assert captured == {"heading": 1, "filters": 1, "motor": 1}
    assert second_reply == first_reply
