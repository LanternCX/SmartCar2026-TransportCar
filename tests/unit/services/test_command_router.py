"""services.command_router 的单元测试."""

import pytest

from services.command_router import CommandRouter


pytestmark = pytest.mark.unit


class FakeUART:
    """收集查询输出,用于断言."""

    def __init__(self):
        self.messages = []

    def write(self, text):
        self.messages.append(text)


class FakeContext:
    """路由上下文桩对象."""

    _query_response_uart: object
    _query_source: str

    def __init__(self):
        self.calls = []
        self.dispatched = None
        self.uart3 = FakeUART()
        self.uart6 = FakeUART()

    def _finalize_route(self, dispatched_keys):
        self.dispatched = dispatched_keys


def test_route_dispatches_registered_commands_and_finalizes():
    router = CommandRouter()
    ctx = FakeContext()

    @router.command("vx")
    def cmd_vx(local_ctx, value):
        local_ctx.calls.append(("vx", value))

    @router.command("vy")
    def cmd_vy(local_ctx, value):
        local_ctx.calls.append(("vy", value))

    ok = router.route("vx=1,vy=2", ctx)
    assert ok is True
    assert ctx.calls == [("vx", 1.0), ("vy", 2.0)]
    assert ctx.dispatched == {"vx", "vy"}


def test_route_handles_print_as_raw_string():
    router = CommandRouter()
    ctx = FakeContext()

    @router.command("print", value_type="raw")
    def cmd_print(local_ctx, value):
        local_ctx.calls.append(("print", value))

    ok = router.route("print=hello world", ctx)
    assert ok is True
    assert ctx.calls == [("print", "hello world")]


def test_route_does_not_force_print_to_raw_without_metadata() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    @router.command("print")
    def cmd_print(local_ctx, value):
        local_ctx.calls.append(("print", value))

    ok = router.route("print=hello world", ctx)

    assert ok is False
    assert ctx.calls == []


def test_route_can_dispatch_raw_string_commands() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    @router.command("log_level", value_type="raw")
    def cmd_log_level(local_ctx, value):
        local_ctx.calls.append(("log_level", value))

    ok = router.route("log_level=debug", ctx)

    assert ok is True
    assert ctx.calls == [("log_level", "debug")]


def test_route_can_dispatch_module_lists_as_raw_string() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    @router.command("log_modules", value_type="raw")
    def cmd_log_modules(local_ctx, value):
        local_ctx.calls.append(("log_modules", value))

    ok = router.route("log_modules=vision|control.yaw", ctx)

    assert ok is True
    assert ctx.calls == [("log_modules", "vision|control.yaw")]


def test_route_keeps_float_parsing_for_default_commands() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    @router.command("vx")
    def cmd_vx(local_ctx, value):
        local_ctx.calls.append(("vx", value))

    ok = router.route("vx=1.5", ctx)

    assert ok is True
    assert ctx.calls == [("vx", 1.5)]


def test_route_ignores_unknown_and_invalid_values():
    router = CommandRouter()
    ctx = FakeContext()

    @router.command("vx")
    def cmd_vx(local_ctx, value):
        local_ctx.calls.append(("vx", value))

    ok = router.route("vx=bad,unknown=1", ctx)
    assert ok is False
    assert ctx.calls == []


def test_route_supports_bare_reset():
    router = CommandRouter()
    ctx = FakeContext()

    @router.command("reset")
    def cmd_reset(local_ctx, value):
        local_ctx.calls.append(("reset", value))

    ok = router.route("reset", ctx)
    assert ok is True
    assert ctx.calls == [("reset", True)]
    assert ctx.dispatched == {"reset"}


def test_route_supports_uppercase_bare_reset() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    @router.command("reset")
    def cmd_reset(local_ctx, value):
        local_ctx.calls.append(("reset", value))

    ok = router.route(" RESET ", ctx)

    assert ok is True
    assert ctx.calls == [("reset", True)]
    assert ctx.dispatched == {"reset"}


def test_handle_query_known_token():
    router = CommandRouter()
    ctx = FakeContext()

    @router.query("pos")
    def query_pos(local_ctx):
        local_ctx.calls.append(("query", "pos"))

    ok = router.handle_query("pos", ctx)
    assert ok is True
    assert ctx.calls == [("query", "pos")]


def test_handle_query_normalizes_registered_key() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    @router.query(" Health ")
    def query_health(local_ctx):
        local_ctx.calls.append(("query", "health"))

    ok = router.handle_query("health", ctx)

    assert ok is True
    assert ctx.calls == [("query", "health")]


def test_handle_query_passes_source_uart_to_context() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    @router.query("health")
    def query_health(local_ctx):
        local_ctx.calls.append(local_ctx._query_response_uart)

    ok = router.handle_query("health", ctx, source="uart3")

    assert ok is True
    assert ctx.calls == [ctx.uart3]


def test_handle_query_restores_temporary_context_attributes() -> None:
    router = CommandRouter()
    ctx = FakeContext()
    previous_uart = object()
    ctx._query_response_uart = previous_uart
    ctx._query_source = "uart9"

    @router.query("health")
    def query_health(local_ctx):
        local_ctx.calls.append(
            (local_ctx._query_response_uart, local_ctx._query_source)
        )

    ok = router.handle_query("health", ctx, source="uart3")

    assert ok is True
    assert ctx.calls == [(ctx.uart3, "uart3")]
    assert ctx._query_response_uart is previous_uart
    assert ctx._query_source == "uart9"


def test_handle_query_removes_temporary_context_attributes_when_absent() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    @router.query("health")
    def query_health(local_ctx):
        local_ctx.calls.append(
            (local_ctx._query_response_uart, local_ctx._query_source)
        )

    ok = router.handle_query("health", ctx, source="uart3")

    assert ok is True
    assert ctx.calls == [(ctx.uart3, "uart3")]
    assert not hasattr(ctx, "_query_response_uart")
    assert not hasattr(ctx, "_query_source")


def test_handle_query_unknown_token_writes_unknown_response_to_source_uart() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    ok = router.handle_query("missing", ctx, source="uart3")

    assert ok is False
    assert ctx.uart3.messages == ["?unknown=missing\r\n"]
    assert ctx.uart6.messages == []


def test_handle_query_unknown_token_writes_unknown_response():
    router = CommandRouter()
    ctx = FakeContext()
    ok = router.handle_query("missing", ctx)
    assert ok is False
    assert ctx.uart6.messages == ["?unknown=missing\r\n"]
