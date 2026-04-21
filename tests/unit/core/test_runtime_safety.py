"""`TransportCar` 安全边界测试."""

from tests.unit.core.runtime_support import (
    CaptureUart,
    DummyMotor,
    DummyPid,
    DummyTicker,
    import_transport_car_module,
    make_minimal_transport_car,
)


def test_transport_car_step_stops_immediately_when_estop_switch_changes() -> None:
    """急停开关变化时立即停机并返回失败."""
    _transport_car, car = make_minimal_transport_car(
        pit_flag=False,
        _boot_step_logged=True,
        switch2_init=1,
    )
    car._process_uart = lambda: None
    car.switch2 = type("Switch", (), {"value": lambda self: 0})()
    stopped = []
    car.stop = lambda: stopped.append("stop")

    assert car.step() is False
    assert stopped == ["stop"]


def test_transport_car_stop_ignores_missing_ticker_but_zeroes_motors() -> None:
    """停车在没有 ticker 时也继续清零输出."""
    motors = [DummyMotor(), DummyMotor()]
    _transport_car, car = make_minimal_transport_car(
        ticker=None,
        wheel_states=[
            {"motor": motors[0]},
            {"motor": motors[1]},
        ],
        uart3=CaptureUart(),
    )

    car.stop()

    assert motors[0].duties == [0]
    assert motors[1].duties == [0]
    assert car.uart3.messages == ["stop\r\n"]


def test_transport_car_diagnostic_mode_uses_safe_null_devices() -> None:
    """诊断模式构造时继续使用安全空设备而非真实执行器."""
    transport_car = import_transport_car_module()
    car = transport_car.TransportCar(diagnostic_mode=True)

    car.motors["m"].duty(123)

    assert car.encoders["m"].get() == 0.0
    assert car.motors["m"].last_duty == 123
    assert car.imu.get() == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
