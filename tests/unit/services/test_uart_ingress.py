"""UART ingress 服务单元测试."""

import sys
import types
from typing import Any, cast

import pytest


def _install_transport_import_stubs() -> None:
    """安装导入 CompatMixin 所需的最小板端桩模块."""

    machine = types.ModuleType("machine")

    class Pin:
        OUT = 0
        IN = 1
        PULL_UP_47K = 2

        def __init__(self, *_args, **_kwargs):
            self._value = 1

        def value(self):
            return self._value

        def toggle(self):
            return None

    class UART:
        def __init__(self, *_args, **_kwargs):
            self.messages = []

        def init(self, *_args, **_kwargs):
            return None

        def write(self, text):
            self.messages.append(text)

        def any(self):
            return 0

        def read(self, _size):
            return b""

    setattr(machine, "Pin", Pin)
    setattr(machine, "UART", UART)
    sys.modules.setdefault("machine", machine)

    seekfree = types.ModuleType("seekfree")

    class MOTOR_CONTROLLER:
        PWM_C30_DIR_C31 = 1
        PWM_D4_DIR_D5 = 2
        PWM_D6_DIR_D7 = 3

        def __init__(self, *_args, **_kwargs):
            return None

        def duty(self, _value):
            return None

    class IMU660RX:
        def get(self):
            return [0, 0, 0, 0, 0, 0]

    setattr(seekfree, "MOTOR_CONTROLLER", MOTOR_CONTROLLER)
    setattr(seekfree, "IMU660RX", IMU660RX)
    sys.modules.setdefault("seekfree", seekfree)

    smartcar = types.ModuleType("smartcar")
    setattr(
        smartcar,
        "encoder",
        lambda *_args, **_kwargs: types.SimpleNamespace(get=lambda: 0),
    )
    sys.modules.setdefault("smartcar", smartcar)


_install_transport_import_stubs()

from services.car.compat import CompatMixin
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


class ChunkedUART(FakeUART):
    """按请求大小切片返回缓冲内容的串口桩."""

    def __init__(self, payload: bytes):
        super().__init__()
        self._payload = payload
        self.read_sizes = []

    def any(self):
        return len(self._payload)

    def read(self, size):
        self.read_sizes.append(size)
        if not self._payload:
            return None
        chunk = self._payload[:size]
        self._payload = self._payload[size:]
        return chunk


class FalseyBuffer:
    """模拟空缓冲, 但禁止直接做字符串拼接."""

    def __bool__(self):
        return False

    def __add__(self, _other):
        raise AssertionError("empty buffer must not be concatenated")


class BufferMap(dict):
    """为缺失 key 返回 FalseyBuffer 的缓冲字典桩."""

    def get(self, key, default=None):
        if key not in self:
            return FalseyBuffer()
        return super().get(key, default)


class FakeQueryContext(FakeUART):
    """带最小 runtime 状态的 query 上下文桩."""

    def __init__(self):
        super().__init__()
        self._runtime = types.SimpleNamespace(
            last_exception_text="none",
            error_count=0,
            last_error_stage=None,
        )

    def reply(self, text):
        self.write(text)


class FakeRouter:
    """记录 query 调用的最小路由桩."""

    def __init__(self):
        self.queries = []

    def handle_query(self, token, ctx):
        self.queries.append((token, ctx))


class FailingQueryRouter:
    """处理 query 时抛异常的路由桩."""

    def __init__(self):
        self.queries = []

    def handle_query(self, token, ctx):
        self.queries.append((token, ctx))
        raise RuntimeError("query failed")


class FakeVisionCoordinator:
    """记录视觉吞包调用的最小协调器桩."""

    def __init__(self):
        self.calls = []

    def consume_uart_line(self, line, source, now_ms):
        self.calls.append((line, source, now_ms))
        return line.startswith("left=")


class LazyVisionProvider:
    """记录视觉协调器 provider 触发次数的桩."""

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.coordinator


