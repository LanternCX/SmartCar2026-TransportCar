"""主车角色运行时短包协议行为测试.

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
    for loaded_name in ("vision.master", "vision.master.forward_runtime", module_name):
        sys.modules.pop(loaded_name, None)
    return import_module(module_name)


class _FakeUart:
    def __init__(self, incoming_lines=()) -> None:
        self._buffer = "".join("%s\n" % line for line in incoming_lines).encode()
        self.messages = []
        self.read_sizes = []
        self.read_error: Optional[BaseException] = None
        self.write_error: Optional[BaseException] = None

    def any(self) -> int:
        return len(self._buffer)

    def read(self, size: int) -> bytes:
        if self.read_error is not None:
            raise self.read_error
        self.read_sizes.append(size)
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
            self.control_state = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
            self.last_chassis_target = {
                "source": None,
                "vx": 0.0,
                "vy": 0.0,
                "omega": 0.0,
                "has_omega": False,
            }
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

        def handle_velocity_packet(self, vx: float, vy: float, omega: float, source: str, has_omega=True) -> None:
            events.append(("handle_velocity", source, vx, vy, omega))
            self.control_state = {"vx": vx, "vy": vy, "omega": omega}
            self.last_chassis_target = {
                "source": source,
                "vx": float(vx),
                "vy": float(vy),
                "omega": float(omega),
                "has_omega": bool(has_omega),
            }

        def _handle_uart_line(self, line: str, source: str) -> None:
            events.append(("handle_uart_line", source, line))

    monkeypatch.setitem(sys.modules, "core", core_package)
    setattr(core_module, "TransportCar", _TransportCar)
    monkeypatch.setitem(sys.modules, "core.runtime", core_module)
    install_fake_uart6_factory(monkeypatch)
    return events, uart3, uart8


def install_fake_uart6_factory(monkeypatch, uart6=None):
    """注入主车本车 UART6 视觉速度输入桩."""

    calls = []
    hardware_package = ModuleType("hardware")
    uart_bus_module = ModuleType("hardware.uart_bus")
    uart6 = uart6 or _FakeUart()

    def create_uart6():
        calls.append("create_uart6")
        return uart6

    setattr(uart_bus_module, "create_uart6", create_uart6)
    monkeypatch.setitem(sys.modules, "hardware", hardware_package)
    monkeypatch.setitem(sys.modules, "hardware.uart_bus", uart_bus_module)
    return calls, uart6


def test_master_forward_runtime_keeps_remote_control_surface(monkeypatch) -> None:
    """主车角色运行时保留启动壳依赖的对外外观."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()
    ticker_obj = object()

    runtime.mark_tick(12)
    runtime.set_ticker(ticker_obj)

    assert runtime.wheel_states == [{"encoder": "enc-left"}, {"encoder": "enc-right"}]
    assert runtime.imu == "imu"
    assert hasattr(runtime, "step")
    assert ("mark_tick", 12) in events
    assert ("set_ticker", ticker_obj) in events


def test_master_forward_runtime_step_runs_role_cycle_before_transport(monkeypatch) -> None:
    """主车角色运行时先进入角色层周期边界再驱动共享底盘."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime()
    runtime._run_role_cycle = lambda: events.append("role_cycle")

    keep_running = runtime.step()

    assert keep_running is False
    assert events.index("role_cycle") < events.index("transport_step")


def test_master_package_entry_builds_forward_runtime(monkeypatch) -> None:
    """主车包入口给启动壳创建主车角色运行时对象."""

    install_fake_transport_car(monkeypatch)
    master_module = import_master_module("vision.master", monkeypatch)

    runtime = master_module.create_transport_car()

    assert hasattr(runtime, "step")
    assert runtime.imu == "imu"


def test_master_forward_runtime_applies_remote_v_packet_to_local_chassis(monkeypatch) -> None:
    """UART3 收到速度短包后, 主车本地速度目标与遥控输入保持一致."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,1.0,-2.5,0.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert runtime._transport_car.last_chassis_target == {
        "source": "uart3",
        "vx": 1.0,
        "vy": -2.5,
        "omega": 0.5,
        "has_omega": True,
    }
    assert ("handle_velocity", "uart3", 1.0, -2.5, 0.5) in events
    assert ("handle_uart_line", "uart3", "v,1.0,-2.5,0.5") not in events


def test_master_forward_runtime_requires_structured_velocity_entry(monkeypatch) -> None:
    """主车速度短包只调用共享底盘结构化速度入口."""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,1.0,-2.5,0.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime()
    delattr(type(runtime._transport_car), "handle_velocity_packet")

    runtime.step()

    assert runtime._transport_car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert uart8.messages == []
    assert runtime._transport_car.last_exception_text == "master role cycle failed"


