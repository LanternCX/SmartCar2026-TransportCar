"""RuntimeCore 单元测试."""

import types

import pytest


pytestmark = pytest.mark.unit


class FakeUART:
    """最小串口假对象."""

    def __init__(self) -> None:
        self.messages = []

    def write(self, text: str) -> None:
        self.messages.append(text)


class FakeLoggerManager:
    """最小日志管理器假对象."""

    def __init__(self) -> None:
        self.modules = []

    def get_logger(self, module_name: str):
        self.modules.append(module_name)
        return types.SimpleNamespace(module_name=module_name)


def test_runtime_core_owns_uart_role_and_oom_fields() -> None:
    from services.runtime.runtime_core import RuntimeCore

    uart3 = FakeUART()
    uart6 = FakeUART()
    logger_manager = FakeLoggerManager()

    core = RuntimeCore(
        vehicle_role="main",
        now_ms=lambda: 1234,
        now_us=lambda: 5678,
        create_uart3_func=lambda: uart3,
        create_uart6_func=lambda: uart6,
        logger_builder=lambda uart, oom_callback=None: logger_manager,
    )

    assert core.vehicle_role == "main"
    assert core.uart3 is uart3
    assert core.uart6 is uart6
    assert core.oom_count == 0
    assert core.last_oom_stage is None
    assert core.last_exception_text == "none"
    assert core.boot_time_ms == 1234
    assert core.last_time_us == 5678


def test_runtime_core_registers_minimal_loggers_and_records_oom() -> None:
    from services.runtime.runtime_core import RuntimeCore

    core = RuntimeCore(
        vehicle_role="aux",
        now_ms=lambda: 10,
        now_us=lambda: 20,
        create_uart3_func=FakeUART,
        create_uart6_func=FakeUART,
        logger_builder=lambda uart, oom_callback=None: FakeLoggerManager(),
    )

    core.record_oom("format")
    core.record_oom("sink")

    assert core.oom_count == 2
    assert core.last_oom_stage == "sink"
    assert core.log_system.module_name == "system.boot"
    assert core.log_command.module_name == "services.command"
    assert core.log_vision.module_name == "vision.state"
    assert core.log_health.module_name == "system.health"
