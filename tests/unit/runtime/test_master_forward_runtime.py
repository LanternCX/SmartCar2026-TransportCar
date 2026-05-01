"""! @file tests/unit/runtime/test_master_forward_runtime.py
@brief 主车角色运行时短包协议行为测试
"""

from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Optional
import sys



PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"


def import_master_module(module_name: str, monkeypatch):
    """! @brief 按正常包路径导入主车视觉运行模块"""

    monkeypatch.syspath_prepend(str(SRC_ROOT))
    for loaded_name in ("vision.master", "vision.master.forward_runtime", module_name):
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
    """! @brief 注入共享底盘最小桩对象"""

    events = []
    core_package = ModuleType("core")
    core_module = ModuleType("core.runtime")
    hardware_package = ModuleType("hardware")
    uart_bus_module = ModuleType("hardware.uart_bus")
    uart3 = _FakeUart()
    uart8 = _FakeUart()
    uart6 = _FakeUart()

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
    setattr(uart_bus_module, "create_uart6", lambda: uart6)
    monkeypatch.setitem(sys.modules, "hardware", hardware_package)
    monkeypatch.setitem(sys.modules, "hardware.uart_bus", uart_bus_module)
    return events, uart3, uart8


def install_fake_uart6_factory(monkeypatch, uart6, calls) -> None:
    """! @brief 注入视觉串口工厂桩"""

    hardware_package = ModuleType("hardware")
    uart_bus_module = ModuleType("hardware.uart_bus")

    def create_uart6():
        calls.append("create_uart6")
        return uart6

    setattr(uart_bus_module, "create_uart6", create_uart6)
    monkeypatch.setitem(sys.modules, "hardware", hardware_package)
    monkeypatch.setitem(sys.modules, "hardware.uart_bus", uart_bus_module)


def test_master_forward_runtime_keeps_remote_control_surface(monkeypatch) -> None:
    """! @brief 主车角色运行时维持启动壳依赖的对外外观"""

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
    """! @brief 主车角色运行时先进入角色层周期边界再驱动共享底盘"""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime()
    runtime._run_role_cycle = lambda: events.append("role_cycle")

    keep_running = runtime.step()

    assert keep_running is False
    assert events.index("role_cycle") < events.index("transport_step")


def test_master_package_entry_builds_forward_runtime(monkeypatch) -> None:
    """! @brief 主车包入口给启动壳创建主车角色运行时对象"""

    install_fake_transport_car(monkeypatch)
    master_module = import_master_module("vision.master", monkeypatch)

    runtime = master_module.create_transport_car()

    assert hasattr(runtime, "step")
    assert runtime.imu == "imu"


def test_master_forward_runtime_applies_remote_v_packet_to_local_chassis(monkeypatch) -> None:
    """! @brief UART3 收到速度短包后仍进入主车本地速度入口"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,1.0,-2.5,0.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert ("handle_velocity", "uart3", 1.0, -2.5, 0.5) in events
    assert runtime._transport_car.last_chassis_target["source"] == "uart3"
    assert ("handle_uart_line", "uart3", "v,1.0,-2.5,0.5") not in events


def test_master_forward_runtime_enters_search_on_role_cycle(monkeypatch) -> None:
    """! @brief 主车角色周期主动进入搜索状态并下发 hook 同步"""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime.search_state == forward_runtime_module.SEARCH_OBJECT
    assert runtime._uart6.messages == [
        "s,1,1,1,1,%d\r\n" % forward_runtime_module._params.MASTER_SEARCH_HOOK_CONFIG_ID
    ]
    assert ("handle_velocity", "master_search", 0.0, 0.0, 0.0) in events




def test_master_forward_runtime_uses_uart6_vision_velocity_in_search(monkeypatch) -> None:
    """! @brief SEARCH_OBJECT 中消费 UART6 视觉速度并写入本车底盘"""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime()
    runtime._uart6._buffer = b"v,0.2,-0.1\n"

    runtime.step()

    assert ("handle_velocity", "master_vision", 0.2, -0.1, 0.0) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_vision",
        "vx": 0.2,
        "vy": -0.1,
        "omega": 0.0,
        "has_omega": False,
    }


def test_master_forward_runtime_does_not_forward_uart6_vision_velocity_to_uart8(monkeypatch) -> None:
    """! @brief 主车视觉 v 包只服务本车搜索, 不转发 UART8"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime()
    runtime._uart6._buffer = b"v,0.2,-0.1\n"

    runtime.step()

    assert uart8.messages == []


