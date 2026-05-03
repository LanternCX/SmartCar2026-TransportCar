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

if str(SRC_ROOT) in sys.path:
    sys.path.remove(str(SRC_ROOT))
sys.path.insert(0, str(SRC_ROOT))

EVENT_TARGET_FOUND = 6
STATE_IDLE = 0


def import_master_module(module_name: str, monkeypatch):
    """按正常包路径导入主车视觉运行模块."""

    monkeypatch.syspath_prepend(str(SRC_ROOT))
    for loaded_name in (
        "vision.master",
        "vision.master.forward_runtime",
        "vision.master.state_machine",
        module_name,
    ):
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


class _FakeNowMs:
    def __init__(self, *values: int) -> None:
        self._values = list(values)
        self._last = self._values[-1] if self._values else 0

    def __call__(self) -> int:
        if self._values:
            self._last = self._values.pop(0)
        return self._last




def _reliable_messages(uart):
    return [message for message in uart.messages if message.startswith(("s,", "a,"))]


def _velocity_messages(uart):
    return [message for message in uart.messages if message.startswith("v,")]

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
            self.heading_est = 0.0
            self.command_lock = False
            self.rear_only_mode = False
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

        def set_rear_only_angle_target(self, angle_deg: float) -> None:
            events.append(("set_rear_only_angle_target", float(angle_deg)))
            self.command_lock = True
            self.rear_only_mode = True
            self.control_state = {"vx": 0.0, "vy": 0.0, "omega": 0.0, "angle": float(angle_deg)}

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

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
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

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
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
    assert _reliable_messages(uart8) == []
    assert runtime._transport_car.last_exception_text == "master role cycle failed"


def test_master_forward_runtime_ignores_non_short_packet_text(monkeypatch) -> None:
    """主车角色层只处理正式短包, 非短包文本不进入控制入口."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"omega=0.5\nx=1.0,y=2.0\ntext\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert _reliable_messages(uart8) == []
    assert ("handle_uart_line", "uart3", "omega=0.5") not in events
    assert ("handle_uart_line", "uart3", "x=1.0,y=2.0") not in events
    assert ("handle_uart_line", "uart3", "text") not in events


def test_master_forward_runtime_forwards_remote_v_packet_to_uart8(monkeypatch) -> None:
    """UART3 收到速度短包后, 主车 UART8 前馈输出与底盘速度保持一致."""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,1,-2.50,0.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["v,1.0,-2.5,0.5\r\n"]

def test_master_forward_runtime_forwards_zero_chassis_velocity_without_input(monkeypatch) -> None:
    """主车没有速度输入时, UART8 仍转发当前零底盘速度."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["v,0.0,0.0,0.0\r\n"]

def test_master_forward_runtime_repeats_latest_uart3_forward_without_new_input(monkeypatch) -> None:
    """UART3 无新速度短包时, 主车继续向 UART8 转发当前底盘速度."""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,1,-2.50,0.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()
    runtime.step()

    assert uart8.messages == ["v,1.0,-2.5,0.5\r\n", "v,1.0,-2.5,0.5\r\n"]

def test_master_forward_runtime_accepts_v_packet_without_omega(monkeypatch) -> None:
    """无 omega 的速度短包本地角速度按零量执行."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,1.0,-2.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["v,1.0,-2.5,0.0\r\n"]
    assert ("handle_velocity", "uart3", 1.0, -2.5, 0.0) in events

def test_master_forward_runtime_rejects_non_short_packet_velocity_forward(monkeypatch) -> None:
    """非短包速度文本不能作为主车正式转发入口."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"vx=1.0,vy=2.0\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["v,0.0,0.0,0.0\r\n"]
    assert ("handle_velocity", "uart3", 1.0, 2.0, 0.0) not in events

def test_master_forward_runtime_does_not_derive_angle_from_omega(monkeypatch) -> None:
    """主车不会把角速度字段派生为 angle 转发."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"omega=0.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["v,0.0,0.0,0.0\r\n"]
    assert ("handle_uart_line", "uart3", "omega=0.5") not in events

def test_master_forward_runtime_ignores_non_short_packet_text(monkeypatch) -> None:
    """主车角色层只处理正式短包, 非短包文本不进入控制入口."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"omega=0.5\nx=1.0,y=2.0\ntext\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["v,0.0,0.0,0.0\r\n"]
    assert ("handle_uart_line", "uart3", "omega=0.5") not in events
    assert ("handle_uart_line", "uart3", "x=1.0,y=2.0") not in events
    assert ("handle_uart_line", "uart3", "text") not in events

