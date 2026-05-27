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
EVENT_ALIGNED = 7
EVENT_CLEARED = 9
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
        self.write_return_value: Optional[int] = None

    def any(self) -> int:
        return len(self._buffer)

    def read(self, size: int) -> bytes:
        if self.read_error is not None:
            raise self.read_error
        self.read_sizes.append(size)
        chunk = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return chunk

    def write(self, text) -> int | None:
        if self.write_error is not None:
            raise self.write_error
        self.messages.append(text)
        if self.write_return_value is None:
            return len(text)
        return self.write_return_value


class _FakeNowMs:
    def __init__(self, *values: int) -> None:
        self._values = list(values)
        self._last = self._values[-1] if self._values else 0

    def __call__(self) -> int:
        if self._values:
            self._last = self._values.pop(0)
        return self._last


class _ManualNowMs:
    def __init__(self, value: int = 0) -> None:
        self.value = int(value)

    def __call__(self) -> int:
        return int(self.value)




def _reliable_messages(uart):
    return [message for message in uart.messages if message.startswith(("s,", "a,"))]


def _velocity_messages(uart):
    return [message for message in uart.messages if message.startswith("v,")]


def _hook_sync_message(module, seq=1, context_id=1):
    return "s,%d,%d,%d,1,%d\r\n" % (
        int(seq),
        int(context_id),
        int(module.STATE_SEARCH_OBJECT),
        int(module.MASTER_SEARCH_HOOK_CONFIG_ID),
    )


def _finish_hook_sync_message(module, seq=4, context_id=4):
    return "s,%d,%d,%d,%d,%d\r\n" % (
        int(seq),
        int(context_id),
        int(module.STATE_TRANSPORT_OBJECT),
        int(module.TARGET_EDGE_LINE),
        int(module.MASTER_TRANSPORT_FINISH_HOOK_CONFIG_ID),
    )


def _orbit_hook_sync_message(module, seq=128, context_id=2):
    return "s,%d,%d,%d,1,%d\r\n" % (
        int(seq),
        int(context_id),
        int(module.STATE_ORBITING),
        int(module.MASTER_ORBIT_HOOK_CONFIG_ID),
    )


def _assistant_sync_message(seq, state, target, arg):
    return "s,%d,%d,%d,%d\r\n" % (
        int(seq),
        int(state),
        int(target),
        int(arg),
    )


def _default_orbit_target_event(module):
    return (
        "set_orbit_target",
        float(module.MASTER_ORBIT_TARGET_DEG),
        float(module.MASTER_ORBIT_RADIUS_SCALE),
    )


def _set_filtered_speeds(car, *speeds):
    for state, speed in zip(car.wheel_states, speeds):
        state["filtered_speed"] = float(speed)

def install_fake_transport_car(monkeypatch):
    """注入共享底盘最小桩对象."""

    events = []
    core_package = ModuleType("core")
    core_module = ModuleType("core.runtime")
    uart3 = _FakeUart()
    uart8 = _FakeUart()

    class _TransportCar:
        def __init__(self) -> None:
            self.wheel_states = [
                {"encoder": "enc-m", "filtered_speed": 0.0},
                {"encoder": "enc-l", "filtered_speed": 0.0},
                {"encoder": "enc-r", "filtered_speed": 0.0},
            ]
            self.imu = "imu"
            self.uart8 = uart8
            self.last_exception_text = "none"
            self.heading_est = 0.0
            self.command_lock = False
            self.orbit_mode = False
            self.control_state = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
            self.last_chassis_target = {
                "source": None,
                "vx": 0.0,
                "vy": 0.0,
                "omega": 0.0,
                "has_omega": False,
            }
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

        def set_orbit_target(self, angle_deg: float, radius_scale: float) -> None:
            events.append(("set_orbit_target", float(angle_deg), float(radius_scale)))
            self.command_lock = True
            self.orbit_mode = True
            self.control_state = {
                "vx": 0.0,
                "vy": 0.0,
                "omega": 0.0,
                "angle": float(angle_deg),
            }

        def set_orbit_velocity_correction(self, vx: float, vy: float) -> None:
            events.append(("set_orbit_velocity_correction", float(vx), float(vy)))
            self.control_state["vx"] = float(vx)
            self.control_state["vy"] = float(vy)
            self.last_chassis_target = {
                "source": "master_orbit_vision",
                "vx": float(vx),
                "vy": float(vy),
                "omega": self.control_state.get("omega", 0.0),
                "has_omega": False,
            }

        def set_heading_target(self, angle_deg: float) -> None:
            events.append(("set_heading_target", float(angle_deg)))
            self.command_lock = True
            self.orbit_mode = False
            self.control_state["omega"] = 0.0
            self.control_state["angle"] = float(angle_deg)

        def set_heading_transition_target(self, angle_deg: float) -> None:
            events.append(("set_heading_transition_target", float(angle_deg)))
            self.command_lock = True
            self.orbit_mode = False
            self.control_state["omega"] = 0.0
            self.control_state["angle"] = float(angle_deg)

        def set_relative_translation_target(
            self,
            dx: float,
            dy: float,
            hold_heading_deg=None,
            max_speed_cmd=None,
        ) -> None:
            event = ["set_relative_translation_target", float(dx), float(dy)]
            if hold_heading_deg is not None:
                event.append(float(hold_heading_deg))
            if max_speed_cmd is not None:
                event.append(float(max_speed_cmd))
            events.append(tuple(event))
            self.command_lock = True
            self.orbit_mode = False
            self.control_state = {
                "vx": 0.0,
                "vy": 0.0,
                "omega": 0.0,
                "angle": float(self.heading_est if hold_heading_deg is None else hold_heading_deg),
                "x": float(dx),
                "y": float(dy),
            }

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


def install_fake_startup_log(monkeypatch):
    """注入启动日志桩并收集日志文本."""

    logs = []
    startup_log_module = ModuleType("utils.startup_log")

    def _log(stage, detail=""):
        logs.append("%s|%s" % (stage, detail))
        return logs[-1]

    setattr(startup_log_module, "log", _log)
    monkeypatch.setitem(sys.modules, "utils.startup_log", startup_log_module)
    return logs


