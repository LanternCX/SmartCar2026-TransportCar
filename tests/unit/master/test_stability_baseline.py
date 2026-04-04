def test_master_planar_target_keeps_numeric_coordinates() -> None:
    from master.ctrl.kinematics import build_planar_target

    target = build_planar_target(10, -2.5)

    assert target == {"dx": 10.0, "dy": -2.5}


def test_master_ctrl_kinematics_exposes_motion_and_odometry_entrypoints() -> None:
    import types

    from master.ctrl.kinematics import (
        OmniKinematics,
        Odometry,
        update_odometry_from_wheels,
    )

    state = types.SimpleNamespace(
        kinematics=OmniKinematics(),
        odometry=Odometry(),
        wheel_speeds={"m": 0.0, "l": 10.0, "r": 10.0},
        tick_s=0.1,
        heading_deg=0.0,
        odom=[0.0, 0.0],
    )

    odom_x, odom_y = update_odometry_from_wheels(state)

    assert isinstance(odom_x, float)
    assert isinstance(odom_y, float)
    assert odom_x > 0.0
    assert state.odom == [odom_x, odom_y]


def test_master_ctrl_pid_exposes_wheel_speed_controller_entrypoint() -> None:
    import types

    from master.ctrl.pid import apply_wheel_speed_control, build_wheel_speed_controllers

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


def test_master_filter_chain_filters_speed_samples() -> None:
    import importlib

    filters_module = importlib.import_module("master.ctrl.filters")
    build_speed_filter_chain = getattr(filters_module, "build_speed_filter_chain")
    chain = build_speed_filter_chain()
    outputs = [chain.update(value) for value in (0.0, 100.0, 0.0)]

    assert all(isinstance(value, float) for value in outputs)
    assert outputs[1] != 100.0


def test_master_and_assistant_filter_chain_keep_same_default_output() -> None:
    from assistant.ctrl.filters import build_speed_filter_chain as build_assistant_chain
    from master.ctrl.filters import build_speed_filter_chain as build_master_chain

    samples = (0.0, 100.0, 0.0, 10.0)
    master_chain = build_master_chain()
    assistant_chain = build_assistant_chain()
    master_outputs = [master_chain.update(value) for value in samples]
    assistant_outputs = [assistant_chain.update(value) for value in samples]

    assert master_outputs == assistant_outputs


def test_master_and_assistant_runtime_use_public_low_pass_filter_entrypoint() -> None:
    import assistant.motion_runtime as assistant_runtime
    import master.motion_runtime as master_runtime

    from assistant.ctrl.filters import LowPassFilter as AssistantLowPassFilter
    from master.ctrl.filters import LowPassFilter as MasterLowPassFilter

    master_state = master_runtime.create_runtime_state(hw_bundle=None)
    assistant_state = assistant_runtime.create_runtime_state(
        timeout_ms=50, hw_bundle=None
    )

    assert isinstance(master_state.gyro_lpf, MasterLowPassFilter)
    assert isinstance(assistant_state.gyro_lpf, AssistantLowPassFilter)


def test_master_heading_estimator_updates_yaw() -> None:
    import importlib

    attitude_module = importlib.import_module("master.ctrl.attitude")
    heading_estimator = getattr(attitude_module, "HeadingEstimator")
    estimator = heading_estimator()
    estimator.update(0.0, 0.0, 90.0, 1.0)

    assert isinstance(estimator.yaw_rad(), float)
    assert estimator.yaw_rad() > 0.0


def test_master_heading_estimator_matches_legacy_quaternion_update() -> None:
    import math

    from legacy.utils.quaternion import Quaternion
    from master.ctrl.attitude import HeadingEstimator

    master_estimator = HeadingEstimator()
    legacy_estimator = Quaternion()

    gx_deg_s = 12.3
    gy_deg_s = -4.5
    gz_deg_s = 67.8
    dt_s = 0.017

    master_estimator.update(gx_deg_s, gy_deg_s, gz_deg_s, dt_s)
    legacy_estimator.update(
        math.radians(gx_deg_s),
        math.radians(gy_deg_s),
        math.radians(gz_deg_s),
        dt_s,
    )

    assert master_estimator.w == legacy_estimator.w
    assert master_estimator.x == legacy_estimator.x
    assert master_estimator.y == legacy_estimator.y
    assert master_estimator.z == legacy_estimator.z


def test_master_update_heading_from_gyro_matches_legacy_chain() -> None:
    import math
    import types

    from legacy.utils.quaternion import Quaternion
    from master.ctrl.attitude import HeadingEstimator, update_heading_from_gyro

    state = types.SimpleNamespace(
        imu_calibrated=(0.0, 0.0, 0.0, 32.768, -16.384, 49.152),
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
    )

    update_heading_from_gyro(state)

    legacy_estimator = Quaternion()
    legacy_estimator.update(
        math.radians(2.0),
        math.radians(-1.0),
        math.radians(3.0),
        0.02,
    )
    legacy_yaw = legacy_estimator.to_euler_yaw()

    assert state.last_yaw_rad == legacy_yaw
    assert state.heading_deg == math.degrees(legacy_yaw)
    assert state.yaw_rate_deg_s == 3.0


