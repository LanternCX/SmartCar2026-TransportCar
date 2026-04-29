"""`TransportCar` 对外行为测试."""

from tests.unit.core.runtime_support import (
    CaptureUart,
    DummyMotor,
    DummyTicker,
    make_minimal_transport_car,
)


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
    """健康快照继续只暴露最小健康字段."""
    transport_car, car = make_minimal_transport_car(
        boot_time_ms=200,
        last_exception_text="boom",
    )
    transport_car.build_command_health_fields = lambda _car: {"mode": "ready"}
    car._now_ms = lambda: 650

    assert car.build_health_snapshot() == {
        "alive": 1,
        "uptime_ms": 450,
        "last_err": "boom",
        "mode": "ready",
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
