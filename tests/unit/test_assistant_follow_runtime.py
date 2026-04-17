"""辅车角色运行时最小行为测试.

@file tests/unit/test_assistant_follow_runtime.py
"""

from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Optional
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"


def import_assistant_module(module_name: str, monkeypatch):
    """按正常包路径导入辅车视觉运行模块."""

    monkeypatch.syspath_prepend(str(SRC_ROOT))
    for loaded_name in (
        "vision.assistant",
        "vision.assistant.follow_runtime",
        module_name,
    ):
        sys.modules.pop(loaded_name, None)
    return import_module(module_name)


class _FakeUart:
    def __init__(self, incoming_lines=()) -> None:
        self._buffer = "".join("%s\n" % line for line in incoming_lines).encode()
        self.messages = []
        self.read_error: Optional[BaseException] = None

    def any(self) -> int:
        return len(self._buffer)

    def read(self, size: int) -> bytes:
        if self.read_error is not None:
            raise self.read_error
        chunk = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return chunk

    def write(self, text) -> None:
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
            self.ticker = None
            self.uart3 = uart3
            self.uart8 = uart8
            self.last_cmd = {"x": 9.0, "y": 8.0, "angle": 7.0}
            self.rear_only_mode = False
            self.command_lock = False
            self.command_mode = "none"
            self._process_uart = self._original_process_uart

        def _original_process_uart(self) -> None:
            events.append("transport_process_uart")

        def mark_tick(self, tick=None) -> None:
            events.append(("mark_tick", tick))

        def set_ticker(self, ticker_obj) -> None:
            self.ticker = ticker_obj
            events.append(("set_ticker", ticker_obj))

        def step(self) -> bool:
            events.append("transport_step")
            return False

        def _handle_uart_line(self, line: str, source: str) -> None:
            events.append(("handle_uart_line", source, line))
            dispatched = set()
            for fragment in line.split(","):
                item = fragment.strip()
                if not item or "=" not in item:
                    continue
                key, value_text = item.split("=", 1)
                key = key.strip()
                value_text = value_text.strip()
                if key in ("vx", "vy", "omega"):
                    self.last_cmd[key] = float(value_text)
                    dispatched.add(key)
                if key in ("x", "y", "angle"):
                    self.last_cmd[key] = float(value_text)
                    dispatched.add(key)
                if key in ("x", "y"):
                    self.last_cmd.pop("vx", None)
                    self.last_cmd.pop("vy", None)
                if key == "angle":
                    self.last_cmd.pop("omega", None)
                if key == "rear":
                    self.rear_only_mode = value_text == "1"
                    self.command_lock = self.rear_only_mode
                    self.command_mode = "locked" if self.rear_only_mode else "none"
                    dispatched.add(key)
            if dispatched:
                self._finalize_route(dispatched)

        def _finalize_route(self, dispatched) -> None:
            events.append(("finalize_route", tuple(sorted(dispatched))))
            if "vx" in dispatched or "vy" in dispatched or "omega" in dispatched:
                self.last_cmd.pop("x", None)
                self.last_cmd.pop("y", None)
                self.last_cmd.pop("angle", None)
                self.command_lock = False
                self.command_mode = "none"

        def build_health_snapshot(self) -> dict:
            return {"alive": 1, "last_err": "none"}

        def get_query_uart(self):
            return self.uart3

    monkeypatch.setitem(sys.modules, "core", core_package)
    setattr(core_module, "TransportCar", _TransportCar)
    monkeypatch.setitem(sys.modules, "core.runtime", core_module)
    return events, uart3, uart8


def install_fake_uart6_factory(monkeypatch, uart6: _FakeUart) -> None:
    hardware_package = ModuleType("hardware")
    uart_bus_module = ModuleType("hardware.uart_bus")

    def create_uart6():
        return uart6

    setattr(uart_bus_module, "create_uart6", create_uart6)
    monkeypatch.setitem(sys.modules, "hardware", hardware_package)
    monkeypatch.setitem(sys.modules, "hardware.uart_bus", uart_bus_module)