def test_master_forward_runtime_keeps_remote_control_surface(monkeypatch) -> None:
    """主车角色运行时保留启动壳依赖的对外外观."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()
    ticker_obj = object()

    runtime.mark_tick(12)
    runtime.set_ticker(ticker_obj)

    assert runtime.wheel_states == [
        {"encoder": "enc-m", "filtered_speed": 0.0},
        {"encoder": "enc-l", "filtered_speed": 0.0},
        {"encoder": "enc-r", "filtered_speed": 0.0},
    ]
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


def test_master_forward_runtime_forwards_zero_chassis_velocity_without_input(monkeypatch) -> None:
    """主车没有速度输入时, UART8 仍转发当前零底盘速度."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["v,0.0,0.0,0.0\r\n"]

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

def test_master_forward_runtime_ignores_uart3_when_uart6_velocity_arrives(monkeypatch) -> None:
    """UART3 作为 REPL 输入时, 主车本地速度使用 UART6 视觉输入."""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart3._buffer = b"v,3.0,4.0,0.7\n"
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
    assert uart3.any() > 0
    assert uart8.messages == ["v,1.0,-2.0,0.0\r\n"]

def test_master_forward_runtime_reuses_latest_uart6_velocity_without_new_input(monkeypatch) -> None:
    """UART6 新文本非法时, 底盘与前馈继续使用上一条合法视觉速度."""

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


def test_master_forward_runtime_logs_generic_sync_start_and_done(monkeypatch) -> None:
    """主车对辅车的通用同步在首次发起和确认完成时各记一次日志."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    logs = install_fake_startup_log(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))

    seq = runtime.request_state_sync(3, 1, 0)
    runtime.step()
    uart8._buffer = ("a,%d\n" % seq).encode()
    runtime.step()

    sync_logs = [
        message for message in logs if message.startswith("sync|master->assistant")
    ]
    assert sync_logs == [
        "sync|master->assistant sync start seq=0 state=3 target=1 arg=0",
        "sync|master->assistant sync done seq=0 state=3 target=1 arg=0",
    ]


def test_master_forward_runtime_skips_uart8_velocity_when_sync_is_sent(
    monkeypatch,
) -> None:
    """主车同一拍发 UART8 可靠同步时不再发速度前馈."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0))

    runtime.request_state_sync(3, 1, 0)
    runtime.step()

    assert uart8.messages == ["s,0,3,1,0\r\n"]


def test_master_forward_runtime_skips_uart8_velocity_during_assistant_idle_sync(
    monkeypatch,
) -> None:
    """主车进入辅车 idle 同步阶段时不发速度前馈."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20))

    runtime.step()
    uart8.messages = []
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()

    assert uart8.messages == ["s,1,0,0,0\r\n"]


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

    assert uart6.messages == [_hook_sync_message(forward_runtime_module)]


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

    expected_message = _hook_sync_message(forward_runtime_module)
    assert uart6.messages == [expected_message, expected_message]


def test_master_forward_runtime_logs_hook_sync_start_and_done(monkeypatch) -> None:
    """主车对摄像头的 hook 同步在首次发起和确认完成时各记一次日志."""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    logs = install_fake_startup_log(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))

    runtime.step()
    uart6._buffer = b"a,1\n"
    runtime.step()

    sync_logs = [message for message in logs if message.startswith("sync|")]
    assert sync_logs == [
        (
            "sync|master->camera sync start seq=1 context=1 state=%d target=1 arg=%d"
            % (
                forward_runtime_module.STATE_SEARCH_OBJECT,
                forward_runtime_module.MASTER_SEARCH_HOOK_CONFIG_ID,
            )
        ),
        (
            "sync|master->camera sync done seq=1 context=1 state=%d target=1 arg=%d"
            % (
                forward_runtime_module.STATE_SEARCH_OBJECT,
                forward_runtime_module.MASTER_SEARCH_HOOK_CONFIG_ID,
            )
        ),
    ]


def test_master_forward_runtime_sends_only_one_reliable_sync_per_cycle(monkeypatch) -> None:
    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)
    def _mark_new_reliable_pair():
        runtime._pending_hook_created_this_cycle = True
        runtime._pending_assistant_sync_created_this_cycle = True

    runtime._advance_state_machine = _mark_new_reliable_pair
    runtime._drain_state_machine_outputs = lambda: None
    runtime._process_uart6 = lambda: None
    runtime._process_uart8 = lambda: None
    runtime._run_clear_phase = lambda: None
    runtime._run_turn_back_phase = lambda: None
    runtime._forward_current_chassis_velocity = lambda: None
    runtime._pending_hook = {
        "kind": "transport_hook",
        "reliable_seq": 9,
        "context_id": 7,
        "state": forward_runtime_module.STATE_SEARCH_OBJECT,
        "target": forward_runtime_module.TARGET_OBJECT,
        "arg": forward_runtime_module.MASTER_TRANSPORT_HOOK_CONFIG_ID,
        "last_sent_ms": None,
        "sent_once": False,
    }
    runtime._pending_assistant_sync = {
        "kind": "assistant_object",
        "seq": 10,
        "state": 2,
        "target": 1,
        "arg": forward_runtime_module.ASSISTANT_APPROACH_OBJECT_CONFIG_ID,
        "last_sent_ms": None,
        "sent_once": False,
    }
    runtime._run_role_cycle()

    assert uart6.messages == []
    assert uart8.messages == [
        "s,10,%d,1,%d\r\n"
        % (
            2,
            forward_runtime_module.ASSISTANT_APPROACH_OBJECT_CONFIG_ID,
        )
    ]
    assert runtime._pending_hook["sent_once"] is False

    runtime._pending_assistant_sync_created_this_cycle = False
    runtime._run_role_cycle()

    assert uart6.messages == [
        "s,9,7,%d,%d,%d\r\n"
        % (
            forward_runtime_module.STATE_SEARCH_OBJECT,
            forward_runtime_module.TARGET_OBJECT,
            forward_runtime_module.MASTER_TRANSPORT_HOOK_CONFIG_ID,
        )
    ]
    assert runtime._pending_hook["sent_once"] is True


def test_master_forward_runtime_old_uart6_ack_does_not_cancel_unsent_new_hook(monkeypatch) -> None:
    """首拍残留旧 ACK 时, 新 hook 仍要先发出去."""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = b"a,1\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0))

    runtime.step()

    assert uart6.messages == [_hook_sync_message(forward_runtime_module)]


def test_master_forward_runtime_old_uart6_event_before_hook_ack_does_not_start_orbit(monkeypatch) -> None:
    """hook 未建立前的残留旧事件不能直接触发绕行."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    uart6._buffer = ("r,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0))

    runtime.step()

    assert _default_orbit_target_event(forward_runtime_module) not in events


