"""`TransportCar` 串口输入与路由测试."""

from tests.unit.core.runtime_support import CaptureUart, make_minimal_transport_car


class RouterSpy:
    """记录非查询路由不应被查询路径调用的最小桩."""

    pass


def test_transport_car_handle_uart3_line_does_not_echo_non_query_command() -> None:
    """非查询命令继续只执行, 不额外回写提示文本."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(),
        _router=object(),
    )
    calls = []
    car.apply_command = lambda line: calls.append(line)

    car._handle_uart_line("rear=1", source="uart3")

    assert calls == ["rear=1"]
    assert car.uart3.messages == []


def test_transport_car_handle_uart3_line_ignores_question_prefixed_input() -> None:
    """问号开头输入不进入查询路由, 也不产生回写."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(),
        _router=RouterSpy(),
    )
    calls = []
    car.apply_command = lambda line: calls.append(line)

    car._handle_uart_line("?health", source="uart3")

    assert calls == []
    assert car.uart3.messages == []


def test_transport_car_process_uart_splits_lines_keeps_residue_and_skips_empty_line() -> None:
    """多行输入按行处理, 空行忽略, 无换行残留保留在缓冲区."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(incoming=b"?health\nrear=1\n\npartial"),
        _router=RouterSpy(),
        rx_buf3="",
    )
    commands = []
    car.apply_command = lambda line: commands.append(line)

    car._process_uart()

    assert commands == ["rear=1"]
    assert car.uart3.messages == []
    assert car.rx_buf3 == "partial"


def test_transport_car_process_uart_merges_previous_buffer_before_newline_split() -> None:
    """已有残留内容会先和新输入拼成完整一行."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(incoming=b"fix\n"),
        _router=RouterSpy(),
        rx_buf3="pre",
    )
    commands = []
    car.apply_command = lambda line: commands.append(line)

    car._process_uart()

    assert commands == ["prefix"]
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
        _router=object(),
        last_cmd={"vx": 0.0, "vy": 0.0, "omega": 0.0},
    )
    finalized = []
    car._finalize_route = lambda dispatched: finalized.append(dispatched)

    car._handle_uart_line("v,1.0,-2.5,0.5", source="uart3")

    assert car.last_cmd == {"vx": 1.0, "vy": -2.5, "omega": 0.5}
    assert finalized == [{"vx", "vy", "omega"}]


def test_transport_car_handle_uart3_line_rejects_key_value_velocity_text() -> None:
    """共享底盘串口入口不接受键值速度字段."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(),
        _router=object(),
        last_cmd={"vx": 0.0, "vy": 0.0, "omega": 0.0},
    )
    calls = []
    car.apply_command = lambda line: calls.append(line)

    car._handle_uart_line("vx=1.0,vy=2.0,omega=0.5", source="uart3")

    assert calls == []
    assert car.last_cmd == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
