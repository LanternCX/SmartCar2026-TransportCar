"""`TransportCar` 对外行为测试."""

import pytest

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
        "rear_only_mode": False,
        "last_rear_mode": False,
        "_pending_dx": None,
        "_pending_dy": None,
        "_pending_d_angle": None,
        "_pending_lock": None,
        "_rear_mode_changed": False,
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
        rear_only_mode=True,
        command_mode="locked",
    )
    car._now_ms = lambda: 650

    assert car.build_health_snapshot() == {
        "alive": 1,
        "uptime_ms": 450,
        "last_err": "boom",
        "lock": 1,
        "rear": 1,
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
    """电机快照继续暴露目标、占空比与后轮模式状态."""
    _transport_car, car = make_minimal_transport_car(
        wheel_states=[
            {"name": "m", "duty": 11.0},
            {"name": "l", "duty": 12.0},
        ],
        target_speeds={"m": 5.0, "l": 6.0},
        rear_only_mode=True,
    )

    assert car.build_motor_snapshot() == {
        "m_target": 5.0,
        "m_duty": 11.0,
        "l_target": 6.0,
        "l_duty": 12.0,
        "rear": 1,
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
