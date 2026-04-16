"""非查询命令回包边界测试."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

import command.commands as _commands  # noqa: F401 触发命令与查询注册

from command.router import router


class _CaptureUart:
    def __init__(self) -> None:
        self.messages = []

    def write(self, text) -> None:
        self.messages.append(text)


class _QueryContext:
    def __init__(self) -> None:
        self.uart8 = _CaptureUart()
        self.uart6 = _CaptureUart()
        self.rear_only_mode = False
        self._rear_mode_changed = False

    def _finalize_route(self, _dispatched) -> None:
        return None

    def get_query_uart(self):
        return getattr(self, "_query_response_uart", self.uart6)

    def build_health_snapshot(self):
        return {
            "alive": 1,
            "last_err": "none",
        }


def test_rear_still_updates_state_without_uart8_prompt() -> None:
    ctx = _QueryContext()

    assert router.route("rear=1", ctx) is True

    assert ctx.rear_only_mode is True
    assert ctx.uart8.messages == []


def test_print_routes_without_emitting_runtime_uart_text() -> None:
    ctx = _QueryContext()

    assert router.route("print=hello world", ctx) is True

    assert ctx.uart8.messages == []
    assert ctx.uart6.messages == []


def test_health_query_still_returns_health_reply() -> None:
    ctx = _QueryContext()

    assert router.handle_query("health", ctx, source="uart8") is True

    assert len(ctx.uart8.messages) == 1
    assert ctx.uart8.messages[0].startswith("?health=")


def test_missing_query_still_returns_unknown_reply() -> None:
    ctx = _QueryContext()

    assert router.handle_query("missing", ctx, source="uart8") is False

    assert ctx.uart8.messages == ["?unknown=missing\r\n"]