def test_master_forward_runtime_forwards_uart6_velocity_when_uart6_controls_chassis(monkeypatch) -> None:
    """UART6 视觉速度控制主车底盘时, UART8 前馈同步转发底盘速度."""

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
    assert uart8.messages == ["v,1.0,-2.0,0.0\r\n"]

def test_master_forward_runtime_prefers_uart3_when_uart3_and_uart6_velocity_arrive_same_tick(monkeypatch) -> None:
    """同一控制拍同时存在 UART3 与 UART6 速度时, UART3 控制本地底盘并决定前馈."""

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
    """UART6 新文本非法且无 UART3 输入时, 底盘与前馈继续使用上一条合法视觉速度."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
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
    assert uart8.messages == ["v,1.0,-2.0,0.0\r\n", "v,1.0,-2.0,0.0\r\n"]

def test_master_forward_runtime_does_not_write_vision_velocity_before_valid_uart6_packet(monkeypatch) -> None:
    """未收到任何合法 UART6 视觉速度时, 主车不会主动写入视觉速度."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
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
    assert uart8.messages == ["v,0.0,0.0,0.0\r\n"]
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
    assert uart8.messages == ["v,0.0,0.0,0.0\r\n"]
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
    """UART6 已有合法速度后收到非速度短包, 保持上一条合法视觉速度与前馈."""

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
    assert uart8.messages == ["v,1.0,-2.0,0.0\r\n", "v,1.0,-2.0,0.0\r\n"]
    assert runtime._transport_car.last_exception_text == "none"
    assert runtime._transport_car.last_chassis_target == {
        "source": "uart6",
        "vx": 1.0,
        "vy": -2.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert ("handle_velocity", "uart6", 1.0, -2.0, 0.0) in second_step_events

def test_master_forward_runtime_repeats_state_sync_until_ack(monkeypatch) -> None:
    """主车状态同步包在收到匹配 ACK 前会重复写出."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60))

    seq = runtime.request_state_sync(3, 1, 0)
    runtime.step()
    runtime.step()
    uart8._buffer = ("a,%d\n" % seq).encode()
    runtime.step()
    runtime.step()

    assert _reliable_messages(uart8) == ["s,0,3,1,0\r\n", "s,0,3,1,0\r\n"]


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

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"v,0.5,-0.25\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    keep_running = runtime.step()

    assert keep_running is False
    assert uart6_calls
    assert ("handle_velocity", "uart6", 0.5, -0.25, 0.0) in events


def test_master_forward_runtime_sends_uart6_hook_when_search_starts(monkeypatch) -> None:
    """主车首次进入寻找态时向本车 UART6 发送 hook 同步包."""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0))

    runtime.step()

    assert uart6.messages == ["s,1,1,1,1,1\r\n"]


def test_master_forward_runtime_stops_resending_uart6_hook_after_ack(monkeypatch) -> None:
    """收到匹配 hook ACK 后停止继续重发该 hook."""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60))

    runtime.step()
    runtime.step()
    uart6._buffer = b"a,1\n"
    runtime.step()
    runtime.step()

    assert uart6.messages == ["s,1,1,1,1,1\r\n", "s,1,1,1,1,1\r\n"]


def test_master_forward_runtime_old_uart6_ack_does_not_cancel_unsent_new_hook(monkeypatch) -> None:
    """首拍残留旧 ACK 时, 新 hook 仍要先发出去."""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"a,1\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0))

    runtime.step()

    assert uart6.messages == ["s,1,1,1,1,1\r\n"]


def test_master_forward_runtime_old_uart6_event_before_hook_ack_does_not_start_orbit(monkeypatch) -> None:
    """hook 未建立前的残留旧事件不能直接触发绕行."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = ("r,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0))

    runtime.step()

    assert ("set_rear_only_angle_target", 90.0) not in events