def test_master_forward_runtime_matching_uart6_target_found_acknowledges_and_starts_orbit(monkeypatch) -> None:
    """匹配当前上下文的 hook 命中事件会先请求辅车 idle, 收到 ACK 后再走统一绕行入口."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()

    runtime.step()

    assert "a,7\r\n" in uart6.messages
    assert _reliable_messages(uart8) == ["s,1,0,0,0\r\n"]
    assert _default_orbit_target_event(forward_runtime_module) not in events
    uart8._buffer = b"a,1\n"
    runtime.step()
    assert _default_orbit_target_event(forward_runtime_module) in events


def test_master_forward_runtime_target_found_before_hook_ack_starts_orbit_after_ack(monkeypatch) -> None:
    """命中先到、hook 确认后到时, 主车在确认建立后仍能进入统一绕行入口."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))
    runtime.step()
    uart6._buffer = ("r,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()

    runtime.step()

    assert "a,7\r\n" in uart6.messages
    assert _reliable_messages(uart8) == []
    assert _default_orbit_target_event(forward_runtime_module) not in events

    uart6._buffer = b"a,1\n"
    runtime.step()

    assert _reliable_messages(uart8) == ["s,1,0,0,0\r\n"]
    assert _default_orbit_target_event(forward_runtime_module) not in events

    uart8._buffer = b"a,1\n"
    runtime.step()

    assert _default_orbit_target_event(forward_runtime_module) in events


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
    assert _default_orbit_target_event(forward_runtime_module) not in events


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
    assert _default_orbit_target_event(forward_runtime_module) not in events


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
    assert _default_orbit_target_event(forward_runtime_module) not in events


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
    uart6._buffer = b"a,128\nv,3.0,4.0\n"
    runtime.step()

    assert ("handle_velocity", "uart6", 3.0, 4.0, 0.0) not in events[event_count:]
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_wait_assistant_idle",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }



def test_master_forward_runtime_assistant_object_sync_does_not_stop_assistant(monkeypatch) -> None:
    """辅车接近目标同步只建立可靠同步, 不走等待辅车停车副作用."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.last_chassis_target = {
        "source": "probe",
        "vx": 1.0,
        "vy": 2.0,
        "omega": 3.0,
        "has_omega": True,
    }
    event_count = len(events)
    runtime._transport_car.command_lock = False

    runtime.step()

    assert runtime._pending_assistant_sync == {
        "kind": "assistant_object",
        "seq": 3,
        "state": 2,
        "target": 1,
        "arg": forward_runtime_module.ASSISTANT_APPROACH_OBJECT_CONFIG_ID,
        "last_sent_ms": 60,
        "sent_once": True,
    }
    assert not any(
        event[0] == "handle_velocity" and event[1] == "master_wait_assistant_idle"
        for event in events[event_count:]
    )
    assert runtime._transport_car.last_chassis_target == {
        "source": "probe",
        "vx": 1.0,
        "vy": 2.0,
        "omega": 3.0,
        "has_omega": True,
    }



def test_master_forward_runtime_assistant_orbit_sync_does_not_stop_assistant(monkeypatch) -> None:
    """辅车绕行同步只建立可靠同步, 不走等待辅车停车副作用."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    runtime._transport_car.last_chassis_target = {
        "source": "probe",
        "vx": 1.0,
        "vy": 2.0,
        "omega": 3.0,
        "has_omega": True,
    }
    event_count = len(events)
    uart8._buffer = b"a,3\nr,9,6,300\n"

    runtime.step()

    assert runtime._pending_assistant_sync == {
        "kind": "assistant_orbit",
        "seq": 5,
        "state": 3,
        "target": 1,
        "arg": 0,
        "last_sent_ms": 100,
        "sent_once": True,
    }
    assert not any(
        event[0] == "handle_velocity" and event[1] == "master_wait_assistant_idle"
        for event in events[event_count:]
    )
    assert runtime._transport_car.last_chassis_target == {
        "source": "probe",
        "vx": 1.0,
        "vy": 2.0,
        "omega": 3.0,
        "has_omega": True,
    }
    assert runtime.last_report == {"type": "r", "seq": 9, "event": 6, "value": 300}

def test_master_forward_runtime_applies_uart6_velocity_as_orbit_correction(monkeypatch) -> None:
    """进入绕行态后, UART6 速度作为绕行视觉修正生效."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.ORBIT_VISION_CORRECTION_ENABLED = True

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
    uart6._buffer = b"a,128\nv,3.0,4.0\n"

    runtime.step()

    assert runtime._transport_car.last_chassis_target == {
        "source": "master_orbit_vision",
        "vx": 3.0,
        "vy": 4.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert ("handle_velocity", "uart6", 3.0, 4.0, 0.0) not in events[event_count:]
    assert ("set_orbit_velocity_correction", 3.0, 4.0) in events[event_count:]


def test_master_forward_runtime_sends_orbit_vision_hook_when_orbit_starts(monkeypatch) -> None:
    """主车进入绕行态时向本车视觉同步绕行修正配置."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"

    runtime.step()

    assert _orbit_hook_sync_message(forward_runtime_module) in uart6.messages


