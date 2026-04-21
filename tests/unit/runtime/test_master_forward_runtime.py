"""主车角色运行时最小行为测试.

@file tests/unit/runtime/test_master_forward_runtime.py
"""

from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Optional
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"


def import_master_module(module_name: str, monkeypatch):
    """按正常包路径导入主车视觉运行模块."""

    monkeypatch.syspath_prepend(str(SRC_ROOT))
    for loaded_name in (
        "vision.master",
        "vision.master.forward_runtime",
        module_name,
    ):
        sys.modules.pop(loaded_name, None)
    return import_module(module_name)


class _FakeUart:
    def __init__(self, incoming_lines=()) -> None:
        self._buffer = "".join("%s\n" % line for line in incoming_lines).encode()
        self.messages = []
        self.read_error: Optional[BaseException] = None
        self.write_error: Optional[BaseException] = None

    def any(self) -> int:
        return len(self._buffer)

    def read(self, size: int) -> bytes:
        if self.read_error is not None:
            raise self.read_error
        chunk = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return chunk

    def write(self, text) -> None:
        if self.write_error is not None:
            raise self.write_error
        self.messages.append(text)


def install_fake_transport_car(monkeypatch):
    """注入共享底盘最小桩对象."""

    events = []
    core_package = ModuleType("core")
    core_module = ModuleType("core.runtime")
    uart3 = _FakeUart()
    uart8 = _FakeUart()

    class _TransportCar:
        def __init__(self) -> None:
            self.wheel_states = [{"encoder": "enc-left"}, {"encoder": "enc-right"}]
            self.imu = "imu"
            self.uart3 = uart3
            self.uart8 = uart8
            self.last_exception_text = "none"
            self._process_uart = self._original_process_uart

        def _original_process_uart(self) -> None:
            events.append("transport_process_uart")

        def mark_tick(self, tick=None) -> None:
            events.append(("mark_tick", tick))

        def set_ticker(self, ticker_obj) -> None:
            events.append(("set_ticker", ticker_obj))

        def step(self) -> bool:
            events.append("transport_step")
            return False

        def _handle_uart_line(self, line: str, source: str) -> None:
            events.append(("handle_uart_line", source, line))

    monkeypatch.setitem(sys.modules, "core", core_package)
    setattr(core_module, "TransportCar", _TransportCar)
    monkeypatch.setitem(sys.modules, "core.runtime", core_module)
    return events, uart3, uart8


def install_fake_uart6_factory(monkeypatch, calls) -> None:
    """注入视觉串口工厂桩, 用于确认主车不会装配视觉分支."""

    hardware_package = ModuleType("hardware")
    uart_bus_module = ModuleType("hardware.uart_bus")

    def create_uart6():
        calls.append("create_uart6")
        raise AssertionError("master runtime should not create uart6")

    setattr(uart_bus_module, "create_uart6", create_uart6)
    monkeypatch.setitem(sys.modules, "hardware", hardware_package)
    monkeypatch.setitem(sys.modules, "hardware.uart_bus", uart_bus_module)


def test_master_forward_runtime_keeps_remote_control_surface(monkeypatch) -> None:
    """主车角色运行时要保留启动壳依赖的对外外观."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )

    runtime = forward_runtime_module.MasterForwardRuntime()
    ticker_obj = object()

    runtime.mark_tick(12)
    runtime.set_ticker(ticker_obj)

    assert runtime.wheel_states == [{"encoder": "enc-left"}, {"encoder": "enc-right"}]
    assert runtime.imu == "imu"
    assert hasattr(runtime, "step")
    assert ("mark_tick", 12) in events
    assert ("set_ticker", ticker_obj) in events


def test_master_forward_runtime_step_runs_role_cycle_before_transport(
    monkeypatch,
) -> None:
    """主车角色运行时的 step 要先进入角色层周期边界再驱动共享底盘."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )
    runtime = forward_runtime_module.MasterForwardRuntime()
    runtime._run_role_cycle = lambda: events.append("role_cycle")

    keep_running = runtime.step()

    assert keep_running is False
    assert events.index("role_cycle") < events.index("transport_step")


def test_master_package_entry_builds_forward_runtime(monkeypatch) -> None:
    """主车包入口要继续给启动壳创建主车角色运行时对象."""

    install_fake_transport_car(monkeypatch)
    master_module = import_master_module("vision.master", monkeypatch)

    runtime = master_module.create_transport_car()

    assert hasattr(runtime, "step")
    assert runtime.imu == "imu"


