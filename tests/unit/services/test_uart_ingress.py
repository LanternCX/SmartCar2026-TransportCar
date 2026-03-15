"""UART ingress 服务单元测试."""

import pytest

from services.runtime.uart_ingress import UartIngressService


pytestmark = pytest.mark.unit


class FakeUART:
    """可注入读缓冲和记录输出的串口桩."""

    def __init__(self, payloads=None):
        self.payloads = list(payloads or [])
        self.messages = []

    def any(self):
        if not self.payloads:
            return 0
        return len(self.payloads[0])

    def read(self, _size):
        if not self.payloads:
            return None
        return self.payloads.pop(0)

    def write(self, text):
        self.messages.append(text)


class FakeRouter:
    """记录 query 调用的最小路由桩."""

    def __init__(self):
        self.queries = []

    def handle_query(self, token, ctx):
        self.queries.append((token, ctx))


class FakeVisionCoordinator:
    """记录视觉吞包调用的最小协调器桩."""

    def __init__(self):
        self.calls = []

    def consume_uart_line(self, line, source, now_ms):
        self.calls.append((line, source, now_ms))
        return line.startswith("left=")


def test_uart_ingress_routes_visual_query_and_command_lines_to_correct_subsystem() -> (
    None
):
    router = FakeRouter()
    coordinator = FakeVisionCoordinator()
    commands = []
    service = UartIngressService(
        router=router,
        vision_coordinator=coordinator,
        build_context=lambda source: {"source": source},
        apply_command=lambda line, source="uart6": commands.append((source, line)),
        command_log=lambda line: commands.append(("log", line)),
        emit_error=lambda message: commands.append("err:%s" % message),
        now_ms=lambda: 1000,
    )

    service.handle_line("left=100,top=20,right=140,bottom=90", source="uart6")
    service.handle_line("?lock", source="uart3")
    service.handle_line("vx=1", source="uart3")
    service.handle_line("vy=2", source="uart6")

    assert coordinator.calls == [
        ("left=100,top=20,right=140,bottom=90", "uart6", 1000),
        ("vy=2", "uart6", 1000),
    ]
    assert router.queries == [("lock", {"source": "uart3"})]
    assert commands == [("log", "vx=1"), ("uart3", "vx=1"), ("uart6", "vy=2")]


def test_uart_ingress_polls_uart_and_keeps_source_buffers_isolated() -> None:
    router = FakeRouter()
    coordinator = FakeVisionCoordinator()
    commands = []
    errors = []
    service = UartIngressService(
        router=router,
        vision_coordinator=coordinator,
        build_context=lambda source: source,
        apply_command=lambda line, source="uart6": commands.append((source, line)),
        command_log=lambda line: commands.append(("log", line)),
        emit_error=lambda message: errors.append(message),
        now_ms=lambda: 1000,
    )
    uart3 = FakeUART([b"?lock\n", b"vx=1\n"])
    uart6 = FakeUART([b"left=100,top=20,", b"right=140,bottom=90\n"])

    service.poll_source(uart3, "uart3")
    service.poll_source(uart3, "uart3")
    service.poll_source(uart6, "uart6")
    service.poll_source(uart6, "uart6")

    assert router.queries == [("lock", "uart3")]
    assert commands == [("log", "vx=1"), ("uart3", "vx=1")]
    assert coordinator.calls == [("left=100,top=20,right=140,bottom=90", "uart6", 1000)]
    assert errors == []


def test_uart_ingress_keeps_multi_detection_frame_batch_lines_together() -> None:
    router = FakeRouter()
    coordinator = FakeVisionCoordinator()
    service = UartIngressService(
        router=router,
        vision_coordinator=coordinator,
        build_context=lambda source: source,
        apply_command=lambda line, source="uart6": None,
        command_log=lambda line: None,
        emit_error=lambda message: None,
        now_ms=lambda: 1000,
    )
    uart6 = FakeUART(
        [
            (
                b"camera_id=cam_b,frame_id=7,category=obstacle,left=10,top=20,right=50,bottom=80\n"
                b"camera_id=cam_b,frame_id=7,frame_end=1\n"
            )
        ]
    )

    service.poll_source(uart6, "uart6")

    assert coordinator.calls == [
        (
            "camera_id=cam_b,frame_id=7,category=obstacle,left=10,top=20,right=50,bottom=80",
            "uart6",
            1000,
        ),
        ("camera_id=cam_b,frame_id=7,frame_end=1", "uart6", 1000),
    ]