def test_master_forward_runtime_matching_uart6_target_found_acknowledges_and_starts_orbit(monkeypatch) -> None:
    """匹配当前上下文的 hook 命中事件会先请求辅车 idle, 收到 ACK 后再触发绕行."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()

    runtime.step()

    assert "a,7\r\n" in uart6.messages
    assert _reliable_messages(uart8) == ["s,1,0,0,0\r\n"]
    assert ("set_rear_only_angle_target", 90.0) not in events
    uart8._buffer = b"a,1\n"
    runtime.step()
    assert ("set_rear_only_angle_target", 90.0) in events


def test_master_forward_runtime_target_found_before_hook_ack_starts_orbit_after_ack(monkeypatch) -> None:
    """命中先到、hook 确认后到时, 主车在确认建立后仍能进入绕行."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))
    runtime.step()
    uart6._buffer = ("r,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()

    runtime.step()

    assert "a,7\r\n" in uart6.messages
    assert _reliable_messages(uart8) == []
    assert ("set_rear_only_angle_target", 90.0) not in events

    uart6._buffer = b"a,1\n"
    runtime.step()

    assert _reliable_messages(uart8) == ["s,1,0,0,0\r\n"]
    assert ("set_rear_only_angle_target", 90.0) not in events

    uart8._buffer = b"a,1\n"
    runtime.step()

    assert ("set_rear_only_angle_target", 90.0) in events


def test_master_forward_runtime_mismatched_uart6_target_found_only_acknowledges(monkeypatch) -> None:
    """上下文不匹配的 hook 命中事件只确认, 不触发绕行."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,9,%d,300\n" % EVENT_TARGET_FOUND).encode()

    runtime.step()

    assert "a,7\r\n" in uart6.messages
    assert _reliable_messages(uart8) == []
    assert ("set_rear_only_angle_target", 90.0) not in events


def test_master_forward_runtime_assistant_idle_sync_preempts_pending_generic_sync(monkeypatch) -> None:
    """辅车 idle 同步优先于通用同步重发，避免主车等待但辅车没收到命令。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))
    runtime.request_state_sync(3, 1, 0)
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()

    runtime.step()

    assert _reliable_messages(uart8) == ["s,0,3,1,0\r\n", "s,1,0,0,0\r\n"]
    assert ("set_rear_only_angle_target", 90.0) not in events


def test_master_forward_runtime_old_uart8_ack_does_not_cancel_unsent_assistant_idle_sync(monkeypatch) -> None:
    """辅车 idle 同步未实际发出前，残留旧 ACK 不能直接放行绕行。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    uart8._buffer = b"a,1\n"

    runtime.step()

    assert _reliable_messages(uart8) == ["s,1,0,0,0\r\n"]
    assert ("set_rear_only_angle_target", 90.0) not in events


def test_master_forward_runtime_assistant_sync_sequence_is_not_fixed_startup_constant(
    monkeypatch,
) -> None:
    """辅车 idle 同步序号不应固定写死在启动后的常量起点。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(8, 20))
    runtime.step()
    uart6._buffer = ("a,9\nr,15,9,%d,300\n" % EVENT_TARGET_FOUND).encode()

    runtime.step()

    assert _reliable_messages(uart8) == ["s,9,0,0,0\r\n"]


def test_master_forward_runtime_repeats_assistant_idle_sync_until_ack(monkeypatch) -> None:
    """辅车 idle 同步在收到匹配 ACK 前会重复写出."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()

    runtime.step()
    runtime.step()

    assert _reliable_messages(uart8) == ["s,1,0,0,0\r\n", "s,1,0,0,0\r\n"]

    uart8._buffer = b"a,1\n"
    runtime.step()

    assert _reliable_messages(uart8) == ["s,1,0,0,0\r\n", "s,1,0,0,0\r\n"]


def test_master_forward_runtime_stops_search_velocity_while_waiting_assistant_idle_ack(monkeypatch) -> None:
    """等待辅车 idle ACK 期间, 主车停止搜索速度且不再应用新的 UART6 搜索速度."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()

    runtime.step()

    assert runtime._transport_car.last_chassis_target == {
        "source": "master_wait_assistant_idle",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }

    event_count = len(events)
    uart6._buffer = b"v,3.0,4.0\n"
    runtime.step()

    assert ("handle_velocity", "uart6", 3.0, 4.0, 0.0) not in events[event_count:]
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_wait_assistant_idle",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_master_forward_runtime_ignores_uart6_search_velocity_after_orbiting(monkeypatch) -> None:
    """进入绕行态后, 主车不再应用 UART6 搜索速度."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    event_count = len(events)
    runtime._transport_car.last_chassis_target = {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": False,
    }
    uart6._buffer = b"v,3.0,4.0\n"

    runtime.step()

    assert runtime._transport_car.last_chassis_target == {
        "source": None,
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert ("handle_velocity", "uart6", 3.0, 4.0, 0.0) not in events[event_count:]


def test_master_forward_runtime_ignores_uart3_velocity_during_orbiting(monkeypatch) -> None:
    """绕行期间不接受新的 UART3 速度覆盖绕行控制."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    event_count = len(events)
    uart3._buffer = b"v,3.0,4.0,0.7\n"

    runtime.step()

    assert ("handle_velocity", "uart3", 3.0, 4.0, 0.7) not in events[event_count:]
    assert runtime._transport_car.command_lock is True
    assert runtime._transport_car.rear_only_mode is True


