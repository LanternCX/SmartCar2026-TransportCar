"""命令路由器的单元测试."""

import pytest

from services.commanding.router import CommandRouter
from services.commanding.session import CommandSession


pytestmark = pytest.mark.unit


class FakeUART:
    """收集查询输出,用于断言."""

    def __init__(self):
        self.messages = []

    def write(self, text):
        self.messages.append(text)


class FakeContext:
    """路由上下文桩对象."""

    def __init__(self):
        self.calls = []
        self.dispatched = None
        self.uart3 = FakeUART()
        self.uart6 = FakeUART()
        self.reply_uart = self.uart6

    def _finalize_route(self, dispatched_keys):
        self.dispatched = dispatched_keys

    def finalize_route(self, dispatched_keys):
        self.dispatched = dispatched_keys

    def reply(self, text):
        self.reply_uart.write(text)


class FakeExplicitContext:
    """显式 handler 上下文桩对象."""

    def __init__(self):
        self.calls = []
        self.dispatched = None
        self.reply_uart = FakeUART()
        self.uart3 = FakeUART()
        self.uart6 = FakeUART()
        self.session = CommandSession()
        self.finalize_calls = []
        self.logger_manager = None
        self.odometry = type("FakeOdometry", (), {"x": 0.0, "y": 0.0})()

    def get_diagnostics_facade(self):
        class _Facade:
            def __init__(self, outer_ctx):
                self._ctx = outer_ctx

            def build_lock_snapshot(self):
                return {"locked": 1 if self._ctx.session.command_lock else 0}

        return _Facade(self)

    def finalize_route(self, dispatched_keys):
        self.finalize_calls.append(dispatched_keys)
        self.dispatched = dispatched_keys

    def reply(self, text):
        self.reply_uart.write(text)


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


def test_registered_query_tokens_exposes_sorted_public_view() -> None:
    router = CommandRouter()

    @router.query("vision", " Health ")
    def query_any(_ctx):
        return None

    assert router.registered_query_tokens() == ("health", "vision")


def test_handle_query_without_explicit_reply_uart_defaults_to_uart6() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    @router.query("lock")
    def query_lock(local_ctx):
        local_ctx.reply("?lock=0\r\n")

    ok = router.handle_query("lock", ctx)

    assert ok is True
    assert ctx.uart6.messages == ["?lock=0\r\n"]
    assert ctx.uart3.messages == []


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
    from services.commanding.router import CommandRouter as ExplicitCommandRouter

    router = ExplicitCommandRouter()
    ctx = FakeExplicitContext()
    ctx.reply_uart = ctx.uart3

    @router.query("health")
    def query_health(local_ctx):
        local_ctx.calls.append(local_ctx.reply_uart)

    ok = router.handle_query("health", ctx)

    assert ok is True
    assert ctx.calls == [ctx.uart3]


def test_handle_query_uses_explicit_context_without_temporary_attributes() -> None:
    from services.commanding.router import CommandRouter as ExplicitCommandRouter

    router = ExplicitCommandRouter()
    ctx = FakeExplicitContext()
    ctx.reply_uart = ctx.uart3

    @router.query("health")
    def query_health(local_ctx):
        local_ctx.calls.append(local_ctx.reply_uart)

    ok = router.handle_query("health", ctx)

    assert ok is True
    assert ctx.calls == [ctx.uart3]
    assert not hasattr(ctx, "_query_response_uart")
    assert not hasattr(ctx, "_query_source")


def test_handle_query_unknown_token_writes_unknown_response_to_explicit_reply_uart() -> (
    None
):
    from services.commanding.router import CommandRouter as ExplicitCommandRouter

    router = ExplicitCommandRouter()
    ctx = FakeExplicitContext()
    ctx.reply_uart = ctx.uart3

    ok = router.handle_query("missing", ctx)

    assert ok is False
    assert ctx.uart3.messages == ["?unknown=missing\r\n"]
    assert ctx.reply_uart.messages == ["?unknown=missing\r\n"]
    assert not hasattr(ctx, "_query_response_uart")
    assert not hasattr(ctx, "_query_source")


def test_handle_query_unknown_token_writes_unknown_response() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    ok = router.handle_query("missing", ctx)

    assert ok is False
    assert ctx.uart6.messages == ["?unknown=missing\r\n"]


def test_relative_command_handlers_use_session_api_instead_of_private_fields() -> None:
    from services.commanding.handlers import cmd_d_angle, cmd_dx, cmd_dy

    ctx = FakeExplicitContext()

    cmd_dx.handle(ctx, 0.1)
    cmd_dy.handle(ctx, -0.2)
    cmd_d_angle.handle(ctx, 15.0)

    assert ctx.session.pending_dx == 0.1
    assert ctx.session.pending_dy == -0.2
    assert ctx.session.pending_d_angle == 15.0
    assert not hasattr(ctx, "_pending_dx")
    assert not hasattr(ctx, "_pending_dy")
    assert not hasattr(ctx, "_pending_d_angle")


def test_query_handlers_do_not_depend_on_transport_private_state() -> None:
    from services.commanding.handlers import query_lock

    ctx = FakeExplicitContext()
    ctx.session.command_lock = True

    query_lock.handle(ctx)

    assert ctx.reply_uart.messages == ["?lock=1\r\n"]
    assert not hasattr(ctx, "_query_response_uart")
    assert not hasattr(ctx, "_query_source")


def test_explicit_route_uses_context_finalize_without_runtime_private_protocol() -> (
    None
):
    from services.commanding.router import CommandRouter as ExplicitCommandRouter

    router = ExplicitCommandRouter()
    ctx = FakeExplicitContext()

    @router.command("vx")
    def cmd_vx(local_ctx, value):
        local_ctx.calls.append(("vx", value))

    ok = router.route("vx=1", ctx)

    assert ok is True
    assert ctx.calls == [("vx", 1.0)]
    assert ctx.finalize_calls == [{"vx"}]
    assert not hasattr(ctx, "runtime")