def test_master_forward_runtime_orbit_vision_hook_uses_new_context(monkeypatch) -> None:
    """主车绕行视觉同步使用新上下文, 避免被 OpenART 当作搜索同步重复包."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))
    runtime.step()
    search_sync = _reliable_messages(uart6)[-1]
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"

    runtime.step()

    orbit_sync = [message for message in _reliable_messages(uart6) if message.startswith("s,128,")][-1]
    search_context = int(search_sync.strip().split(",")[2])
    orbit_context = int(orbit_sync.strip().split(",")[2])
    assert orbit_context == (search_context + 1) % 256


def test_master_forward_runtime_orbit_vision_switch_only_disables_motion_correction(monkeypatch) -> None:
    """关闭绕行视觉修正时, 主车仍建立视觉 hook, 但不写入运动修正."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.ORBIT_VISION_CORRECTION_ENABLED = False

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    event_count = len(events)
    uart6._buffer = b"a,128\nv,3.0,4.0\n"

    runtime.step()

    assert _orbit_hook_sync_message(forward_runtime_module) in uart6.messages
    assert not any(event[0] == "set_orbit_velocity_correction" for event in events[event_count:])
    assert runtime._latest_uart6_velocity == {
        "type": "v",
        "vx": 3.0,
        "vy": 4.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_forward_runtime_stale_orbit_hook_ack_does_not_ack_post_orbit_hook(
    monkeypatch,
) -> None:
    """绕行视觉 ACK 不能误确认绕行后的搜索 hook."""

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
    uart6._buffer = b"a,128\n"

    runtime.step()

    assert runtime._pending_hook is not None
    assert runtime._pending_hook["state"] == forward_runtime_module.STATE_SEARCH_OBJECT
    assert runtime._pending_hook["reliable_seq"] == 2


def test_master_forward_runtime_keeps_orbiting_when_uart3_has_repl_input(monkeypatch) -> None:
    """绕行期间 UART3 输入只留给 REPL."""

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
    assert uart3.any() > 0
    assert runtime._transport_car.command_lock is True
    assert runtime._transport_car.orbit_mode is True


def test_master_forward_runtime_returns_search_after_orbit_finishes(monkeypatch) -> None:
    """绕行完成后, 主车重新进入对正态."""

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

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_SEARCH_OBJECT


def test_master_forward_runtime_orbit_finish_only_depends_on_unlock(
    monkeypatch,
) -> None:
    """绕行结束只看当前统一绕行是否解锁."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    uart8.messages = []
    runtime._transport_car.command_lock = False

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_SEARCH_OBJECT
    assert _reliable_messages(uart8) == [
        _assistant_sync_message(
            3,
            2,
            1,
            forward_runtime_module.ASSISTANT_APPROACH_OBJECT_CONFIG_ID,
        )
    ]


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
    runtime.step()
    runtime.step()
    uart6._buffer = b"a,2\n"
    runtime.step()

    expected_message = _assistant_sync_message(
        3,
        2,
        1,
        forward_runtime_module.ASSISTANT_APPROACH_OBJECT_CONFIG_ID,
    )
    assert _reliable_messages(uart8) == [expected_message]

    uart8._buffer = b"a,3\n"
    runtime.step()

    assert _reliable_messages(uart8) == [expected_message]
    assert runtime.last_report is None


def test_master_forward_runtime_acknowledges_assistant_target_found_report_and_records_result(
    monkeypatch,
) -> None:
    """主车收到辅车 TARGET_FOUND 回报后回复 ACK、记录结果并下发辅车绕行同步."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(
        now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100, 120, 140, 160)
    )
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart8._buffer = b"a,3\nr,11,6,300\n"
    uart8.messages = []

    runtime.step()
    uart6._buffer = b"a,2\n"
    runtime.step()

    assert "a,11\r\n" in _reliable_messages(uart8)
    assert "s,5,3,1,0\r\n" in _reliable_messages(uart8)
    assert runtime.last_report == {"type": "r", "seq": 11, "event": 6, "value": 300}
    assert runtime._state_machine.state == forward_runtime_module.STATE_SEARCH_OBJECT
    assert events.count(_default_orbit_target_event(forward_runtime_module)) == 1

    runtime.step()

    assert _reliable_messages(uart8).count("s,5,3,1,0\r\n") == 2

    uart8._buffer = b"a,5\n"
    runtime.step()
    runtime.step()

    assert _reliable_messages(uart8).count("s,5,3,1,0\r\n") == 2


def test_master_forward_runtime_keeps_search_stop_orbit_and_assistant_object_order(monkeypatch) -> None:
    """主车寻找、停辅车、绕行、绕行完成后下发找物体的顺序保持不变."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60, 80))

    runtime.step()
    assert runtime._state_machine.state == forward_runtime_module.STATE_SEARCH_OBJECT
    assert _reliable_messages(uart8) == []

    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()

    assert _reliable_messages(uart8) == ["s,1,0,0,0\r\n"]
    assert _default_orbit_target_event(forward_runtime_module) not in events

    uart8._buffer = b"a,1\n"
    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_ORBITING
    assert _default_orbit_target_event(forward_runtime_module) in events

    runtime.step()

    assert _reliable_messages(uart8) == ["s,1,0,0,0\r\n"]

    runtime._transport_car.command_lock = False
    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_SEARCH_OBJECT
    assert _reliable_messages(uart8) == [
        "s,1,0,0,0\r\n",
        _assistant_sync_message(
            3,
            2,
            1,
            forward_runtime_module.ASSISTANT_APPROACH_OBJECT_CONFIG_ID,
        ),
    ]


def test_master_forward_runtime_keeps_orbit_heading_during_post_orbit_realign(
    monkeypatch,
) -> None:
    """绕行结束后的二次对正继续维持绕行目标角度."""

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
    uart6._buffer = b"v,3.0,4.0\n"

    runtime.step()

    assert runtime._transport_car.last_chassis_target == {
        "source": "uart6",
        "vx": 3.0,
        "vy": 4.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert runtime._transport_car.control_state["angle"] == float(
        runtime._state_machine._boot_heading_deg + forward_runtime_module.MASTER_ORBIT_TARGET_DEG
    )


def test_master_forward_runtime_uses_configured_transport_hook_id_after_orbit(
    monkeypatch,
) -> None:
    """绕行结束后的主车视觉 hook 必须使用当前配置的搬运入口编号."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.MASTER_TRANSPORT_HOOK_CONFIG_ID = 9

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False

    runtime.step()

    assert "s,2,3,1,1,9\r\n" in uart6.messages


def test_master_forward_runtime_reapplies_uart6_search_velocity_after_orbit_finishes(
    monkeypatch,
) -> None:
    """绕行完成后, 主车重新接受本车视觉对正速度."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    uart6._buffer = b"v,3.0,4.0\n"

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_SEARCH_OBJECT
    assert runtime._transport_car.last_chassis_target == {
        "source": "uart6",
        "vx": 3.0,
        "vy": 4.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert ("handle_velocity", "uart6", 3.0, 4.0, 0.0) in events


def test_master_forward_runtime_orbit_uses_unified_entry_with_target_and_radius(monkeypatch) -> None:
    """主车进入 ORBITING 时读取主车绕行角度与半径参数并走统一入口."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.MASTER_ORBIT_TARGET_DEG = 135
    forward_runtime_module.MASTER_ORBIT_RADIUS_SCALE = 1.25

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40))
    runtime._transport_car.heading_est = 10.0
    runtime._state_machine._boot_heading_deg = 10.0
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"

    runtime.step()

    assert ("set_orbit_target", 145.0, 1.25) in events


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