def test_master_forward_runtime_returns_idle_after_orbit_finishes(monkeypatch) -> None:
    """绕行完成后, 主车状态机回到 IDLE."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime._transport_car.rear_only_mode = False

    runtime.step()

    assert runtime._state_machine.state == STATE_IDLE


def test_master_forward_runtime_requests_assistant_object_after_orbit_finish_until_ack(
    monkeypatch,
) -> None:
    """绕行完成后, 主车只发一次辅车找物体同步, 并在 ACK 前按原机制重发."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60, 80))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    uart8.messages = []

    runtime.step()

    assert _reliable_messages(uart8) == []

    runtime._transport_car.command_lock = False
    runtime._transport_car.rear_only_mode = False
    runtime.step()
    runtime.step()

    assert _reliable_messages(uart8) == ["s,3,2,1,1\r\n", "s,3,2,1,1\r\n"]

    uart8._buffer = b"a,3\n"
    runtime.step()

    assert _reliable_messages(uart8) == ["s,3,2,1,1\r\n", "s,3,2,1,1\r\n"]
    assert runtime.last_report is None


def test_master_forward_runtime_acknowledges_assistant_target_found_report_and_records_result(
    monkeypatch,
) -> None:
    """主车收到辅车 TARGET_FOUND 回报后回复 ACK, 并记录结果而不推进新主状态."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime._transport_car.rear_only_mode = False
    runtime.step()
    uart8._buffer = b"a,3\nr,11,6,300\n"
    uart8.messages = []

    runtime.step()

    assert "a,11\r\n" in _reliable_messages(uart8)
    assert runtime.last_report == {"type": "r", "seq": 11, "event": 6, "value": 300}
    assert runtime._state_machine.state == STATE_IDLE
    assert events.count(("set_rear_only_angle_target", 90.0)) == 1


def test_master_forward_runtime_applies_uart6_vision_velocity_to_local_chassis(monkeypatch) -> None:
    """UART6 收到视觉速度后, 主车本地底盘按零角速度执行."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
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


def test_master_forward_runtime_clears_oversized_uart3_input_buffer_and_records_invalid_input(
    monkeypatch,
) -> None:
    """UART3 输入缓存超过固定上限时会被清空并记录输入无效。"""

    _events, uart3, _uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"x" * 129
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert runtime._rx_buf3 == ""
    assert runtime._transport_car.last_exception_text == "invalid uart3 input"


def test_master_forward_runtime_clears_oversized_uart8_input_buffer_and_records_invalid_input(
    monkeypatch,
) -> None:
    """UART8 输入缓存超过固定上限时会被清空并记录输入无效。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"x" * 129
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert runtime._rx_buf8 == ""
    assert runtime._transport_car.last_exception_text == "invalid uart8 input"


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


def test_master_forward_runtime_prints_state_debug_to_uart3(monkeypatch) -> None:
    """主车运行时每拍向 UART3 输出状态诊断行."""

    _events, uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, _uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0))

    runtime.step()

    assert uart3.messages
    assert uart3.messages[-1].startswith("dbg,state=SEARCH_OBJECT,")
    assert "ctx=1" in uart3.messages[-1]
    assert "pending_hook=1" in uart3.messages[-1]


def test_master_forward_runtime_prints_orbiting_debug_to_uart3(monkeypatch) -> None:
    """主车进入绕行后 UART3 诊断行能看到 ORBITING."""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()

    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()

    assert uart3.messages[-1].startswith("dbg,state=ORBITING,")
    assert "active_ctx=1" in uart3.messages[-1]
    assert "orbit=1" in uart3.messages[-1]


def test_master_forward_runtime_prints_start_to_uart3_on_boot(monkeypatch) -> None:
    """主车运行时初始化时向 UART3 输出 start."""

    _events, uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, _uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    forward_runtime_module.MasterForwardRuntime()

    assert uart3.messages[0] == "start\r\n"