def test_master_forward_runtime_prefers_uart3_velocity_over_uart6_vision_in_same_cycle(monkeypatch) -> None:
    """! @brief 同拍存在 UART3 速度时优先使用 UART3 并继续转发 UART8"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,0.8,0.4,0.3\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime()
    runtime._uart6._buffer = b"v,0.2,-0.1\n"

    runtime.step()

    assert runtime._transport_car.last_chassis_target == {
        "source": "uart3",
        "vx": 0.8,
        "vy": 0.4,
        "omega": 0.3,
        "has_omega": True,
    }
    assert ("handle_velocity", "master_vision", 0.2, -0.1, 0.0) not in events
    assert uart8.messages == ["v,0.8,0.4,0.3\r\n"]


def test_master_forward_runtime_object_found_ignores_uart6_vision_velocity_and_outputs_zero(monkeypatch) -> None:
    """! @brief OBJECT_FOUND 忽略主车视觉速度并输出零平移速度"""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime()
    runtime.start_search()
    runtime._search.handle_event({
        "context_id": runtime._search.context_id,
        "event": 6,
        "value": 99,
    })
    runtime._uart6._buffer = b"v,0.2,-0.1\n"

    runtime.step()

    assert runtime.search_state == forward_runtime_module.OBJECT_FOUND
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_search",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert ("handle_velocity", "master_vision", 0.2, -0.1, 0.0) not in events


def test_master_forward_runtime_clears_vision_velocity_when_target_found_before_late_v(monkeypatch) -> None:
    """! @brief TARGET_FOUND 后同批到达的视觉速度不会残留为搜索输入"""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)
    runtime.start_search()
    runtime.step()

    runtime._uart6._buffer = b"r,7,1,6,90\nv,0.2,-0.1\n"
    runtime.step()

    assert runtime.search_state == forward_runtime_module.OBJECT_FOUND
    assert runtime._latest_search_velocity is None
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_search",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": False,
    }
    assert ("handle_velocity", "master_vision", 0.2, -0.1, 0.0) not in events


def test_master_forward_runtime_search_without_uart6_vision_velocity_outputs_zero(monkeypatch) -> None:
    """! @brief 搜索态没有视觉速度时输出零平移速度, 不再使用固定搜索速度"""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)

    runtime.step()

    assert runtime.search_state == forward_runtime_module.SEARCH_OBJECT
    assert ("handle_velocity", "master_search", 0.0, 0.0, 0.0) in events
    assert runtime._transport_car.last_chassis_target == {
        "source": "master_search",
        "vx": 0.0,
        "vy": 0.0,
        "omega": 0.0,
        "has_omega": False,
    }

def test_master_forward_runtime_requires_structured_velocity_entry(monkeypatch) -> None:
    """! @brief 主车速度短包只调用共享底盘结构化速度入口"""

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
    """! @brief UART3 收到速度短包后, 主车 UART8 前馈输出与遥控输入保持一致"""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,1,-2.50,0.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["v,1,-2.50,0.5\r\n"]


def test_master_forward_runtime_does_not_sleep_for_v_packet_forward(monkeypatch) -> None:
    """! @brief UART3 速度短包转发不触发可靠包延时"""

    _events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,1,-2.50,0.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    reliable_writes = []
    monkeypatch.setattr(
        forward_runtime_module.protocol_link,
        "write_reliable_line",
        lambda uart, line: reliable_writes.append((uart, line)),
    )

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert not any(uart is uart8 for uart, _line in reliable_writes)


def test_master_forward_runtime_accepts_v_packet_without_omega(monkeypatch) -> None:
    """! @brief 无 omega 的速度短包本地角速度按零量执行"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,1.0,-2.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == ["v,1.0,-2.5\r\n"]
    assert ("handle_velocity", "uart3", 1.0, -2.5, 0.0) in events


def test_master_forward_runtime_rejects_non_short_packet_velocity_forward(monkeypatch) -> None:
    """! @brief 非短包速度文本不能作为主车正式转发入口"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"vx=1.0,vy=2.0\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == []
    assert ("handle_velocity", "uart3", 1.0, 2.0, 0.0) not in events


def test_master_forward_runtime_does_not_derive_angle_from_omega(monkeypatch) -> None:
    """! @brief 主车不会把角速度字段派生为 angle 转发"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"omega=0.5\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == []
    assert ("handle_uart_line", "uart3", "omega=0.5") not in events