def test_master_forward_runtime_does_not_emit_uart3_debug_line(monkeypatch) -> None:
    """主车运行时不向 UART3 输出调试行."""

    _events, uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, _uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0))

    runtime.step()

    assert uart3.messages == []



def test_master_forward_runtime_does_not_print_start_to_uart3_on_boot(monkeypatch) -> None:
    """主车运行时初始化不写 UART3."""

    _events, uart3, _uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, _uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    forward_runtime_module.MasterForwardRuntime()

    assert uart3.messages == []


def test_master_forward_runtime_does_not_enter_transport_before_front_half_finishes(
    monkeypatch,
) -> None:
    """前半段未跑完时, 收到 ALIGNED 不会进入搬运态."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,0\n" % EVENT_ALIGNED).encode()

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_SEARCH_OBJECT
    assert not any(
        message.startswith(
            "s,%d,%d,%d,%d"
            % (
                0,
                forward_runtime_module.ASSISTANT_TRANSPORT_SYNC_STATE,
                forward_runtime_module.ASSISTANT_TRANSPORT_SYNC_TARGET,
                forward_runtime_module.ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
            )
        )
        for message in uart8.messages
    )


def test_master_forward_runtime_enters_transport_after_both_aligned_and_applies_base_speed(
    monkeypatch,
) -> None:
    """主车和辅车都对正后进入搬运态并写入基础推进速度."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.TRANSPORT_FORWARD_SPEED = 3.0

    runtime = forward_runtime_module.MasterForwardRuntime(
        now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100, 120)
    )
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_SEARCH_OBJECT
    assert uart8.messages[-1] == "s,7,4,1,2\r\n"
    assert "a,13\r\n" in uart6.messages

    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_TRANSPORT_OBJECT
    assert ("handle_velocity", "master_transport", 0.0, 3.0, 0.0) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_transport",
        "vx": 0.0,
        "vy": 3.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert "a,13\r\n" in uart6.messages
    assert "a,15\r\n" in _reliable_messages(uart8)
    assert (
        "s,7,%d,%d,%d\r\n"
        % (
            forward_runtime_module.ASSISTANT_TRANSPORT_SYNC_STATE,
            forward_runtime_module.ASSISTANT_TRANSPORT_SYNC_TARGET,
            forward_runtime_module.ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
        )
    ) in _reliable_messages(uart8)


def test_master_forward_runtime_transport_adds_uart6_visual_correction(
    monkeypatch,
) -> None:
    """搬运态叠加主车本车视觉修正."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.TRANSPORT_FORWARD_SPEED = 3.0

    runtime = forward_runtime_module.MasterForwardRuntime(
        now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100, 120, 140)
    )
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    uart6._buffer = b"v,0.5,-0.25\n"

    runtime.step()

    assert ("handle_velocity", "master_transport", 0.5, 2.75, 0.0) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_transport",
        "vx": 0.5,
        "vy": 2.75,
        "omega": 0.0,
        "has_omega": False,
    }
    assert uart8.messages[-1] == "v,0.5,2.75,0.0\r\n"


def test_master_forward_runtime_transport_ignores_uart3_repl_input(
    monkeypatch,
) -> None:
    """搬运态 UART3 输入只留给 REPL."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.TRANSPORT_FORWARD_SPEED = 3.0

    runtime = forward_runtime_module.MasterForwardRuntime(
        now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100, 120, 140)
    )
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    event_count = len(events)
    uart3._buffer = b"v,9.0,8.0,0.7\n"

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_TRANSPORT_OBJECT
    assert ("handle_velocity", "uart3", 9.0, 8.0, 0.7) not in events[event_count:]
    assert uart3.any() > 0
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_transport",
        "vx": 0.0,
        "vy": 3.0,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_forward_runtime_transport_clears_stale_uart6_velocity_before_transport_ready(
    monkeypatch,
) -> None:
    """搬运待生效阶段不会把搜索残留视觉速度带入搬运态."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.TRANSPORT_FORWARD_SPEED = 3.0

    runtime = forward_runtime_module.MasterForwardRuntime(
        now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100, 120)
    )
    runtime.step()
    uart6._buffer = b"a,1\nv,0.5,-0.25\n"
    runtime.step()
    uart6._buffer = ("r,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_SEARCH_OBJECT
    assert runtime._latest_uart6_velocity is None
    assert not any(event[:2] == ("handle_velocity", "master_transport") for event in events)


def test_master_forward_runtime_transport_sync_sent_before_first_transport_feedforward(
    monkeypatch,
) -> None:
    """搬运同步先于首拍搬运前馈."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.TRANSPORT_FORWARD_SPEED = 3.0

    runtime = forward_runtime_module.MasterForwardRuntime(
        now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100, 120, 140)
    )
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()

    assert uart8.messages[-1] == "s,7,4,1,2\r\n"

    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_TRANSPORT_OBJECT
    assert uart8.messages[-1] == "v,0.0,3.0,0.0\r\n"


def test_master_forward_runtime_master_aligned_stops_before_transport(
    monkeypatch,
) -> None:
    """主车自己判定对正完成后先停住."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60, 80))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_SEARCH_OBJECT
    assert ("handle_velocity", "master_aligned_hold", 0.0, 0.0, 0.0) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_aligned_hold",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_master_forward_runtime_master_aligned_ignores_new_uart6_search_velocity(
    monkeypatch,
) -> None:
    """主车自己判定对正完成后不再继续跟物体."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100))
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    event_count = len(events)
    uart6._buffer = b"v,0.5,-0.25\n"

    runtime.step()

    assert ("handle_velocity", "uart6", 0.5, -0.25, 0.0) not in events[event_count:]
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_aligned_hold",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }


def test_master_forward_runtime_transport_ready_sends_finish_hook(
    monkeypatch,
) -> None:
    """主车进入正式搬运后向本车 UART6 下发搬运结束 hook."""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.TRANSPORT_FORWARD_SPEED = 3.0

    runtime = forward_runtime_module.MasterForwardRuntime(
        now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100, 120)
    )
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_TRANSPORT_OBJECT
    assert uart6.messages[-1] == _finish_hook_sync_message(forward_runtime_module)