def test_master_update_heading_from_gyro_matches_verified_inspect_attitude_chain() -> (
    None
):
    import math
    import types

    import pytest

    from legacy.utils.quaternion import Quaternion
    from master.ctrl.attitude import HeadingEstimator, update_heading_from_gyro

    state = types.SimpleNamespace(
        imu_calibrated=(0.0, 0.0, 0.0, 34.4064, -16.384, 50.7904),
        gyro_scale=16.384,
        q_est=HeadingEstimator(),
        tick_s=0.02,
        last_yaw_rad=0.0,
        heading_deg=0.0,
        yaw_rate_deg_s=0.0,
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


def test_master_heading_correction_matches_legacy_pi_and_yaw_rate_damping() -> None:
    import types

    from master.ctrl.attitude import compute_heading_correction as master_compute

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

    assert master_compute(state) == 0.86


def test_master_heading_correction_accumulates_integral_by_tick_s() -> None:
    import pytest
    import types

    from master.ctrl.attitude import compute_heading_correction as master_compute

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

    master_compute(state)

    assert state.yaw_integral == pytest.approx(0.1)


def test_master_heading_correction_clamps_tick_scaled_integral() -> None:
    import types

    from master.ctrl.attitude import compute_heading_correction as master_compute

    state = types.SimpleNamespace(
        heading_hold_enabled=True,
        target_heading_deg=15.0,
        heading_deg=10.0,
        yaw_integral=19.95,
        yaw_kp=0.0,
        yaw_ki=1.0,
        yaw_kd=0.0,
        yaw_i_max=20.0,
        yaw_rate_deg_s=0.0,
        tick_s=0.02,
        auto_omega_max=50.0,
    )

    master_compute(state)

    assert state.yaw_integral == 20.0


def test_master_heading_correction_uses_shortest_turn_across_wrap() -> None:
    import types

    from master.ctrl.attitude import compute_heading_correction as master_compute

    state = types.SimpleNamespace(
        heading_hold_enabled=True,
        target_heading_deg=1.0,
        heading_deg=359.0,
        yaw_integral=0.0,
        yaw_kp=0.1,
        yaw_ki=0.0,
        yaw_kd=0.0,
        yaw_i_max=20.0,
        yaw_rate_deg_s=0.0,
        tick_s=0.02,
        auto_omega_max=5.0,
    )

    assert master_compute(state) == 0.2


def test_master_runtime_uses_ctrl_attitude_and_filter_entrypoints(monkeypatch) -> None:
    import types

    import master.motion_runtime as runtime

    captured = {"heading": 0, "filters": 0, "kinematics": 0, "odometry": 0, "pid": 0}

    def _fake_build_kinematics():
        captured["kinematics"] += 1
        return object()

    def _fake_build_odometry():
        captured["odometry"] += 1
        return object()

    def _fake_build_wheel_speed_controllers(pid_map, ident_lookup, output_limit):
        captured["pid"] += 1
        return {}

    def _fake_update_odometry(state):
        state.odom[0] = 1.5
        state.odom[1] = -0.5
        return (1.5, -0.5)

    def _fake_update_heading(state, heading_override=None):
        captured["heading"] += 1
        state.heading_deg = 12.0

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
    monkeypatch.setattr(runtime, "update_heading_from_gyro", _fake_update_heading)
    monkeypatch.setattr(runtime, "update_wheel_speeds", _fake_update_wheel_speeds)

    state = runtime.create_runtime_state(hw_bundle=None)
    snapshot = runtime.run_base_cycle(state, hw_bundle=None)

    assert captured == {
        "heading": 1,
        "filters": 1,
        "kinematics": 1,
        "odometry": 1,
        "pid": 1,
    }
    assert snapshot["heading_est_deg"] == 12.0
    assert snapshot["odom"] == (1.5, -0.5)


def test_master_runtime_dedupes_equal_cycle_tokens(monkeypatch) -> None:
    import master.motion_runtime as runtime

    captured = {"heading": 0, "filters": 0}

    class CycleToken:
        def __init__(self, value):
            self.value = value

        def __eq__(self, other):
            return isinstance(other, CycleToken) and self.value == other.value

    def _fake_update_heading(state, heading_override=None):
        captured["heading"] += 1

    def _fake_update_wheel_speeds(filter_bank, raw_ticks, wheel_names):
        captured["filters"] += 1
        return {name: 0.0 for name in wheel_names}

    monkeypatch.setattr(runtime, "update_heading_from_gyro", _fake_update_heading)
    monkeypatch.setattr(runtime, "update_wheel_speeds", _fake_update_wheel_speeds)

    state = runtime.create_runtime_state(hw_bundle=None)
    first_snapshot = runtime.run_base_cycle(
        state, hw_bundle=None, cycle_token=CycleToken(7)
    )
    second_snapshot = runtime.run_base_cycle(
        state,
        hw_bundle=None,
        cycle_token=CycleToken(7),
    )

    assert captured == {"heading": 1, "filters": 1}
    assert second_snapshot == first_snapshot