def test_master_forward_runtime_ignores_non_short_packet_text(monkeypatch) -> None:
    """! @brief 主车角色层只处理正式短包, 非短包文本不进入控制入口"""

    events, uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"omega=0.5\nx=1.0,y=2.0\ntext\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    runtime.step()

    assert uart8.messages == []
    assert ("handle_uart_line", "uart3", "omega=0.5") not in events
    assert ("handle_uart_line", "uart3", "x=1.0,y=2.0") not in events
    assert ("handle_uart_line", "uart3", "text") not in events


def test_master_forward_runtime_assembles_local_vision_uart6(monkeypatch) -> None:
    """! @brief 主车角色层装配本车视觉链路"""

    events, uart3, _uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,0,0,0\n"
    uart6 = _FakeUart()
    uart6_calls = []
    install_fake_uart6_factory(monkeypatch, uart6, uart6_calls)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)

    runtime = forward_runtime_module.MasterForwardRuntime()

    keep_running = runtime.step()

    assert keep_running is False
    assert uart6_calls == ["create_uart6"]
    assert ("handle_velocity", "uart3", 0.0, 0.0, 0.0) in events


def test_master_forward_runtime_sends_search_hook_sync_on_uart6(monkeypatch) -> None:
    """! @brief 进入搜索态后通过 UART6 发送视觉 hook 同步包"""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)
    runtime.start_search()

    runtime.step()

    assert runtime.search_state == forward_runtime_module.SEARCH_OBJECT
    assert runtime._uart6.messages == ["s,1,1,1,1,%d\r\n" % forward_runtime_module._params.MASTER_SEARCH_HOOK_CONFIG_ID]


def test_master_forward_runtime_keeps_uart3_velocity_owner_during_search(monkeypatch) -> None:
    """! @brief 搜索已启动时, 同拍 UART3 速度输入仍拥有底盘控制权"""

    events, uart3, _uart8 = install_fake_transport_car(monkeypatch)
    uart3._buffer = b"v,0.2,-0.1,0.0\n"
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)
    runtime.start_search()

    runtime.step()

    assert ("handle_velocity", "uart3", 0.2, -0.1, 0.0) in events
    assert runtime._transport_car.last_chassis_target["source"] == "uart3"


def test_master_forward_runtime_writes_search_velocity_without_uart3_input(monkeypatch) -> None:
    """! @brief 搜索已启动且无 UART3 速度输入时, 状态机写出搜索速度"""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)
    runtime.start_search()

    runtime.step()

    assert ("handle_velocity", "master_search", 0.0, 0.0, 0.0) in events
    assert runtime._transport_car.last_chassis_target["source"] == "master_search"


def test_master_forward_runtime_resends_search_hook_until_matching_ack(monkeypatch) -> None:
    """! @brief 视觉 hook 同步包只在收到匹配确认后停止重发"""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    now_ms = [100]
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: now_ms[0])
    runtime.start_search()

    runtime.step()
    runtime._uart6._buffer = b"a,99\n"
    runtime.step()
    now_ms[0] += forward_runtime_module._params.RELIABLE_RESEND_INTERVAL_MS
    runtime.step()
    runtime._uart6._buffer = b"a,1\n"
    runtime.step()
    now_ms[0] += forward_runtime_module._params.RELIABLE_RESEND_INTERVAL_MS
    runtime.step()

    sync_line = "s,1,1,1,1,%d\r\n" % forward_runtime_module._params.MASTER_SEARCH_HOOK_CONFIG_ID
    assert runtime._uart6.messages.count(sync_line) == 2


def test_master_forward_runtime_clears_unacked_search_hook_after_target_found(monkeypatch) -> None:
    """! @brief 匹配 TARGET_FOUND 到达后停止重发搜索 hook 同步包"""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    now_ms = [100]
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: now_ms[0])
    runtime.start_search()

    runtime.step()
    runtime._uart6._buffer = b"r,7,1,6,90\n"
    runtime.step()
    now_ms[0] += forward_runtime_module._params.RELIABLE_RESEND_INTERVAL_MS
    runtime.step()

    sync_line = "s,1,1,1,1,%d\r\n" % forward_runtime_module._params.MASTER_SEARCH_HOOK_CONFIG_ID
    assert runtime.search_state == forward_runtime_module.OBJECT_FOUND
    assert runtime._uart6.messages.count(sync_line) == 1


