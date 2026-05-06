"""`TransportCar` 对外行为测试."""

import inspect

import pytest

from config import params as real_params
from tests.unit.core.runtime_support import (
    CaptureUart,
    DummyMotor,
    DummyTicker,
    RecordingController,
    make_minimal_transport_car,
)


class _ResettableWithArgs:
    """记录复位参数的最小桩."""

    def __init__(self) -> None:
        self.reset_calls = []

    def reset(self, *args) -> None:
        self.reset_calls.append(args)


class _Odom:
    """记录里程计复位的最小桩."""

    def __init__(self, x=1.0, y=2.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1
        self.x = 0.0
        self.y = 0.0


class _Quat:
    """最小四元数桩."""

    def __init__(self) -> None:
        self.w = 0.5
        self.x = 1.0
        self.y = 2.0
        self.z = 3.0


def _make_control_car(**attrs):
    """构造可执行底盘控制入口的最小对象."""
    motors = [DummyMotor(), DummyMotor(), DummyMotor()]
    defaults = {
        "control_state": {"vx": 0.0, "vy": 0.0, "omega": 0.0},
        "command_lock": False,
        "command_mode": "none",
        "lock_start_time": 0,
        "orbit_mode": False,
        "orbit_radius_scale": 1.0,
        "_pending_dx": None,
        "_pending_dy": None,
        "_pending_d_angle": None,
        "_pending_lock": None,
        "heading_est": 0.0,
        "heading_target": 0.0,
        "_yaw_rate": 0.0,
        "yaw_integral": 0.0,
        "yaw_pid": RecordingController(return_value=0.0),
        "gyro_lpf": _ResettableWithArgs(),
        "q_est": _Quat(),
        "last_yaw_rad": 9.0,
        "odometry": _Odom(),
        "target_speeds": {"m": 0.0, "l": 0.0, "r": 0.0},
        "wheel_states": [
            {
                "name": "m",
                "controller": RecordingController(return_value=0.0),
                "filtered_speed": 0.0,
                "motor": motors[0],
                "duty": 7.0,
            },
            {
                "name": "l",
                "controller": RecordingController(return_value=0.0),
                "filtered_speed": 0.0,
                "motor": motors[1],
                "duty": 8.0,
            },
            {
                "name": "r",
                "controller": RecordingController(return_value=0.0),
                "filtered_speed": 0.0,
                "motor": motors[2],
                "duty": 9.0,
            },
        ],
    }
    defaults.update(attrs)
    return make_minimal_transport_car(**defaults)


@pytest.mark.parametrize(
    "param_name",
    ("MASTER_ORBIT_RADIUS_SCALE", "ASSISTANT_ORBIT_RADIUS_SCALE"),
)
def test_orbit_radius_scale_params_exist_and_are_positive(param_name: str) -> None:
    """主辅车绕行半径倍率参数存在且保持正数语义."""
    value = float(getattr(real_params, param_name))

    assert value > 0.0


def test_runtime_config_params_stay_in_explicit_ranges() -> None:
    """运行时配置中能从代码直接确定范围的参数保持在合法区间."""

    assert int(real_params.TICK_MS) > 0
    assert int(real_params.RELIABLE_PACKET_SEND_DELAY_MS) >= 0
    assert int(real_params.RELIABLE_RESEND_INTERVAL_MS) >= 0
    assert 0 <= int(real_params.MASTER_SEARCH_HOOK_CONFIG_ID) <= 255
    assert 0 <= int(real_params.ASSISTANT_APPROACH_OBJECT_CONFIG_ID) <= 255
    assert 0.0 <= float(real_params.ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE) <= 1.0
    assert int(real_params.ASSISTANT_LOCAL_VISION_SYNC_RESEND_INTERVAL_MS) >= 0
    assert 0 < float(real_params.MAX_DUTY) <= 10000.0
    assert float(real_params.V_CMD_MAX) > 0.0
    assert float(real_params.TARGET_SPEED_MAX) > 0.0
    assert float(real_params.POS_MAX_SPEED) > 0.0
    assert float(real_params.POS_TOLERANCE) >= 0.0
    assert float(real_params.ANGLE_TOLERANCE) >= 0.0
    assert set(real_params.ACTIVE_WHEELS).issubset({"m", "l", "r"})
    assert 0.0 <= float(real_params.GYRO_LPF_ALPHA) <= 1.0
    assert float(real_params.GYRO_SCALE) > 0.0
    assert 0 <= int(real_params.GYRO_AXIS_Z) <= 5
    assert float(real_params.YAW_I_MAX) >= 0.0
    assert float(real_params.AUTO_OMEGA_MAX) >= 0.0
    assert float(real_params.HOLD_SPEED_EPS) >= 0.0


def test_transport_car_has_no_query_uart_public_api() -> None:
    """运行时对象不暴露通用查询回包串口入口."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(),
        uart8=CaptureUart(),
    )

    assert not hasattr(car, "get_query_uart")


def test_transport_car_stop_stops_ticker_zeroes_motors_and_writes_stop() -> None:
    """停止时关闭 ticker、清零电机并回写 stop."""
    ticker = DummyTicker()
    motors = [DummyMotor(), DummyMotor()]
    _transport_car, car = make_minimal_transport_car(
        ticker=ticker,
        wheel_states=[
            {"motor": motors[0]},
            {"motor": motors[1]},
        ],
        uart3=CaptureUart(),
    )

    car.stop()

    assert ticker.stop_count == 1
    assert motors[0].duties == [0]
    assert motors[1].duties == [0]
    assert car.uart3.messages == ["stop\r\n"]


def test_transport_car_builds_health_snapshot() -> None:
    """健康快照直接暴露底盘控制状态."""
    _transport_car, car = make_minimal_transport_car(
        boot_time_ms=200,
        last_exception_text="boom",
        command_lock=True,
        command_mode="locked",
    )
    car._now_ms = lambda: 650

    assert car.build_health_snapshot() == {
        "alive": 1,
        "uptime_ms": 450,
        "last_err": "boom",
        "lock": 1,
        "command_mode": "locked",
    }


def test_transport_car_builds_tick_snapshot() -> None:
    """周期快照继续反映最小统计值."""
    _transport_car, car = make_minimal_transport_car(
        tick_count=4,
        last_loop_dt_us=300,
        max_loop_dt_us=700,
        loop_dt_total_us=2000,
        loop_overrun_count=2,
    )

    assert car.build_tick_snapshot() == {
        "count": 4,
        "last_us": 300,
        "max_us": 700,
        "avg_us": 500,
        "overrun": 2,
    }


def test_transport_car_builds_imu_snapshot() -> None:
    """IMU 快照继续暴露最小姿态事实."""
    _transport_car, car = make_minimal_transport_car(
        imu_data=[1.0],
        heading_est=12.5,
        _yaw_rate=3.0,
        _last_gz_raw=9.0,
    )

    assert car.build_imu_snapshot() == {
        "ok": 1,
        "yaw_deg": 12.5,
        "yaw_rate_dps": 3.0,
        "gz_raw": 9.0,
    }


def test_transport_car_builds_encoder_snapshot() -> None:
    """编码器快照继续按轮输出原始值与滤波值."""
    _transport_car, car = make_minimal_transport_car(
        wheel_states=[
            {"name": "m", "raw_speed": 1.0, "filtered_speed": 0.5},
            {"name": "l", "raw_speed": 2.0, "filtered_speed": 1.5},
        ]
    )

    assert car.build_encoder_snapshot() == {
        "m_raw": 1.0,
        "m_filt": 0.5,
        "l_raw": 2.0,
        "l_filt": 1.5,
    }


def test_transport_car_builds_motor_snapshot() -> None:
    """电机快照继续暴露目标与占空比."""
    _transport_car, car = make_minimal_transport_car(
        wheel_states=[
            {"name": "m", "duty": 11.0},
            {"name": "l", "duty": 12.0},
        ],
        target_speeds={"m": 5.0, "l": 6.0},
    )

    assert car.build_motor_snapshot() == {
        "m_target": 5.0,
        "m_duty": 11.0,
        "l_target": 6.0,
        "l_duty": 12.0,
    }


def test_transport_car_set_velocity_target_updates_control_state() -> None:
    """结构化速度目标写入后, 底盘控制状态按当前行为保存速度量."""
    _transport_car, car = _make_control_car()
    car.set_velocity_target(1.0, -2.5, 0.5, has_omega=True)

    assert car.control_state == {"vx": 1.0, "vy": -2.5, "omega": 0.5}
    assert car.command_lock is False
    assert car.command_mode == "none"


def test_transport_car_velocity_target_keeps_current_speed_limit() -> None:
    """结构化速度目标沿用底盘轮速限幅边界."""
    transport_car, car = _make_control_car()
    limit = float(transport_car.TARGET_SPEED_MAX)

    car.set_velocity_target(limit * 10.0, 0.0, 0.0, has_omega=True)
    car._run_control(0.005)

    assert car.target_speeds == pytest.approx(
        {"m": -limit, "l": limit / 2.0, "r": limit / 2.0}
    )


def test_transport_car_translation_velocity_keeps_angle_target() -> None:
    """平移速度更新不清除当前角度目标."""
    _transport_car, car = _make_control_car(
        control_state={"vx": 0.0, "vy": 0.0, "angle": 45.0},
        command_lock=True,
        command_mode="locked",
    )

    car.set_velocity_target(12.0, -3.0, has_omega=False)

    assert car.control_state["angle"] == 45.0
    assert car.control_state["vx"] == 12.0
    assert car.control_state["vy"] == -3.0
    assert car.command_lock is True
    assert car.command_mode == "locked"


def test_transport_car_explicit_omega_clears_angle_target() -> None:
    """显式角速度更新清除当前角度目标."""
    _transport_car, car = _make_control_car(
        control_state={"vx": 0.0, "vy": 0.0, "angle": 45.0},
        command_lock=True,
        command_mode="locked",
    )

    car.set_velocity_target(12.0, -3.0, 6.0, has_omega=True)

    assert "angle" not in car.control_state
    assert car.control_state == {"vx": 12.0, "vy": -3.0, "omega": 6.0}
    assert car.command_lock is False
    assert car.command_mode == "none"


def test_transport_car_exposes_shared_orbit_entry_without_assistant_naming() -> None:
    """共享底盘公开统一绕行入口, 不暴露 assistant 专属命名."""
    transport_car, car = _make_control_car()
    signature = inspect.signature(transport_car.TransportCar.set_orbit_target)

    assert hasattr(car, "set_orbit_target")
    assert not hasattr(car, "set_assistant_orbit_target")
    assert tuple(signature.parameters) == ("self", "target_angle_deg", "radius_scale")


@pytest.mark.parametrize("radius_scale", (0.0, -1.0))
def test_transport_car_orbit_entry_rejects_non_positive_radius_scale(
    radius_scale: float,
) -> None:
    """统一绕行入口只接受正数半径倍率."""
    _transport_car, car = _make_control_car()

    with pytest.raises(ValueError):
        car.set_orbit_target(90.0, radius_scale)


def test_transport_car_set_orbit_target_enters_locked_shared_orbit_mode() -> None:
    """统一绕行入口只接收目标角度和半径倍率, 不暴露专用 x/y/omega 调参."""
    _transport_car, car = _make_control_car(
        control_state={"vx": 8.0, "vy": -3.0, "omega": 4.0, "x": 1.0, "y": 2.0}
    )

    car.set_orbit_target(90.0, 1.5)

    assert car.orbit_mode is True
    assert car.orbit_radius_scale == pytest.approx(1.5)
    assert car.command_lock is True
    assert car.command_mode == "locked"
    assert car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0, "angle": 90.0}


def test_transport_car_set_heading_target_keeps_translation_and_leaves_orbit_mode() -> None:
    """普通角度保持入口保留平移速度, 且不继续保留绕行模式."""
    _transport_car, car = _make_control_car(
        control_state={"vx": 8.0, "vy": -3.0, "omega": 4.0},
        orbit_mode=True,
        orbit_radius_scale=1.5,
    )

    car.set_heading_target(90.0)

    assert car.orbit_mode is False
    assert car.orbit_radius_scale == pytest.approx(_transport_car.MASTER_ORBIT_RADIUS_SCALE)
    assert car.command_lock is True
    assert car.command_mode == "locked"
    assert car.control_state == {"vx": 8.0, "vy": -3.0, "omega": 0.0, "angle": 90.0}


def test_runtime_config_accepts_separate_orbit_omega_limit() -> None:
    """运行时配置为绕行保留独立角速度限幅参数."""

    assert float(real_params.ORBIT_AUTO_OMEGA_MAX) >= 0.0


def test_transport_car_orbit_target_uses_orbit_specific_omega_limit() -> None:
    """绕行角速度限幅与普通角度保持限幅分离."""
    transport_car, car = _make_control_car(
        heading_est=0.0,
        _yaw_rate=0.0,
        yaw_pid=RecordingController(return_value=50.0),
    )

    car.control_state = {"vx": 0.0, "vy": 0.0, "omega": 0.0, "angle": 90.0}
    car.command_lock = True
    car.command_mode = "locked"
    non_orbit_omega = car._compute_omega_cmd(0.005)

    car.set_orbit_target(90.0, 1.0)
    orbit_omega = car._compute_omega_cmd(0.005)

    assert non_orbit_omega == pytest.approx(float(transport_car.AUTO_OMEGA_MAX))
    assert orbit_omega == pytest.approx(float(transport_car.ORBIT_AUTO_OMEGA_MAX))
    assert orbit_omega < non_orbit_omega


def test_transport_car_orbit_target_reuses_legacy_omega_chain_and_scales_radius() -> None:
    """统一绕行保持旧角速度目标行为, 线速度只按半径倍率解算."""
    _transport_car, car = _make_control_car(
        heading_est=10.0,
        yaw_pid=RecordingController(return_value=4.0),
    )
    applied = []

    def _capture(vx_cmd, vy_cmd, omega_cmd, dt_s):
        applied.append((vx_cmd, vy_cmd, omega_cmd, dt_s))

    car._apply_target_speeds = _capture

    car.set_orbit_target(40.0, 0.5)
    car._run_control(0.005)
    first_call = applied[-1]

    car.set_orbit_target(40.0, 2.0)
    car._run_control(0.005)
    second_call = applied[-1]

    assert first_call[2] == pytest.approx(float(_transport_car.ORBIT_AUTO_OMEGA_MAX))
    assert second_call[2] == pytest.approx(float(_transport_car.ORBIT_AUTO_OMEGA_MAX))
    assert first_call[1] == pytest.approx(0.0)
    assert second_call[1] == pytest.approx(0.0)
    assert first_call[0] == pytest.approx(
        -float(_transport_car.ORBIT_AUTO_OMEGA_MAX) * 0.5
    )
    assert second_call[0] == pytest.approx(
        -float(_transport_car.ORBIT_AUTO_OMEGA_MAX) * 2.0
    )
    assert abs(second_call[0]) > abs(first_call[0])


def test_transport_car_orbit_target_runs_through_existing_inverse_kinematics_chain() -> None:
    """统一绕行最终仍走现有底盘控制链和三轮逆运动学."""
    _transport_car, car = _make_control_car(
        heading_est=10.0,
        yaw_pid=RecordingController(return_value=3.0),
    )

    car.set_orbit_target(40.0, 2.0)
    car._run_control(0.005)

    expected_omega = float(_transport_car.ORBIT_AUTO_OMEGA_MAX)
    expected_vx = -expected_omega * 2.0
    expected_targets = {
        "m": (-2.0 / 3.0) * expected_vx + expected_omega / 3.0,
        "l": expected_vx / 3.0 + expected_omega / 3.0,
        "r": expected_vx / 3.0 + expected_omega / 3.0,
    }

    assert car.target_speeds == pytest.approx(expected_targets)
    for state, target in zip(
        car.wheel_states,
        (
            expected_targets["m"],
            expected_targets["l"],
            expected_targets["r"],
        ),
    ):
        assert state["controller"].update_calls == [(target, 0.0, 0.005)]


def test_transport_car_set_orbit_target_unlock_clears_mode_and_output() -> None:
    """统一绕行目标收敛后关闭锁定、清零输出并停止电机."""
    _transport_car, car = _make_control_car(heading_est=0.0, heading_target=0.0)

    car.set_orbit_target(90.0, 1.0)
    car.heading_target = 90.0
    car.heading_est = 90.0

    car._check_unlock()

    assert car.orbit_mode is False
    assert car.command_lock is False
    assert car.command_mode == "none"
    assert car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    for state in car.wheel_states:
        assert state["duty"] == 0.0
        assert state["motor"].duties == [0]


def test_transport_car_has_no_legacy_mode_entry() -> None:
    """共享底盘不再暴露旧模式入口."""
    _transport_car, car = _make_control_car()

    assert sorted(
        name for name in dir(car) if name.startswith("set_") and name.endswith("target")
    ) == ["set_heading_target", "set_orbit_target", "set_velocity_target"]


def test_transport_car_reset_control_state_keeps_reset_behavior() -> None:
    """结构化复位入口清空运动状态、姿态状态和锁定状态."""
    _transport_car, car = _make_control_car(
        control_state={"vx": 1.0, "vy": 2.0, "omega": 3.0, "angle": 45.0},
        command_lock=True,
        command_mode="locked",
        _pending_dx=1.0,
        _pending_dy=2.0,
        _pending_d_angle=3.0,
        _pending_lock=True,
        heading_est=12.0,
        heading_target=13.0,
        yaw_integral=7.0,
    )

    car.reset_control_state()

    assert car.odometry.reset_count == 1
    assert car.heading_est == 0.0
    assert car.heading_target == 0.0
    assert car.yaw_integral == 0.0
    assert (car.q_est.w, car.q_est.x, car.q_est.y, car.q_est.z) == (
        1.0,
        0.0,
        0.0,
        0.0,
    )
    assert car.last_yaw_rad == 0.0
    assert car.gyro_lpf.reset_calls == [(0.0,)]
    assert car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert car.command_lock is False
    assert car.command_mode == "none"
    assert car._pending_lock is None
    assert car._pending_dx is None
    assert car._pending_dy is None
    assert car._pending_d_angle is None


def test_transport_car_zero_motors_keeps_motor_clear_behavior() -> None:
    """结构化电机清零入口保持三轮占空比清零行为."""
    _transport_car, car = _make_control_car()

    car.zero_motors()

    for state in car.wheel_states:
        assert state["duty"] == 0.0
        assert state["motor"].duties == [0]
