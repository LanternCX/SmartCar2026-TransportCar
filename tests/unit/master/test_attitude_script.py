def test_quaternion_to_euler_deg_returns_identity_angles() -> None:
    from master.ctrl.attitude import quaternion_to_euler_deg

    roll_deg, pitch_deg, yaw_deg = quaternion_to_euler_deg(1.0, 0.0, 0.0, 0.0)

    assert roll_deg == 0.0
    assert pitch_deg == 0.0
    assert yaw_deg == 0.0


def test_normalize_gyro_deg_s_rounds_to_one_decimal() -> None:
    from master.script.inspect_attitude import normalize_gyro_deg_s

    assert normalize_gyro_deg_s((0.183, -0.149, 1.99)) == (0.2, -0.1, 2.0)


def test_heading_estimator_euler_deg_tracks_yaw_rotation() -> None:
    import math

    from master.ctrl.attitude import HeadingEstimator, estimator_euler_deg

    estimator = HeadingEstimator()
    estimator.update(0.0, 0.0, 90.0, 1.0)

    roll_deg, pitch_deg, yaw_deg = estimator_euler_deg(estimator)

    assert abs(roll_deg) < 1e-6
    assert abs(pitch_deg) < 1e-6
    assert yaw_deg == math.degrees(estimator.yaw_rad())
    assert yaw_deg > 70.0


def test_inspect_attitude_feeds_degree_rate_directly_into_estimator() -> None:
    from pathlib import Path

    content = Path("src/master/script/inspect_attitude.py").read_text(encoding="utf-8")

    assert "estimator.update(" in content
    assert "gx_deg_s," in content
    assert "gy_deg_s," in content
    assert "gz_deg_s," in content
    assert "gx_deg_s * rad_scale" not in content


def test_inspect_attitude_formats_quaternion_and_euler_line() -> None:
    from master.script.inspect_attitude import format_attitude_line

    line = format_attitude_line(
        tick=3,
        quat=(1.0, 0.0, 0.0, 0.0),
        euler_deg=(0.0, 0.0, 0.0),
        gyro_deg_s=(1.2, -3.4, 5.6),
        dt_s=0.012,
    )

    assert "tick=3" in line
    assert "dt_s=0.012000" in line
    assert "quat=(1.000000,0.000000,0.000000,0.000000)" in line
    assert "roll_deg=0.000" in line
    assert "pitch_deg=0.000" in line
    assert "yaw_deg=0.000" in line
    assert "gyro_deg_s=(1.200,-3.400,5.600)" in line


def test_inspect_attitude_has_direct_run_guard() -> None:
    from pathlib import Path

    content = Path("src/master/script/inspect_attitude.py").read_text(encoding="utf-8")

    assert 'if __name__ == "__main__"' in content


def test_inspect_attitude_supports_direct_board_imports() -> None:
    from pathlib import Path

    content = Path("src/master/script/inspect_attitude.py").read_text(encoding="utf-8")

    assert "from ctrl.attitude import HeadingEstimator, estimator_euler_deg" in content
    assert "from hw.imu import build_imu_bundle" in content


def test_inspect_attitude_uses_unbounded_loop_when_max_ticks_non_positive() -> None:
    from pathlib import Path

    content = Path("src/master/script/inspect_attitude.py").read_text(encoding="utf-8")

    assert "while True:" in content
    assert "# if int(max_ticks) > 0 and tick > int(max_ticks):" in content


def test_inspect_attitude_uses_dynamic_dt_from_ticks_us() -> None:
    from pathlib import Path

    content = Path("src/master/script/inspect_attitude.py").read_text(encoding="utf-8")

    assert "time.ticks_us()" in content
    assert "time.ticks_diff" in content
