"""Unit tests for services.command_router."""

import pytest

from services.command_router import CommandRouter


pytestmark = pytest.mark.unit


class FakeUART:
    """Collect output for query assertions."""

    def __init__(self):
        self.messages = []

    def write(self, text):
        self.messages.append(text)


class FakeContext:
    """Router context fake."""

    def __init__(self):
        self.calls = []
        self.dispatched = None
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

    @router.command("print")
    def cmd_print(local_ctx, value):
        local_ctx.calls.append(("print", value))

    ok = router.route("print=hello world", ctx)
    assert ok is True
    assert ctx.calls == [("print", "hello world")]


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


def test_handle_query_known_token():
    router = CommandRouter()
    ctx = FakeContext()

    @router.query("pos")
    def query_pos(local_ctx):
        local_ctx.calls.append(("query", "pos"))

    ok = router.handle_query("pos", ctx)
    assert ok is True
    assert ctx.calls == [("query", "pos")]


def test_handle_query_unknown_token_writes_unknown_response():
    router = CommandRouter()
    ctx = FakeContext()
    ok = router.handle_query("missing", ctx)
    assert ok is False
    assert ctx.uart6.messages == ["?unknown=missing\r\n"]