def test_uart_ingress_routes_visual_query_and_command_lines_to_correct_subsystem() -> (
    None
):
    router = FakeRouter()
    coordinator = FakeVisionCoordinator()
    commands = []
    service = UartIngressService(
        router=router,
        ensure_query_handlers=lambda: None,
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

    assert coordinator.calls == [("left=100,top=20,right=140,bottom=90", "uart6", 1000)]
    assert router.queries == [("lock", {"source": "uart3"})]
    assert commands == [("log", "vx=1"), ("uart3", "vx=1"), ("uart6", "vy=2")]


def test_uart_ingress_defers_vision_provider_until_visual_uart6_traffic() -> None:
    router = FakeRouter()
    coordinator = FakeVisionCoordinator()
    provider = LazyVisionProvider(coordinator)
    commands = []
    service = UartIngressService(
        router=router,
        ensure_query_handlers=lambda: None,
        build_context=lambda source: {"source": source},
        apply_command=lambda line, source="uart6": commands.append((source, line)),
        command_log=lambda line: commands.append(("log", line)),
        emit_error=lambda message: commands.append("err:%s" % message),
        now_ms=lambda: 1000,
        get_vision_coordinator=provider,
    )

    assert provider.calls == 0

    service.handle_line("vx=1", source="uart3")
    service.handle_line("vy=2", source="uart6")

    assert provider.calls == 0

    service.handle_line("left=100,top=20,right=140,bottom=90", source="uart6")

    assert provider.calls == 1
    assert coordinator.calls == [("left=100,top=20,right=140,bottom=90", "uart6", 1000)]


def test_uart_ingress_polls_uart_and_keeps_source_buffers_isolated() -> None:
    router = FakeRouter()
    coordinator = FakeVisionCoordinator()
    commands = []
    errors = []
    service = UartIngressService(
        router=router,
        ensure_query_handlers=lambda: None,
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
        ensure_query_handlers=lambda: None,
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


def test_uart_ingress_reads_full_available_buffer_and_preserves_split_lines() -> None:
    router = FakeRouter()
    coordinator = FakeVisionCoordinator()
    errors = []
    service = UartIngressService(
        router=router,
        ensure_query_handlers=lambda: None,
        vision_coordinator=coordinator,
        build_context=lambda source: source,
        apply_command=lambda line, source="uart6": None,
        command_log=lambda line: None,
        emit_error=lambda message: errors.append(message),
        now_ms=lambda: 1000,
    )
    line = b"left=100,top=20,right=140,bottom=90\n"
    uart6 = ChunkedUART(line * 4)

    while uart6.any():
        service.poll_source(uart6, "uart6")

    assert coordinator.calls == [
        ("left=100,top=20,right=140,bottom=90", "uart6", 1000),
        ("left=100,top=20,right=140,bottom=90", "uart6", 1000),
        ("left=100,top=20,right=140,bottom=90", "uart6", 1000),
        ("left=100,top=20,right=140,bottom=90", "uart6", 1000),
    ]
    assert uart6.read_sizes == [len(line * 4)]
    assert errors == []


def test_uart_ingress_avoids_concatenating_missing_empty_buffer() -> None:
    router = FakeRouter()
    coordinator = FakeVisionCoordinator()
    errors = []
    service = UartIngressService(
        router=router,
        ensure_query_handlers=lambda: None,
        vision_coordinator=coordinator,
        build_context=lambda source: source,
        apply_command=lambda line, source="uart6": None,
        command_log=lambda line: None,
        emit_error=lambda message: errors.append(message),
        now_ms=lambda: 1000,
    )
    service._buffers = BufferMap()
    uart6 = FakeUART([b"left=100,top=20,right=140,bottom=90\n"])

    service.poll_source(uart6, "uart6")

    assert coordinator.calls == [("left=100,top=20,right=140,bottom=90", "uart6", 1000)]
    assert errors == []


def test_uart_ingress_query_failure_replies_with_minimal_error_response() -> None:
    router = FailingQueryRouter()
    coordinator = FakeVisionCoordinator()
    errors = []
    uart3 = FakeUART()
    service = UartIngressService(
        router=router,
        ensure_query_handlers=lambda: None,
        vision_coordinator=coordinator,
        build_context=lambda _source: uart3,
        apply_command=lambda line, source="uart6": None,
        command_log=lambda line: None,
        emit_error=lambda message: errors.append(message),
        now_ms=lambda: 1000,
    )

    service.handle_line("?health", source="uart3")

    assert router.queries == [("health", uart3)]
    assert errors == ["query failed"]
    assert uart3.messages == ["?health=error:RuntimeError\r\n"]


def test_uart_ingress_query_failure_on_runtime_context_updates_state_without_logging() -> (
    None
):
    router = FailingQueryRouter()
    coordinator = FakeVisionCoordinator()
    errors = []
    ctx = FakeQueryContext()
    service = UartIngressService(
        router=router,
        ensure_query_handlers=lambda: None,
        vision_coordinator=coordinator,
        build_context=lambda _source: ctx,
        apply_command=lambda line, source="uart6": None,
        command_log=lambda line: None,
        emit_error=lambda message: errors.append(message),
        now_ms=lambda: 1000,
    )

    service.handle_line("?health", source="uart3")

    assert errors == []
    assert ctx._runtime.last_exception_text == "query failed"
    assert ctx._runtime.error_count == 1
    assert ctx._runtime.last_error_stage == "query"
    assert ctx.messages == ["?health=error:RuntimeError\r\n"]


def test_uart_ingress_accepts_minimal_command_runtime_query_loader() -> None:
    from services.runtime.minimal_command_runtime import MinimalCommandRuntime

    router = FakeRouter()
    coordinator = FakeVisionCoordinator()
    calls = []
    handlers_module = types.SimpleNamespace(
        QUERY_HANDLER_START_INDEX=18,
        load_query_handlers=lambda: calls.append("query"),
        load_command_handlers=lambda: calls.append("command"),
    )
    runtime = MinimalCommandRuntime(
        import_runtime_module=lambda _name: handlers_module,
        drop_stale_handler_modules=lambda start_index, stop_index=None: calls.append(
            (start_index, stop_index)
        ),
    )
    service = UartIngressService(
        router=router,
        ensure_query_handlers=runtime.ensure_query_handlers,
        vision_coordinator=coordinator,
        build_context=lambda source: {"source": source},
        apply_command=lambda line, source="uart6": None,
        command_log=lambda line: None,
        emit_error=lambda message: None,
        now_ms=lambda: 1000,
    )

    service.handle_line("?health", source="uart3")

    assert calls == [(18, None), "query"]


def test_compat_mixin_ensure_uart_ingress_emits_memory_trace_before_and_after_init() -> (
    None
):
    class FakeCompatCar(CompatMixin):
        """测试 CompatMixin 懒初始化埋点的最小宿主."""

    trace_calls = []
    car = cast(Any, FakeCompatCar())
    car.uart_ingress = None
    car.uart3 = FakeUART()
    car.uart6 = FakeUART()
    car._router = FakeRouter()
    car._ensure_query_handlers = lambda: None
    car._build_handler_context = lambda source="uart6": {"source": source}
    car.apply_command = lambda line, source="uart6": None
    car._log_uart_command = lambda line: None
    car._emit_error_log = lambda message: None
    car._now_ms = lambda: 1000
    car._ensure_vision_coordinator = lambda: None
    car.trace_runtime_mem = lambda stage, uart=None: trace_calls.append((stage, uart))

    ingress = car._ensure_uart_ingress()

    assert isinstance(ingress, UartIngressService)
    assert ingress is car.uart_ingress
    assert [stage for stage, _uart in trace_calls] == [
        "before_uart_ingress_init",
        "after_uart_ingress_init",
    ]
    assert all(uart is car.uart3 for _stage, uart in trace_calls)
