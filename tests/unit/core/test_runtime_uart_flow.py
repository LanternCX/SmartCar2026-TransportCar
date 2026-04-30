"""`TransportCar` 串口短包输入测试."""

import pytest

from tests.unit.core.runtime_support import CaptureUart, make_minimal_transport_car


def test_transport_car_handle_uart3_line_rejects_non_short_packet_text() -> None:
    """非短包文本不改变底盘控制状态."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(),
        control_state={"vx": 0.0, "vy": 0.0, "omega": 0.0},
    )
    car._handle_uart_line("rear=1", source="uart3")

    assert car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert car.uart3.messages == []


def test_transport_car_handle_uart3_line_ignores_question_prefixed_input() -> None:
    """问号开头输入不属于正式短包, 也不产生回写."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(),
    )
    car._handle_uart_line("?health", source="uart3")

    assert car.uart3.messages == []


def test_transport_car_process_uart_splits_lines_keeps_residue_and_skips_empty_line() -> None:
    """多行输入按行处理, 空行忽略, 无换行残留保留在缓冲区."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(incoming=b"?health\nv,1.0,2.0,0.5\nrear=1\n\npartial"),
        rx_buf3="",
        control_state={"vx": 0.0, "vy": 0.0, "omega": 0.0},
        command_lock=False,
        command_mode="none",
        _pending_dx=None,
        _pending_dy=None,
        _pending_d_angle=None,
    )
    car._process_uart()

    assert car.control_state == {"vx": 1.0, "vy": 2.0, "omega": 0.5}
    assert car.uart3.messages == []
    assert car.rx_buf3 == "partial"


def test_transport_car_process_uart_merges_previous_buffer_before_newline_split() -> None:
    """已有残留内容会先和新输入拼成完整一行."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(incoming=b"1.0,2.0,0.5\n"),
        rx_buf3="v,",
        control_state={"vx": 0.0, "vy": 0.0, "omega": 0.0},
        command_lock=False,
        command_mode="none",
        _pending_dx=None,
        _pending_dy=None,
        _pending_d_angle=None,
    )
    car._process_uart()

    assert car.control_state == {"vx": 1.0, "vy": 2.0, "omega": 0.5}
    assert car.rx_buf3 == ""


def test_transport_car_process_uart_keeps_err_output() -> None:
    """UART 读取异常时继续保留错误回写."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(incoming=b"boom\n", read_error=RuntimeError("boom")),
        uart8=CaptureUart(),
        uart6=CaptureUart(),
        rx_buf3="",
        rx_buf6="",
        last_exception_text="none",
    )

    car._process_uart()

    assert car.last_exception_text == "boom"
    assert len(car.uart3.messages) == 1
    assert car.uart3.messages[0].startswith("ERR ")
    assert "boom" in car.uart3.messages[0]


def test_transport_car_handle_uart3_line_accepts_v_short_packet() -> None:
    """共享底盘串口入口接受速度短包并结构化写入速度."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(),
        control_state={"vx": 0.0, "vy": 0.0, "omega": 0.0},
        command_lock=False,
        command_mode="none",
        _pending_dx=None,
        _pending_dy=None,
        _pending_d_angle=None,
    )
    velocity_packets = []
    original_handle_velocity_packet = car.handle_velocity_packet
    car.handle_velocity_packet = lambda *args, **kwargs: (
        velocity_packets.append((args, kwargs)),
        original_handle_velocity_packet(*args, **kwargs),
    )
    car._handle_uart_line("v,1.0,-2.5,0.5", source="uart3")

    assert velocity_packets == [
        ((1.0, -2.5, 0.5), {"source": "uart3", "has_omega": True})
    ]
    assert car.control_state == {"vx": 1.0, "vy": -2.5, "omega": 0.5}


def test_transport_car_handle_uart3_line_rejects_invalid_and_unused_short_packets() -> None:
    """非法短包和未消费短包不改变共享底盘控制状态."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(),
        control_state={"vx": 3.0, "vy": -4.0, "omega": 0.7},
    )
    for line in (
        "v,1.0",
        "v,1.0,nope,0.5",
        "x,1,2,3",
        "s,12,3,1,0",
        "a,12",
        "o,12,1.0,-0.5,3.0",
        "r,12,2,-1",
        "?health",
        "vx=1.0,vy=2.0,omega=0.5",
    ):
        car._handle_uart_line(line, source="uart3")

    assert car.control_state == {"vx": 3.0, "vy": -4.0, "omega": 0.7}


def test_transport_car_handle_uart3_line_ignores_non_short_packet_text() -> None:
    """非短包文本不会改变底盘控制状态."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(),
        control_state={"vx": 0.0, "vy": 0.0, "omega": 0.0},
    )

    car._handle_uart_line("diag=1", source="uart3")

    assert car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
