"""`TransportCar` 安全边界测试."""

from tests.unit.core.runtime_support import (
    CaptureUart,
    DummyMotor,
    DummyPid,
    DummyTicker,
    import_transport_car_module,
    make_minimal_transport_car,
)


def test_transport_car_unlock_completion_does_not_emit_prompt_text() -> None:
    """锁定完成后继续只回收状态, 不额外输出提示文本."""
    _transport_car, car = make_minimal_transport_car(
        command_lock=True,
        command_mode="locked",
        last_cmd={},
        heading_est=0.0,
        rear_only_mode=True,
        uart3=CaptureUart(),
        wheel_states=[{"motor": DummyMotor(), "duty": 1.0}],
        yaw_pid=DummyPid(),
        yaw_integral=1.0,
    )

    car._check_unlock()

    assert car.command_lock is False
    assert car.rear_only_mode is False
    assert car.uart3.messages == []


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


def test_transport_car_handle_tick_counts_overrun_when_cycle_exceeds_tick_budget() -> None:
    """控制周期超预算时累计 overrun 统计."""
    _transport_car, car = make_minimal_transport_car(
        tick_count=0,
        last_time_us=1000,
        last_loop_dt_us=0,
        max_loop_dt_us=0,
        loop_dt_total_us=0,
        loop_overrun_count=0,
        led=type("Led", (), {"toggle": lambda self: None})(),
    )
    car._now_us = lambda: 8000
    car._ticks_diff_us = lambda current, previous: current - previous
    car._update_wheel_speeds = lambda: None
    car._update_attitude = lambda _dt_s: None
    car._run_control = lambda _dt_s: None

    car._handle_tick()

    assert car.tick_count == 1
    assert car.last_loop_dt_us == 7000
    assert car.max_loop_dt_us == 7000
    assert car.loop_dt_total_us == 7000
    assert car.loop_overrun_count == 1


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
