"""角色运行时 play 导入边界测试."""

import sys

from protocol.topic import ROLE_ASSISTANT, ROLE_MASTER
from protocol.transport import create_transport
from tests.unit.runtime.transport_runtime_support import (
    BufferedUart,
    ManualClock,
    import_module_clean,
    install_fake_core,
)


def _clear_play_modules() -> None:
    for module_name in tuple(sys.modules):
        if module_name == "play" or module_name.startswith("play."):
            sys.modules.pop(module_name, None)


def _assert_only_sequence_loaded() -> None:
    loaded = {
        module_name
        for module_name in sys.modules
        if module_name == "play" or module_name.startswith("play.")
    }
    assert loaded == {
        "play",
        "play.routines",
        "play.routines.assistant_return_garage",
        "play.routines.master_return_garage",
        "play.routines.startup_move",
        "play.sequence",
    }


class StartupTransport:
    def __init__(self) -> None:
        self.events = []

    def wait_local_vision_ready(self) -> None:
        self.events.append("vision_ready")


def test_master_prepare_runtime_imports_only_light_play_sequence(monkeypatch) -> None:
    _clear_play_modules()
    install_fake_core(monkeypatch)
    clock = ManualClock(0)
    module = import_module_clean("role.master.forward_runtime", monkeypatch)
    transport = StartupTransport()
    runtime = module.MasterForwardRuntime(
        now_ms=clock,
        transport=transport,
    )

    runtime.prepare_runtime()

    assert transport.events == ["vision_ready"]
    _assert_only_sequence_loaded()


def test_assistant_prepare_runtime_imports_only_light_play_sequence(monkeypatch) -> None:
    _clear_play_modules()
    install_fake_core(monkeypatch)
    clock = ManualClock(0)
    module = import_module_clean("role.assistant.follow_runtime", monkeypatch)
    transport = StartupTransport()
    runtime = module.AssistantFollowRuntime(
        now_ms=clock,
        transport=transport,
    )

    runtime.prepare_runtime()

    assert transport.events == ["vision_ready"]
    _assert_only_sequence_loaded()