def test_master_forward_runtime_forwards_velocity_and_keeps_raw_line_for_transport(
    monkeypatch,
) -> None:
    """纯速度命令要上行转发给辅车，同时原始整行继续交给主车底盘。"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"vx=1.0,vy=-2.5,omega=3.0\n"
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )

    runtime = forward_runtime_module.MasterForwardRuntime()

    keep_running = runtime.step()

    assert keep_running is False
    assert uart8.messages == ["vx=1.0,vy=-2.5,omega=3.0\r\n"]
    assert ("handle_uart_line", "uart3", "vx=1.0,vy=-2.5,omega=3.0") in events


def test_master_forward_runtime_only_forwards_velocity_fields_from_mixed_command(
    monkeypatch,
) -> None:
    """混合命令只转发速度字段，非速度内容仍只留给主车本地处理。"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"rear=1,vx=1.0,angle=90,w=-0.5\n"
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["vx=1.0,omega=-0.5\r\n"]
    assert ("handle_uart_line", "uart3", "rear=1,vx=1.0,angle=90,w=-0.5") in events


def test_master_forward_runtime_folds_w_alias_and_keeps_last_angular_velocity(
    monkeypatch,
) -> None:
    """同包同时出现 w 和 omega 时, 转发链要折叠成单个 omega 字段."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"vx=1.0,w=-0.5,omega=2.0\n"
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["vx=1.0,omega=2.0\r\n"]
    assert ("handle_uart_line", "uart3", "vx=1.0,w=-0.5,omega=2.0") in events


def test_master_forward_runtime_does_not_forward_query_or_non_velocity_command(
    monkeypatch,
) -> None:
    """查询和非速度命令不能进入辅车转发链。"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"?health\nrear=1,angle=90\n"
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == []
    assert ("handle_uart_line", "uart3", "?health") in events
    assert ("handle_uart_line", "uart3", "rear=1,angle=90") in events


def test_master_forward_runtime_skips_invalid_velocity_forward_but_records_error(
    monkeypatch,
) -> None:
    """非法速度字段不转发，但主车本地处理和最小错误信息要保留。"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"vx=oops,rear=1\n"
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == []
    assert ("handle_uart_line", "uart3", "vx=oops,rear=1") in events
    assert runtime._transport_car.last_exception_text == "invalid velocity field: vx=oops"


def test_master_forward_runtime_keeps_running_when_forward_write_fails(
    monkeypatch,
) -> None:
    """写出失败只能留下最小错误，不能阻断主车控制周期。"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"vx=1.0\n"
    uart8.write_error = OSError("uart8 boom")
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )

    runtime = forward_runtime_module.MasterForwardRuntime()

    keep_running = runtime.step()

    assert keep_running is False
    assert ("handle_uart_line", "uart3", "vx=1.0") in events
    assert runtime._transport_car.last_exception_text == "uart8 forward write failed"


def test_master_forward_runtime_keeps_later_lines_running_after_invalid_velocity(
    monkeypatch,
) -> None:
    """同一批 UART3 输入里前一条非法速度失败后, 后续合法命令仍要继续转发."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"vx=oops\nvx=1.0,omega=0.5\n"
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["vx=1.0,omega=0.5\r\n"]
    assert ("handle_uart_line", "uart3", "vx=oops") in events
    assert ("handle_uart_line", "uart3", "vx=1.0,omega=0.5") in events
    assert runtime._transport_car.last_exception_text == "invalid velocity field: vx=oops"


def test_master_forward_runtime_rejects_non_finite_velocity_field(
    monkeypatch,
) -> None:
    """nan 和 inf 这类伪数字不能被继续转发给辅车."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"vx=nan,rear=1\n"
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == []
    assert ("handle_uart_line", "uart3", "vx=nan,rear=1") in events
    assert runtime._transport_car.last_exception_text == "invalid velocity field: vx=nan"


def test_master_forward_runtime_rejects_out_of_range_velocity_field(
    monkeypatch,
) -> None:
    """超过辅车入口幅值边界的速度字段不能继续转发."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"vx=1001,rear=1\n"
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == []
    assert ("handle_uart_line", "uart3", "vx=1001,rear=1") in events
    assert runtime._transport_car.last_exception_text == "invalid velocity field: vx=1001"


def test_master_forward_runtime_does_not_assemble_visual_input_branch(
    monkeypatch,
) -> None:
    """主车角色层当前不接视觉输入, 控制周期里也不应装配视觉分支."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"?health\n"
    uart6_calls = []
    install_fake_uart6_factory(monkeypatch, uart6_calls)
    forward_runtime_module = import_master_module(
        "vision.master.forward_runtime", monkeypatch
    )

    runtime = forward_runtime_module.MasterForwardRuntime()

    keep_running = runtime.step()

    assert keep_running is False
    assert uart6_calls == []
    assert ("handle_uart_line", "uart3", "?health") in events
