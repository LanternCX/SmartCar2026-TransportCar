"""`TransportCar` 串口输入与路由测试."""

from tests.unit.core.runtime_support import CaptureUart, make_minimal_transport_car


class RouterSpy:
    """记录查询路由的最小桩."""

    def __init__(self) -> None:
        self.queries = []

    def handle_query(self, token, car, source):
        self.queries.append((token, car, source))


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


def test_transport_car_handle_uart3_line_routes_query_to_router() -> None:
    """查询行继续交给 query 路由处理."""
    router = RouterSpy()
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(),
        _router=router,
    )

    car._handle_uart_line("?health", source="uart3")

    assert router.queries == [("health", car, "uart3")]


def test_transport_car_process_uart_splits_lines_keeps_residue_and_skips_empty_line() -> None:
    """多行输入按行处理, 空行忽略, 无换行残留保留在缓冲区."""
    router = RouterSpy()
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(incoming=b"?health\nrear=1\n\npartial"),
        _router=router,
        rx_buf3="",
    )
    commands = []
    car.apply_command = lambda line: commands.append(line)

    car._process_uart()

    assert len(router.queries) == 1
    assert router.queries[0][0] == "health"
    assert router.queries[0][1] is car
    assert router.queries[0][2] == "uart3"
    assert commands == ["rear=1"]
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