def test_master_forward_runtime_forwards_remote_v_packet_to_uart8(monkeypatch) -> None:
    """UART3 收到速度短包后, 主车 UART8 前馈输出与遥控输入保持一致."""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,1,-2.50,0.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["v,1,-2.50,0.5\r\n"]


def test_master_forward_runtime_accepts_v_packet_without_omega(monkeypatch) -> None:
    """无 omega 的速度短包本地角速度按零量执行."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,1.0,-2.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["v,1.0,-2.5\r\n"]
    assert ("handle_velocity", "uart3", 1.0, -2.5, 0.0) in events


def test_master_forward_runtime_rejects_non_short_packet_velocity_forward(monkeypatch) -> None:
    """非短包速度文本不能作为主车正式转发入口."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"vx=1.0,vy=2.0\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == []
    assert ("handle_velocity", "uart3", 1.0, 2.0, 0.0) not in events


def test_master_forward_runtime_does_not_derive_angle_from_omega(monkeypatch) -> None:
    """主车不会把角速度字段派生为 angle 转发."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"omega=0.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == []
    assert ("handle_uart_line", "uart3", "omega=0.5") not in events


def test_master_forward_runtime_ignores_non_short_packet_text(monkeypatch) -> None:
    """主车角色层只处理正式短包, 非短包文本不进入控制入口."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"omega=0.5\nx=1.0,y=2.0\ntext\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == []
    assert ("handle_uart_line", "uart3", "omega=0.5") not in events
    assert ("handle_uart_line", "uart3", "x=1.0,y=2.0") not in events
    assert ("handle_uart_line", "uart3", "text") not in events


def test_master_forward_runtime_repeats_state_sync_until_ack(monkeypatch) -> None:
    """主车状态同步包在收到匹配 ACK 前会重复写出."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime()

    seq = runtime.request_state_sync(3, 1, 0)
    runtime.step()
    runtime.step()
    uart8._buffer = ("a,%d\n" % seq).encode()
    runtime.step()
    runtime.step()

    assert uart8.messages[:2] == ["s,%d,3,1,0\r\n" % seq, "s,%d,3,1,0\r\n" % seq]
    assert uart8.messages.count("s,%d,3,1,0\r\n" % seq) == 2


def test_master_forward_runtime_records_report_packet(monkeypatch) -> None:
    """主车通过 UART8 记录事件回报短包."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"r,12,2,-1\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert runtime.last_report == {"type": "r", "seq": 12, "event": 2, "value": -1}


def test_master_forward_runtime_assembles_local_uart6_vision_input(monkeypatch) -> None:
    """主车角色层会装配本车 UART6 视觉速度输入."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"v,0.5,-0.25\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    keep_running = runtime.step()

    assert keep_running is False
    assert uart6_calls
    assert ("handle_velocity", "uart6", 0.5, -0.25, 0.0) in events


def test_master_forward_runtime_applies_uart6_vision_velocity_to_local_chassis(monkeypatch) -> None:
    """UART6 收到视觉速度后, 主车本地底盘按零角速度执行."""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"v,1.0,-2.0\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert runtime._transport_car.last_chassis_target == {
        "source": "uart6",
        "vx": 1.0,
        "vy": -2.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_forward_runtime_does_not_forward_uart6_vision_velocity_to_uart8(monkeypatch) -> None:
    """UART6 视觉速度只作用于主车本地底盘, 不写入 UART8."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"v,1.0,-2.0\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart6.any() == 0
    assert runtime._transport_car.last_chassis_target == {
        "source": "uart6",
        "vx": 1.0,
        "vy": -2.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert uart8.messages == []


def test_master_forward_runtime_prefers_uart3_when_uart3_and_uart6_velocity_arrive_same_tick(monkeypatch) -> None:
    """同一控制拍同时存在 UART3 与 UART6 速度时, UART3 控制本地底盘并独占转发."""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart3._buffer = b"v,3.0,4.0,0.7\n"
    uart6._buffer = b"v,1.0,-2.0\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert runtime._transport_car.last_chassis_target == {
        "source": "uart3",
        "vx": 3.0,
        "vy": 4.0,
        "omega": 0.7,
        "has_omega": True,
    }
    assert uart8.messages == ["v,3.0,4.0,0.7\r\n"]