def test_master_forward_runtime_acks_uart6_target_found_and_stops(monkeypatch) -> None:
    """! @brief UART6 匹配上下文 TARGET_FOUND 事件会被确认并触发停车"""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)
    runtime.start_search()
    runtime.step()

    runtime._uart6._buffer = b"r,7,1,6,90\n"
    runtime.step()
    runtime._uart6._buffer = b"r,7,1,6,90\n"
    runtime.step()

    assert runtime.search_state == forward_runtime_module.OBJECT_FOUND
    assert runtime._uart6.messages[-2:] == ["a,7\r\n", "a,7\r\n"]
    assert events.count(("handle_velocity", "master_search", 0.0, 0.0, 0.0)) == 3
    assert runtime._transport_car.last_chassis_target["has_omega"] is False
    assert runtime.search_transition_count == 1


def test_master_forward_runtime_keeps_uart3_velocity_owner_after_found(monkeypatch) -> None:
    """! @brief 已找到物体后, 同拍 UART3 速度输入仍拥有底盘控制权"""

    events, uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)
    runtime.start_search()
    runtime.step()
    runtime._uart6._buffer = b"r,7,1,6,90\n"
    runtime.step()

    uart3._buffer = b"v,0.3,0.4,0.0\n"
    runtime.step()

    assert runtime.search_state == forward_runtime_module.OBJECT_FOUND
    assert ("handle_velocity", "uart3", 0.3, 0.4, 0.0) in events
    assert runtime._transport_car.last_chassis_target["source"] == "uart3"


def test_master_forward_runtime_ignores_nonmatching_target_found(monkeypatch) -> None:
    """! @brief UART6 非匹配上下文 TARGET_FOUND 不触发搜索状态跳转"""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)
    runtime.start_search()
    runtime.step()

    runtime._uart6._buffer = b"r,7,2,6,90\n"
    runtime.step()

    assert runtime.search_state == forward_runtime_module.SEARCH_OBJECT
    assert runtime._uart6.messages[-1] == "a,7\r\n"


def test_master_forward_runtime_ignores_uart6_observation(monkeypatch) -> None:
    """! @brief 主车视觉观测包不进入主车搜索控制链路"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)
    runtime.start_search()
    runtime.step()
    uart8.messages.clear()

    runtime._uart6._buffer = b"o,1,0.0,0.0,99.0\n"
    runtime.step()

    assert not hasattr(runtime._search, "last_observation")
    assert uart8.messages == []
    assert runtime._transport_car.last_exception_text == "none"


def test_master_forward_runtime_does_not_call_state_machine_for_uart6_observation(monkeypatch) -> None:
    """! @brief UART6 观测包不会进入状态机入口"""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)
    runtime.start_search()
    runtime.step()
    runtime._search.handle_observation = lambda _packet: (_ for _ in ()).throw(
        AssertionError("observation must not reach state machine")
    )

    runtime._uart6._buffer = b"o,1,1.0,0.0,10.0\no,1,2.0,0.0,20.0\no,1,3.0,0.0,30.0\n"
    runtime.step()

    assert runtime._transport_car.last_exception_text == "none"


def test_master_forward_runtime_skips_sync_resend_after_event_ack_in_same_cycle(
    monkeypatch,
) -> None:
    """! @brief 同一控制拍已发送事件确认时跳过视觉同步包重发"""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    now_ms = [100]
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: now_ms[0])
    runtime.start_search()
    runtime.step()
    now_ms[0] += forward_runtime_module._params.RELIABLE_RESEND_INTERVAL_MS

    runtime._uart6._buffer = b"r,7,2,6,90\n"
    runtime.step()

    sync_line = "s,1,1,1,1,%d\r\n" % forward_runtime_module._params.MASTER_SEARCH_HOOK_CONFIG_ID
    assert runtime._uart6.messages[-1] == "a,7\r\n"
    assert runtime._uart6.messages.count(sync_line) == 1


def test_master_forward_runtime_does_not_reliable_write_for_uart6_observation(monkeypatch) -> None:
    """! @brief UART6 观测包不触发可靠写出"""

    _events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    forward_runtime_module = import_master_module("vision.master.forward_runtime", monkeypatch)
    runtime = forward_runtime_module.MasterForwardRuntime(now_ms=lambda: 100)
    runtime.start_search()
    runtime.step()
    runtime._uart6._buffer = b"a,1\n"
    runtime.step()
    reliable_writes = []
    monkeypatch.setattr(
        forward_runtime_module.protocol_link,
        "write_reliable_line",
        lambda uart, line: reliable_writes.append((uart, line)),
    )

    runtime._uart6._buffer = b"o,1,0.0,0.0,99.0\n"
    runtime.step()

    assert not hasattr(runtime._search, "last_observation")
    assert reliable_writes == []