def test_master_forward_runtime_arrived_event_enters_clear_phase_and_syncs_assistant_clear(
    monkeypatch,
) -> None:
    """主车收到搬运结束事件后先进入脱离阶段并同步辅车后退."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.TRANSPORT_FORWARD_SPEED = 3.0

    runtime = forward_runtime_module.MasterForwardRuntime(
        now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100, 120, 140)
    )
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    uart6._buffer = ("a,4\nr,17,4,%d,0\n" % forward_runtime_module.EVENT_ARRIVED).encode()

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_CLEAR_OBJECT
    assert ("handle_velocity", "master_wait_clear_ready", 0.0, 0.0, 0.0) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_wait_clear_ready",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": True,
    }
    assert "a,17\r\n" in uart6.messages
    assert (
        "s,9,%d,%d,%d\r\n"
        % (
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_STATE,
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_TARGET,
            forward_runtime_module.CLEAR_PHASE_RETREAT,
        )
    ) in _reliable_messages(uart8)


def test_master_forward_runtime_clear_sync_ack_starts_master_retreat_step(
    monkeypatch,
) -> None:
    """主车在辅车脱离同步确认后先沿自身 Y 负方向后退半步."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(
        now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100, 120, 140, 160)
    )
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    uart6._buffer = ("a,4\nr,17,4,%d,0\n" % forward_runtime_module.EVENT_ARRIVED).encode()
    runtime.step()
    uart8._buffer = b"a,9\n"

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_CLEAR_OBJECT
    assert (
        "set_relative_translation_target",
        0.0,
        -float(forward_runtime_module.TRANSPORT_CLEAR_RETREAT_DISTANCE_M),
        float(forward_runtime_module.TRANSPORT_CLEAR_RETREAT_MAX_SPEED),
    ) in events


def test_master_forward_runtime_retreat_completion_waits_assistant_cleared_before_turn_back(
    monkeypatch,
) -> None:
    """主车本车后退完成后仍等待辅车后退完成回报."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(
        now_ms=_FakeNowMs(0, 20, 40, 60, 80, 100, 120, 140, 160, 180)
    )
    runtime.step()
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    uart8._buffer = b"a,1\n"
    runtime.step()
    runtime._transport_car.command_lock = False
    runtime.step()
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    uart6._buffer = ("a,4\nr,17,4,%d,0\n" % forward_runtime_module.EVENT_ARRIVED).encode()
    runtime.step()
    uart8._buffer = b"a,9\n"
    runtime.step()
    runtime._transport_car.command_lock = False

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_CLEAR_OBJECT
    assert not any(
        message.startswith("s,11,%d,%d,%d" % (
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_STATE,
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_TARGET,
            forward_runtime_module.CLEAR_PHASE_FORWARD,
        ))
        for message in _reliable_messages(uart8)
    )
    assert not any(
        event[0] == "set_heading_transition_target"
        for event in events
        if isinstance(event, tuple)
    )


def test_master_forward_runtime_both_retreats_complete_then_start_turn_back(
    monkeypatch,
) -> None:
    """主辅都完成后退后, 主车立刻进入原地转身."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.MOTION_STOP_CONFIRM_TICKS = 2
    clock = _ManualNowMs(0)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=clock)
    runtime.step()
    clock.value = 20
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    clock.value = 40
    uart8._buffer = b"a,1\n"
    runtime.step()
    clock.value = 60
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 80
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    clock.value = 100
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    clock.value = 120
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    clock.value = 140
    uart6._buffer = ("a,4\nr,17,4,%d,0\n" % forward_runtime_module.EVENT_ARRIVED).encode()
    runtime.step()
    clock.value = 160
    uart8._buffer = b"a,9\n"
    runtime.step()
    clock.value = 180
    runtime._transport_car.command_lock = False
    uart8._buffer = ("r,19,%d,%d\n" % (
        EVENT_CLEARED,
        forward_runtime_module.CLEAR_PHASE_RETREAT,
    )).encode()

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_CLEAR_OBJECT
    assert not any(
        event[0] == "set_heading_transition_target" for event in events if isinstance(event, tuple)
    )

    _set_filtered_speeds(runtime._transport_car, 1.0, 1.0, 1.0)
    clock.value = 200
    runtime.step()

    assert not any(
        event[0] == "set_heading_transition_target" for event in events if isinstance(event, tuple)
    )

    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    clock.value = 220
    runtime.step()
    assert not any(
        event[0] == "set_heading_transition_target" for event in events if isinstance(event, tuple)
    )

    clock.value = 240
    runtime.step()

    assert (
        "set_heading_transition_target",
        float(forward_runtime_module.MASTER_TURN_BACK_DELTA_DEG),
    ) in events


