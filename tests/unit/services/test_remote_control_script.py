"""remote_control 启动脚本回归测试."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

import config.boot_role as boot_role_module
from config.boot_role import clear_vehicle_role, set_vehicle_role


pytestmark = pytest.mark.unit


def _script_path() -> Path:
    """返回 remote_control 脚本绝对路径."""
    return Path(__file__).resolve().parents[3] / "src" / "script" / "remote_control.py"


def test_remote_control_uses_chassis_state_wheel_states_for_ticker_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """启动脚本应通过 chassis_state 暴露的轮组状态注册 ticker 采集项."""

    capture_calls: list[tuple] = []
    callback_calls: list[object] = []
    start_calls: list[int] = []

    class FakeTicker:
        """记录 ticker 接线行为的假对象."""

        def capture_list(self, *items: object) -> None:
            capture_calls.append(items)

        def callback(self, func: object) -> None:
            callback_calls.append(func)

        def start(self, tick_ms: int) -> None:
            start_calls.append(tick_ms)

    class FakeUart:
        """记录串口输出的假对象."""

        def __init__(self) -> None:
            self.messages: list[str] = []

        def write(self, text: str) -> None:
            self.messages.append(text)

    class FakeTransportCar:
        """仅暴露重构后状态接口的假车对象."""

        def __init__(self, vehicle_role: str) -> None:
            self.uart3 = FakeUart()
            self.imu = object()
            self.mark_tick = object()
            self.ticker = None
            self.step_calls = 0
            self.vehicle_role = vehicle_role
            self.chassis_state = types.SimpleNamespace(
                wheel_states=[
                    {"encoder": "enc-m"},
                    {"encoder": "enc-l"},
                    {"encoder": "enc-r"},
                ]
            )

        def set_ticker(self, ticker_obj: object) -> None:
            self.ticker = ticker_obj

        def step(self) -> bool:
            self.step_calls += 1
            return False

    fake_smartcar = types.ModuleType("smartcar")
    setattr(fake_smartcar, "ticker", lambda _channel: FakeTicker())

    fake_transport_module = types.ModuleType("services.transport_car")
    setattr(fake_transport_module, "TransportCar", FakeTransportCar)

    monkeypatch.setitem(sys.modules, "smartcar", fake_smartcar)
    monkeypatch.setitem(sys.modules, "services.transport_car", fake_transport_module)
    monkeypatch.setitem(sys.modules, "config.boot_role", boot_role_module)
    sys.modules.pop("remote_control_test_module", None)

    spec = importlib.util.spec_from_file_location(
        "remote_control_test_module", _script_path()
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    clear_vehicle_role()
    set_vehicle_role("main")

    spec.loader.exec_module(module)

    assert module.VEHICLE_ROLE == "main"
    assert module.car.vehicle_role == "main"
    assert capture_calls == [("enc-m", "enc-l", "enc-r", module.car.imu)]
    assert callback_calls == [module.car.mark_tick]
    assert start_calls == [module.TICK_MS]
    assert module.car.ticker is not None
    assert module.car.uart3.messages[:2] == [
        "Creating ticker...\r\n",
        "Starting ticker (%d ms)...\r\n" % module.TICK_MS,
    ]


def test_remote_control_requires_exposed_vehicle_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正常运行脚本应要求 boot 显式暴露车辆角色."""

    class FakeTicker:
        """最小 ticker 假对象."""

        def capture_list(self, *items: object) -> None:
            return None

        def callback(self, func: object) -> None:
            return None

        def start(self, tick_ms: int) -> None:
            return None

    class FakeUart:
        """最小串口假对象."""

        def write(self, text: str) -> None:
            return None

    class FakeTransportCar:
        """满足启动路径最小依赖的假车对象."""

        def __init__(self, vehicle_role: str) -> None:
            self.uart3 = FakeUart()
            self.imu = object()
            self.mark_tick = object()
            self.vehicle_role = vehicle_role
            self.chassis_state = types.SimpleNamespace(
                wheel_states=[
                    {"encoder": "enc-m"},
                    {"encoder": "enc-l"},
                    {"encoder": "enc-r"},
                ]
            )

        def set_ticker(self, ticker_obj: object) -> None:
            return None

        def step(self) -> bool:
            return False

    fake_smartcar = types.ModuleType("smartcar")
    setattr(fake_smartcar, "ticker", lambda _channel: FakeTicker())

    fake_transport_module = types.ModuleType("services.transport_car")
    setattr(fake_transport_module, "TransportCar", FakeTransportCar)

    monkeypatch.setitem(sys.modules, "smartcar", fake_smartcar)
    monkeypatch.setitem(sys.modules, "services.transport_car", fake_transport_module)
    monkeypatch.setitem(sys.modules, "config.boot_role", boot_role_module)
    sys.modules.pop("remote_control_missing_role_module", None)

    spec = importlib.util.spec_from_file_location(
        "remote_control_missing_role_module", _script_path()
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    clear_vehicle_role()

    with pytest.raises(RuntimeError, match="VEHICLE_ROLE is not exposed"):
        spec.loader.exec_module(module)
