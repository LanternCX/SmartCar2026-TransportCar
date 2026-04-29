"""非查询命令回包边界测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

import command.commands as _commands  # noqa: F401 触发命令注册

from command.router import router


class _CaptureUart:
    def __init__(self) -> None:
        self.messages = []

    def write(self, text) -> None:
        self.messages.append(text)


class _CommandContext:
    def __init__(self) -> None:
        self.uart3 = _CaptureUart()
        self.uart8 = _CaptureUart()
        self.uart6 = _CaptureUart()
        self.rear_only_mode = False
        self._rear_mode_changed = False

    def _finalize_route(self, _dispatched) -> None:
        return None


def test_rear_still_updates_state_without_uart3_prompt() -> None:
    ctx = _CommandContext()

    assert router.route("rear=1", ctx) is True

    assert ctx.rear_only_mode is True
    assert ctx.uart3.messages == []


def test_print_routes_without_emitting_runtime_uart_text() -> None:
    ctx = _CommandContext()

    assert router.route("print=hello world", ctx) is True

    assert ctx.uart3.messages == []
    assert ctx.uart6.messages == []


def test_router_has_no_query_runtime_entrypoints() -> None:
    assert not hasattr(router, "query")
    assert not hasattr(router, "handle_query")
    assert not hasattr(router, "_query_handlers")


def test_question_prefixed_input_is_not_a_command_reply() -> None:
    ctx = _CommandContext()

    assert router.route("?health", ctx) is False
    assert router.route("?missing", ctx) is False

    assert ctx.uart3.messages == []