def test_master_forward_runtime_turn_back_completion_syncs_forward_phase(
    monkeypatch,
) -> None:
    """主车转身完成后同步辅车进入前进阶段."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.MOTION_STOP_CONFIRM_TICKS = 2
    clock = _ManualNowMs(0)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=clock)
    runtime.step()
    clock.value = 20
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    clock.value = 40
    uart8._buffer = b"a,1\n"
    runtime.step()
    clock.value = 60
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 80
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    clock.value = 100
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    clock.value = 120
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    clock.value = 140
    uart6._buffer = ("a,4\nr,17,4,%d,0\n" % forward_runtime_module.EVENT_ARRIVED).encode()
    runtime.step()
    clock.value = 160
    uart8._buffer = b"a,9\n"
    runtime.step()
    clock.value = 180
    runtime._transport_car.command_lock = False
    uart8._buffer = ("r,19,%d,%d\n" % (
        EVENT_CLEARED,
        forward_runtime_module.CLEAR_PHASE_RETREAT,
    )).encode()
    runtime.step()
    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    clock.value = 200
    runtime.step()
    clock.value = 220
    runtime.step()
    assert any(
        event[0] == "set_heading_transition_target"
        for event in events
        if isinstance(event, tuple)
    )
    _set_filtered_speeds(runtime._transport_car, 1.0, 1.0, 1.0)
    clock.value = 240
    runtime._transport_car.command_lock = False

    runtime.step()

    assert (
        "s,11,%d,%d,%d\r\n"
        % (
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_STATE,
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_TARGET,
            forward_runtime_module.CLEAR_PHASE_FORWARD,
        )
    ) not in _reliable_messages(uart8)

    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    clock.value = 260
    runtime.step()
    assert (
        "s,11,%d,%d,%d\r\n"
        % (
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_STATE,
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_TARGET,
            forward_runtime_module.CLEAR_PHASE_FORWARD,
        )
    ) not in _reliable_messages(uart8)

    clock.value = 280
    runtime.step()

    assert (
        "s,11,%d,%d,%d\r\n"
        % (
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_STATE,
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_TARGET,
            forward_runtime_module.CLEAR_PHASE_FORWARD,
        )
    ) in _reliable_messages(uart8)


def test_master_forward_runtime_forward_sync_ack_starts_master_forward_step(
    monkeypatch,
) -> None:
    """主车在第二段脱离同步确认后按自身 Y 正方向前进."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.MOTION_STOP_CONFIRM_TICKS = 2
    clock = _ManualNowMs(0)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=clock)
    runtime.step()
    clock.value = 20
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    clock.value = 40
    uart8._buffer = b"a,1\n"
    runtime.step()
    clock.value = 60
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 80
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    clock.value = 100
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    clock.value = 120
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    clock.value = 140
    uart6._buffer = ("a,4\nr,17,4,%d,0\n" % forward_runtime_module.EVENT_ARRIVED).encode()
    runtime.step()
    clock.value = 160
    uart8._buffer = b"a,9\n"
    runtime.step()
    clock.value = 180
    runtime._transport_car.command_lock = False
    uart8._buffer = ("r,19,%d,%d\n" % (
        EVENT_CLEARED,
        forward_runtime_module.CLEAR_PHASE_RETREAT,
    )).encode()
    runtime.step()
    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    clock.value = 200
    runtime.step()
    clock.value = 220
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 240
    runtime.step()

    assert (
        "s,11,%d,%d,%d\r\n"
        % (
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_STATE,
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_TARGET,
            forward_runtime_module.CLEAR_PHASE_FORWARD,
        )
    ) in _reliable_messages(uart8)

    clock.value = 260
    uart8._buffer = b"a,11\n"
    runtime.step()

    assert (
        "set_relative_translation_target",
        0.0,
        float(forward_runtime_module.TRANSPORT_CLEAR_STEP_DISTANCE_M),
        float(forward_runtime_module.MASTER_TURN_BACK_DELTA_DEG),
    ) in events


def test_master_forward_runtime_forward_step_keeps_turn_back_target_heading(
    monkeypatch,
) -> None:
    """主车第二段前进应保持回身目标角, 不能改用转完时的当前角度."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.MOTION_STOP_CONFIRM_TICKS = 2
    clock = _ManualNowMs(0)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=clock)
    runtime.step()
    clock.value = 20
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    clock.value = 40
    uart8._buffer = b"a,1\n"
    runtime.step()
    clock.value = 60
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 80
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    clock.value = 100
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    clock.value = 120
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    clock.value = 140
    uart6._buffer = ("a,4\nr,17,4,%d,0\n" % forward_runtime_module.EVENT_ARRIVED).encode()
    runtime.step()
    clock.value = 160
    uart8._buffer = b"a,9\n"
    runtime.step()
    clock.value = 180
    runtime._transport_car.command_lock = False
    uart8._buffer = ("r,19,%d,%d\n" % (
        EVENT_CLEARED,
        forward_runtime_module.CLEAR_PHASE_RETREAT,
    )).encode()
    runtime.step()
    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    clock.value = 200
    runtime.step()
    clock.value = 220
    runtime.step()
    runtime._transport_car.heading_est = 210.0
    clock.value = 240
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 260
    runtime.step()

    assert (
        "s,11,%d,%d,%d\r\n"
        % (
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_STATE,
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_TARGET,
            forward_runtime_module.CLEAR_PHASE_FORWARD,
        )
    ) in _reliable_messages(uart8)

    clock.value = 280
    uart8._buffer = b"a,11\n"
    runtime.step()

    assert (
        "set_relative_translation_target",
        0.0,
        float(forward_runtime_module.TRANSPORT_CLEAR_STEP_DISTANCE_M),
        float(forward_runtime_module.MASTER_TURN_BACK_DELTA_DEG),
    ) in events


def test_master_forward_runtime_waits_after_master_forward_done_without_restarting_step(
    monkeypatch,
) -> None:
    """主车完成前进后等待辅车回报, 不重复启动本车前进."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.MOTION_STOP_CONFIRM_TICKS = 2
    clock = _ManualNowMs(0)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=clock)
    runtime.step()
    clock.value = 20
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    clock.value = 40
    uart8._buffer = b"a,1\n"
    runtime.step()
    clock.value = 60
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 80
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    clock.value = 100
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    clock.value = 120
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    clock.value = 140
    uart6._buffer = ("a,4\nr,17,4,%d,0\n" % forward_runtime_module.EVENT_ARRIVED).encode()
    runtime.step()
    clock.value = 160
    uart8._buffer = b"a,9\n"
    runtime.step()
    clock.value = 180
    runtime._transport_car.command_lock = False
    uart8._buffer = ("r,19,%d,%d\n" % (
        EVENT_CLEARED,
        forward_runtime_module.CLEAR_PHASE_RETREAT,
    )).encode()
    runtime.step()
    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    clock.value = 200
    runtime.step()
    clock.value = 220
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 240
    runtime.step()
    clock.value = 260
    uart8._buffer = b"a,11\n"
    runtime.step()

    forward_event = (
        "set_relative_translation_target",
        0.0,
        float(forward_runtime_module.TRANSPORT_CLEAR_STEP_DISTANCE_M),
        float(forward_runtime_module.MASTER_TURN_BACK_DELTA_DEG),
    )
    assert events.count(forward_event) == 1

    clock.value = 280
    runtime._transport_car.command_lock = False
    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    runtime.step()
    clock.value = 300
    runtime.step()
    clock.value = 320
    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_CLEAR_OBJECT
    assert events.count(forward_event) == 1