def test_master_forward_runtime_reuses_latest_uart6_velocity_without_new_uart3_input(monkeypatch) -> None:
    """UART6 新文本非法且无 UART3 输入时, 底盘继续使用上一条合法视觉速度."""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"v,1.0,-2.0\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()
    uart6._buffer = b"v,bad,-9.0\n"
    runtime._transport_car.last_chassis_target = {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": False,
    }
    runtime.step()

    assert uart6.any() == 0
    assert runtime._transport_car.last_chassis_target == {
        "source": "uart6",
        "vx": 1.0,
        "vy": -2.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_forward_runtime_does_not_write_vision_velocity_before_valid_uart6_packet(monkeypatch) -> None:
    """未收到任何合法 UART6 视觉速度时, 主车不会主动写入视觉速度."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"v,bad,-2.0\ntext\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert runtime._transport_car.last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert not any(event[0] == "handle_velocity" and event[1] == "uart6" for event in events)


def test_master_forward_runtime_ignores_uart6_non_velocity_short_packet(monkeypatch) -> None:
    """UART6 收到非速度短包时, 不写底盘、不转发且不记录异常."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"r,12,2,-1\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert "transport_step" in events
    assert uart8.messages == []
    assert runtime._transport_car.last_exception_text == "none"
    assert runtime._transport_car.last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert not any(event[0] == "handle_velocity" and event[1] == "uart6" for event in events)


def test_master_forward_runtime_ignores_uart6_non_velocity_without_overwriting_latest_valid(monkeypatch) -> None:
    """UART6 已有合法速度后收到非速度短包, 保持上一条合法视觉速度."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"v,1.0,-2.0\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()
    event_count_before_second_step = len(events)
    uart6._buffer = b"r,12,2,-1\n"
    runtime._transport_car.last_chassis_target = {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": False,
    }
    runtime.step()

    second_step_events = events[event_count_before_second_step:]
    assert uart6.any() == 0
    assert uart8.messages == []
    assert runtime._transport_car.last_exception_text == "none"
    assert runtime._transport_car.last_chassis_target == {
        "source": "uart6",
        "vx": 1.0,
        "vy": -2.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert ("handle_velocity", "uart6", 1.0, -2.0, 0.0) in second_step_events


def test_master_forward_runtime_records_invalid_uart6_velocity_without_overwriting_latest_valid(monkeypatch) -> None:
    """UART6 收到非法速度短包时, 记录输入无效且不覆盖上一条合法视觉速度."""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"v,1.0,-2.0\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()
    uart6._buffer = b"v,bad,-9.0\n"
    runtime._transport_car.last_chassis_target = {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": False,
    }
    runtime.step()

    assert uart6.any() == 0
    assert runtime._transport_car.last_exception_text == "invalid uart6 velocity packet"
    assert runtime._transport_car.last_chassis_target == {
        "source": "uart6",
        "vx": 1.0,
        "vy": -2.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_forward_runtime_leaves_uart6_half_line_pending_and_keeps_control_cycle(monkeypatch) -> None:
    """UART6 收到半行输入时不处理该半行, 控制周期继续执行."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"v,4.0,5.0"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert "transport_step" in events
    assert runtime._rx_buf6 == "v,4.0,5.0"
    assert runtime._transport_car.last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert not any(event[0] == "handle_velocity" and event[1] == "uart6" for event in events)


def test_master_forward_runtime_clears_oversized_uart6_input_buffer_and_records_invalid_input(monkeypatch) -> None:
    """UART6 输入缓存超过固定上限时会被清空并记录输入无效."""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"x" * 129
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert runtime._rx_buf6 == ""
    assert runtime._transport_car.last_exception_text == "invalid uart6 input"


def test_master_forward_runtime_drops_oversized_uart6_line_before_parsing(monkeypatch) -> None:
    """UART6 带换行超长行在解析前丢弃并记录输入无效."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"v," + b"1" * 200 + b",0\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert runtime._rx_buf6 == ""
    assert runtime._transport_car.last_exception_text == "invalid uart6 input"
    assert not any(event[0] == "handle_velocity" and event[1] == "uart6" for event in events)


def test_master_forward_runtime_limits_single_uart6_read_size(monkeypatch) -> None:
    """UART6 单次读取长度不能随硬件缓存无限放大."""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"x" * 300
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart6.read_sizes
    assert max(uart6.read_sizes) <= 128


def test_master_forward_runtime_keeps_transport_step_when_uart6_read_fails(monkeypatch) -> None:
    """UART6 读取异常时, 控制周期仍继续执行共享底盘 step()."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"v,1.0,2.0\n"
    uart6.read_error = RuntimeError("uart6 read timeout")
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    keep_running = runtime.step()

    assert keep_running is False
    assert "transport_step" in events
    assert runtime._transport_car.last_exception_text == "uart6 read failed"