def test_assistant_follow_runtime_keeps_remote_control_surface(monkeypatch) -> None:
    """辅车角色运行时要保留启动壳依赖的对外外观."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime()
    ticker_obj = object()

    runtime.mark_tick(12)
    runtime.set_ticker(ticker_obj)

    assert runtime.wheel_states == [{"encoder": "enc-left"}, {"encoder": "enc-right"}]
    assert runtime.imu == "imu"
    assert hasattr(runtime, "step")
    assert events[:2] == [("mark_tick", 12), ("set_ticker", ticker_obj)]


def test_assistant_follow_runtime_step_runs_role_cycle_boundary(monkeypatch) -> None:
    """辅车角色运行时的 step 要先进入角色层周期边界再驱动共享底盘."""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )
    runtime = follow_runtime_module.AssistantFollowRuntime()
    runtime._run_role_cycle = lambda: events.append("role_cycle")

    keep_running = runtime.step()

    assert keep_running is False
    assert events == ["role_cycle", "transport_step"]


def test_assistant_follow_runtime_keeps_transport_uart3_processing_active(
    monkeypatch,
) -> None:
    """辅车角色层接管 UART8 后，不应顺手屏蔽共享底盘自己的 UART3 输入链。"""

    events, _uart3, _uart8 = install_fake_transport_car(monkeypatch)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime()
    runtime._transport_car._process_uart()

    assert events == ["transport_process_uart"]


def test_assistant_package_entry_builds_follow_runtime(monkeypatch) -> None:
    """辅车包入口要继续给启动壳创建辅车角色运行时对象."""

    install_fake_transport_car(monkeypatch)
    assistant_module = import_assistant_module("vision.assistant", monkeypatch)

    runtime = assistant_module.create_transport_car()

    assert runtime.__class__.__name__ == "AssistantFollowRuntime"


def test_assistant_follow_runtime_prioritizes_role_inputs_and_routes_effective_speed_through_transport(
    monkeypatch,
) -> None:
    """辅车角色层要保留前馈和视觉修正，但最终速度仍走共享底盘入口。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0\n?health\nrear=1\n"
    uart6 = _FakeUart(["x=0.5,y=-0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime()

    keep_running = runtime.step()

    assert keep_running is False
    assert ("handle_uart_line", "uart8", "vx=1.0") not in events
    assert ("handle_uart_line", "uart6", "x=0.5,y=-0.25") not in events
    assert ("handle_uart_line", "uart8", "?health") in events
    assert ("handle_uart_line", "uart8", "rear=1") in events
    assert runtime._transport_car.last_cmd == {"vx": 1.5, "vy": -0.25, "omega": 0.0}
    assert runtime._transport_car.rear_only_mode is True
    assert runtime._transport_car.command_lock is False
    assert runtime._transport_car.command_mode == "none"


def test_assistant_follow_runtime_routes_corrected_speed_through_transport_when_vision_is_present(
    monkeypatch,
) -> None:
    """视觉输入存在时，修正后的速度也必须通过共享底盘入口生效。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0,vy=-2.0,omega=0.5\n"
    uart6 = _FakeUart(["x=0.5,y=-0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert ("handle_uart_line", "uart8", "vx=1.0,vy=-2.0,omega=0.5") not in events
    assert ("handle_uart_line", "uart8", "vx=1.5,vy=-2.25,omega=0.5") in events
    assert runtime._transport_car.last_cmd == {"vx": 1.5, "vy": -2.25, "omega": 0.5}


def test_assistant_follow_runtime_keeps_last_uart8_velocity_without_old_timeout(
    monkeypatch,
) -> None:
    """UART8 速度命令应像 UART3 一样持续生效，不能沿用旧的超时清零语义。"""

    class _FakeClock:
        def __init__(self, initial_ms: int = 0) -> None:
            self.now_ms = initial_ms

        def advance(self, delta_ms: int) -> None:
            self.now_ms += delta_ms

        def __call__(self) -> int:
            return self.now_ms

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    clock = _FakeClock(100)
    uart8._buffer = b"vx=2.0,omega=0.5\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=clock)

    runtime.step()
    clock.advance(200)
    runtime.step()

    assert events[-1] == "transport_step"
    assert runtime._transport_car.last_cmd == {"vx": 2.0, "vy": 0.0, "omega": 0.5}


def test_assistant_follow_runtime_exposes_follow_diagnostics_snapshot(
    monkeypatch,
) -> None:
    """辅车角色运行时要暴露当前生效速度和本地视觉观测状态。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=2.0,omega=1.0\n"
    uart6 = _FakeUart(["x=-0.5,y=0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert events[-1] == "transport_step"
    assert snapshot["state"] == "active"
    assert snapshot["transport_command"] == {"vx": 1.5, "vy": 0.25, "omega": 1.0}
    assert snapshot["uart8_input_status"] == "active"
    assert snapshot["vision_input"] == {
        "valid": True,
        "x": -0.5,
        "y": 0.25,
        "timestamp_ms": 100,
        "age_ms": 0,
    }
    assert snapshot["vision_input_status"] == "active"
    assert snapshot["last_error_text"] == "none"


def test_assistant_follow_runtime_keeps_feedforward_when_vision_is_missing(
    monkeypatch,
) -> None:
    """UART6 没有观测时，UART8 速度包要按共享底盘原生语义直接生效。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=2.0,vy=-1.0,omega=0.5\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert events[-1] == "transport_step"
    assert runtime._transport_car.last_cmd == {"vx": 2.0, "vy": -1.0, "omega": 0.5}
    assert snapshot["state"] == "active"
    assert snapshot["transport_command"] == {"vx": 2.0, "vy": -1.0, "omega": 0.5}
    assert snapshot["vision_input"]["valid"] is False
    assert snapshot["vision_input_status"] == "idle"


def test_assistant_follow_runtime_routes_velocity_back_through_transport_when_vision_is_missing(
    monkeypatch,
) -> None:
    """无视觉时的速度写回仍要走共享底盘入口，而不是角色层直写内部状态。"""

    _events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=2.0,vy=-1.0,omega=0.5\n"
    uart6 = _FakeUart()
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    routed = []

    def routed_handle(line: str, source: str) -> None:
        routed.append((source, line))
        dispatched = set()
        for fragment in line.split(","):
            item = fragment.strip()
            if not item or "=" not in item:
                continue
            key, value_text = item.split("=", 1)
            key = key.strip()
            if key not in ("vx", "vy", "omega"):
                continue
            runtime._transport_car.last_cmd[key] = float(value_text)
            dispatched.add(key)
        if dispatched:
            runtime._transport_car._finalize_route(dispatched)

    monkeypatch.setattr(runtime._transport_car, "_handle_uart_line", routed_handle)
    runtime._transport_car.command_lock = True
    runtime._transport_car.command_mode = "locked"

    runtime.step()

    assert routed == [("uart8", "vx=2.0,vy=-1.0,omega=0.5")]
    assert runtime._transport_car.last_cmd == {"vx": 2.0, "vy": -1.0, "omega": 0.5}
    assert runtime._transport_car.command_lock is False
    assert runtime._transport_car.command_mode == "none"


def test_assistant_follow_runtime_intercepts_velocity_fields_inside_mixed_uart8_packet(
    monkeypatch,
) -> None:
    """混合包里的速度字段要先被角色层接管，再把修正后的速度交回共享底盘。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0,vy=2.0,rear=1\n"
    uart6 = _FakeUart(["x=0.25,y=0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()

    assert ("handle_uart_line", "uart8", "vx=1.0") not in events
    assert ("handle_uart_line", "uart8", "vy=2.0") not in events
    assert ("handle_uart_line", "uart8", "vx=1.0,vy=2.0,rear=1") not in events
    assert ("handle_uart_line", "uart8", "rear=1") in events
    assert runtime._transport_car.last_cmd == {"vx": 1.25, "vy": 2.5, "omega": 0.0}
    assert runtime._transport_car.rear_only_mode is True


def test_assistant_follow_runtime_keeps_running_and_records_uart_errors(
    monkeypatch,
) -> None:
    """串口读取异常不能把角色层 step 炸掉，并且要留下最小错误信息。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"broken"
    uart8.read_error = ValueError("uart8 boom")
    uart6 = _FakeUart()
    uart6._buffer = b"\xff\n"
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    keep_running = runtime.step()
    snapshot = runtime.build_follow_snapshot()

    assert keep_running is False
    assert events[-1] == "transport_step"
    assert runtime._transport_car.last_cmd == {"x": 9.0, "y": 8.0, "angle": 7.0}
    assert snapshot["state"] == "idle"
    assert snapshot["uart8_input_status"] == "error"
    assert snapshot["vision_input_status"] == "error"
    assert snapshot["vision_input"]["valid"] is False
    assert (
        snapshot["last_error_text"]
        == "uart6 decode failed: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte"
    )


def test_assistant_follow_runtime_preserves_position_and_angle_passthrough_commands(
    monkeypatch,
) -> None:
    """位置和角度透传命令生效后，角色层不能立刻再用速度写回把它们冲掉。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0,x=12.0,angle=45.0\n"
    uart6 = _FakeUart(["x=0.5,y=0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    first_cmd = dict(runtime._transport_car.last_cmd)
    runtime.step()
    second_cmd = dict(runtime._transport_car.last_cmd)

    assert ("handle_uart_line", "uart8", "x=12.0,angle=45.0") in events
    assert first_cmd == {"x": 12.0, "y": 8.0, "angle": 45.0}
    assert second_cmd == {"x": 12.0, "y": 8.0, "angle": 45.0}


def test_assistant_follow_runtime_new_velocity_packet_reclaims_control_after_position_mode(
    monkeypatch,
) -> None:
    """位置命令保住后，新的速度包仍要能让角色层重新接管。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"x=12.0,angle=45.0\n"
    uart6 = _FakeUart(["x=0.5,y=0.5"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    after_position = dict(runtime._transport_car.last_cmd)
    uart8._buffer = b"vx=2.0,omega=1.0\n"
    runtime.step()
    after_velocity = dict(runtime._transport_car.last_cmd)

    assert ("handle_uart_line", "uart8", "x=12.0,angle=45.0") in events
    assert after_position == {"x": 12.0, "y": 8.0, "angle": 45.0}
    assert after_velocity == {"vx": 2.5, "vy": 0.5, "omega": 1.0}


def test_assistant_follow_runtime_builds_diagnostics_snapshot_on_demand(
    monkeypatch,
) -> None:
    """控制周期不应每拍构造完整诊断快照，只有查询时才组织字典。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=2.0,omega=1.0\n"
    uart6 = _FakeUart(["x=-0.5,y=0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    original_builder = follow_runtime_module.build_follow_snapshot
    build_calls = []

    def counting_builder(*args, **kwargs):
        build_calls.append((args, kwargs))
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        follow_runtime_module, "build_follow_snapshot", counting_builder
    )
    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    build_calls[:] = []

    runtime.step()
    runtime.step()

    assert events[-1] == "transport_step"
    assert build_calls == []

    snapshot = runtime.build_follow_snapshot()

    assert len(build_calls) == 1
    assert snapshot["transport_command"] == {"vx": 1.5, "vy": 0.25, "omega": 1.0}


def test_assistant_follow_runtime_velocity_write_keeps_rear_mode_state(
    monkeypatch,
) -> None:
    """rear 命令生效后，角色层速度写回要保住 rear_only_mode，并沿共享底盘速度入口执行。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"rear=1\nvx=1.0\n"
    uart6 = _FakeUart(["x=0.5,y=0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)

    runtime.step()
    runtime.step()

    assert ("handle_uart_line", "uart8", "rear=1") in events
    assert runtime._transport_car.last_cmd == {"vx": 1.5, "vy": 0.25, "omega": 0.0}
    assert runtime._transport_car.rear_only_mode is True
    assert runtime._transport_car.command_lock is False
    assert runtime._transport_car.command_mode == "none"


def test_assistant_follow_runtime_step_avoids_public_vision_observation_copy(
    monkeypatch,
) -> None:
    """角色层内部控制周期读取视觉时不应走公开副本接口。"""

    events, _uart3, uart8 = install_fake_transport_car(monkeypatch)
    uart8._buffer = b"vx=1.0\n"
    uart6 = _FakeUart(["x=0.5,y=0.25"])
    install_fake_uart6_factory(monkeypatch, uart6)
    follow_runtime_module = import_assistant_module(
        "vision.assistant.follow_runtime", monkeypatch
    )

    runtime = follow_runtime_module.AssistantFollowRuntime(now_ms=lambda: 100)
    vision_calls = []
    vision_input_cls = runtime._vision_input.__class__
    original_public_getter = vision_input_cls.get_active_observation

    def counting_public_getter(self):
        vision_calls.append("public_get")
        return original_public_getter(self)

    monkeypatch.setattr(
        vision_input_cls, "get_active_observation", counting_public_getter
    )

    runtime.step()

    assert events[-1] == "transport_step"
    assert vision_calls == []

    snapshot = runtime.build_follow_snapshot()

    assert vision_calls == ["public_get", "public_get"]
    assert snapshot["vision_input"] == {
        "valid": True,
        "x": 0.5,
        "y": 0.25,
        "timestamp_ms": 100,
        "age_ms": 0,
    }