def test_master_forward_runtime_forward_completion_restarts_search_and_waits_follow_ack(
    monkeypatch,
) -> None:
    """第二段前进完成后直接重启搜索, 仍继续等待 follow 与本车 hook 确认."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.MOTION_STOP_CONFIRM_TICKS = 2
    clock = _ManualNowMs(0)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=clock)
    runtime.step()
    clock.value = 20
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    clock.value = 40
    uart8._buffer = b"a,1\n"
    runtime.step()
    clock.value = 60
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 80
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    clock.value = 100
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    clock.value = 120
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    clock.value = 140
    uart6._buffer = ("a,4\nr,17,4,%d,0\n" % forward_runtime_module.EVENT_ARRIVED).encode()
    runtime.step()
    clock.value = 160
    uart8._buffer = b"a,9\n"
    runtime.step()
    clock.value = 180
    runtime._transport_car.command_lock = False
    uart8._buffer = ("r,19,%d,%d\n" % (
        EVENT_CLEARED,
        forward_runtime_module.CLEAR_PHASE_RETREAT,
    )).encode()
    runtime.step()
    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    clock.value = 200
    runtime.step()
    clock.value = 220
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 240
    runtime.step()

    assert (
        "s,11,%d,%d,%d\r\n"
        % (
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_STATE,
            forward_runtime_module.ASSISTANT_CLEAR_SYNC_TARGET,
            forward_runtime_module.CLEAR_PHASE_FORWARD,
        )
    ) in _reliable_messages(uart8)

    clock.value = 260
    uart8._buffer = b"a,11\n"
    runtime.step()
    clock.value = 280
    runtime._transport_car.command_lock = False
    uart8._buffer = ("r,21,%d,%d\n" % (
        EVENT_CLEARED,
        forward_runtime_module.CLEAR_PHASE_FORWARD,
    )).encode()

    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_CLEAR_OBJECT

    _set_filtered_speeds(runtime._transport_car, 1.0, 1.0, 1.0)
    clock.value = 300
    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_CLEAR_OBJECT

    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    clock.value = 320
    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_CLEAR_OBJECT

    clock.value = 340
    runtime.step()

    assert runtime._state_machine.state == forward_runtime_module.STATE_SEARCH_OBJECT
    assert _hook_sync_message(forward_runtime_module, seq=5, context_id=5) in uart6.messages
    assert _assistant_sync_message(
        13,
        forward_runtime_module.ASSISTANT_FOLLOW_SYNC_STATE,
        forward_runtime_module.ASSISTANT_FOLLOW_SYNC_TARGET,
        0,
    ) in _reliable_messages(uart8)
    assert "a,21\r\n" in _reliable_messages(uart8)
    event_count = len(events)
    clock.value = 360
    uart6._buffer = b"v,3.0,4.0\n"
    runtime.step()

    assert ("handle_velocity", "uart6", 3.0, 4.0, 0.0) not in events[event_count:]

    clock.value = 380
    uart8._buffer = b"a,13\n"
    runtime.step()

    clock.value = 400
    uart6._buffer = b"v,3.0,4.0\n"
    runtime.step()

    assert ("handle_velocity", "uart6", 3.0, 4.0, 0.0) not in events[event_count:]

    clock.value = 420
    uart6._buffer = b"a,5\n"
    runtime.step()

    clock.value = 440
    uart6._buffer = b"v,3.0,4.0\n"
    runtime.step()

    assert ("handle_velocity", "uart6", 3.0, 4.0, 0.0) in events


def test_master_forward_runtime_turn_back_wait_is_non_blocking(monkeypatch) -> None:
    """转身阶段按拍检查锁定状态, 不阻塞控制周期."""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.MOTION_STOP_CONFIRM_TICKS = 2
    clock = _ManualNowMs(0)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=clock)
    runtime.step()
    clock.value = 20
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    clock.value = 40
    uart8._buffer = b"a,1\n"
    runtime.step()
    clock.value = 60
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 80
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    clock.value = 100
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    clock.value = 120
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    clock.value = 140
    uart6._buffer = ("a,4\nr,17,4,%d,0\n" % forward_runtime_module.EVENT_ARRIVED).encode()
    runtime.step()
    clock.value = 160
    uart8._buffer = b"a,9\n"
    runtime.step()
    clock.value = 180
    runtime._transport_car.command_lock = False
    uart8._buffer = ("r,19,%d,%d\n" % (
        EVENT_CLEARED,
        forward_runtime_module.CLEAR_PHASE_RETREAT,
    )).encode()
    runtime.step()
    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    clock.value = 200
    runtime.step()

    transport_step_count = events.count("transport_step")

    clock.value = 220
    runtime.step()

    assert events.count("transport_step") == transport_step_count + 1
    assert runtime._state_machine.state == forward_runtime_module.STATE_CLEAR_OBJECT
    assert any(
        event[0] == "set_heading_transition_target" for event in events if isinstance(event, tuple)
    )


def test_master_forward_runtime_does_not_print_turn_heading_to_uart3_while_turn_back_active(
    monkeypatch,
) -> None:
    """主车转身阶段不向 UART3 输出当前角度调试信息."""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    _uart6_calls, uart6 = install_fake_uart6_factory(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    forward_runtime_module.MOTION_STOP_CONFIRM_TICKS = 2
    clock = _ManualNowMs(0)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=clock)
    runtime.step()
    clock.value = 20
    uart6._buffer = ("a,1\nr,7,1,%d,300\n" % EVENT_TARGET_FOUND).encode()
    runtime.step()
    clock.value = 40
    uart8._buffer = b"a,1\n"
    runtime.step()
    clock.value = 60
    runtime._transport_car.command_lock = False
    runtime.step()
    clock.value = 80
    uart8._buffer = b"a,3\nr,11,6,300\n"
    runtime.step()
    clock.value = 100
    uart6._buffer = ("a,2\nr,13,3,%d,0\n" % EVENT_ALIGNED).encode()
    uart8._buffer = ("r,15,%d,0\n" % EVENT_ALIGNED).encode()
    runtime.step()
    clock.value = 120
    uart8._buffer = b"a,7\n"
    uart6._buffer = b"a,3\n"
    runtime.step()
    clock.value = 140
    uart6._buffer = ("a,4\nr,17,4,%d,0\n" % forward_runtime_module.EVENT_ARRIVED).encode()
    runtime.step()
    clock.value = 160
    uart8._buffer = b"a,9\n"
    runtime.step()
    clock.value = 180
    runtime._transport_car.command_lock = False
    uart8._buffer = ("r,19,%d,%d\n" % (
        EVENT_CLEARED,
        forward_runtime_module.CLEAR_PHASE_RETREAT,
    )).encode()
    runtime.step()
    _set_filtered_speeds(runtime._transport_car, 0.0, 0.0, 0.0)
    clock.value = 200
    runtime.step()
    clock.value = 220
    runtime.step()

    runtime._transport_car.heading_est = 33.5
    clock.value = 240
    runtime.step()

    assert uart3.messages == []

    runtime._transport_car.heading_est = 35.0
    clock.value = 260
    runtime.step()

    assert uart3.messages == []
