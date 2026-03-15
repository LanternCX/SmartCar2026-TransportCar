"""boot 启动脚本行为测试."""

import builtins
import importlib.util
import sys
import types
from pathlib import Path

import pytest

from config.boot_role import clear_vehicle_role


pytestmark = pytest.mark.unit


def _boot_path() -> Path:
    """返回 boot 脚本绝对路径."""
    return Path(__file__).resolve().parents[3] / "src" / "boot.py"


def _load_boot_module(
    monkeypatch: pytest.MonkeyPatch,
    *,
    d8: int,
    d9: int,
    button1: int,
    button2: int,
    execfile_impl=None,
):
    """在伪造硬件环境下装载 boot 模块."""

    exec_calls: list[str] = []
    chdir_calls: list[str] = []
    print_calls: list[str] = []

    pin_values = {
        "D8": d8,
        "D9": d9,
        "C8": button1,
        "C9": button2,
    }

    class FakePin:
        """返回固定电平的引脚假对象."""

        IN = "in"
        PULL_UP_47K = "pull_up"

        def __init__(
            self, name: str, _mode: object, pull: object | None = None
        ) -> None:
            assert pull == self.PULL_UP_47K
            self._value = pin_values[name]

        def value(self) -> int:
            return self._value

    fake_machine = types.ModuleType("machine")
    fake_machine.Pin = FakePin

    fake_os = types.ModuleType("os")
    fake_os.chdir = chdir_calls.append

    fake_time = types.ModuleType("time")
    fake_time.sleep_ms = lambda _ms: None

    def fake_execfile(path: str) -> None:
        exec_calls.append(path)
        if execfile_impl is not None:
            execfile_impl(path)

    module_name = "boot_test_module"
    monkeypatch.setitem(sys.modules, "machine", fake_machine)
    monkeypatch.setitem(sys.modules, "os", fake_os)
    monkeypatch.setitem(sys.modules, "time", fake_time)
    monkeypatch.setattr(builtins, "execfile", fake_execfile, raising=False)
    monkeypatch.setattr(builtins, "print", lambda text: print_calls.append(str(text)))
    sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(module_name, _boot_path())
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module, exec_calls, chdir_calls, print_calls


def test_boot_long_press_button1_runs_pid_identify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """上电长按按钮 1 应进入 PID 辨识脚本."""

    module, exec_calls, _chdir_calls, _print_calls = _load_boot_module(
        monkeypatch,
        d8=1,
        d9=0,
        button1=0,
        button2=1,
    )

    assert module.decode_vehicle_role(1, 0) == "main"
    assert exec_calls == ["script/pid_identify.py"]


def test_boot_button_pin_constants_match_board_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """boot 脚本应使用板级定义的 Button 1-4 引脚名."""

    module, _exec_calls, _chdir_calls, _print_calls = _load_boot_module(
        monkeypatch,
        d8=1,
        d9=0,
        button1=1,
        button2=1,
    )

    assert module.BUTTON1_PIN == "C8"
    assert module.BUTTON2_PIN == "C9"
    assert module.BUTTON3_PIN == "C14"
    assert module.BUTTON4_PIN == "C15"


def test_boot_long_press_button2_runs_calibrate_gyro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """上电长按按钮 2 应进入 IMU 校准脚本."""

    module, exec_calls, _chdir_calls, _print_calls = _load_boot_module(
        monkeypatch,
        d8=0,
        d9=1,
        button1=1,
        button2=0,
    )

    assert module.decode_vehicle_role(0, 1) == "aux"
    assert exec_calls == ["script/calibrate_gyro.py"]


def test_boot_without_long_press_runs_remote_control_and_exposes_vehicle_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未长按按钮时应进入正常运行脚本, 并暴露车辆角色."""

    module, exec_calls, chdir_calls, _print_calls = _load_boot_module(
        monkeypatch,
        d8=1,
        d9=0,
        button1=1,
        button2=1,
    )

    assert exec_calls == ["script/remote_control.py"]
    assert chdir_calls == ["/flash"]
    assert module.VEHICLE_ROLE == "main"


def test_boot_passes_vehicle_role_to_remote_control_via_explicit_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正常启动时应通过显式状态接口把角色传给 remote_control."""

    remote_role = {"value": None}

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
        """满足 remote_control 装载最小依赖的假车对象."""

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
    fake_smartcar.ticker = lambda _channel: FakeTicker()

    fake_transport_module = types.ModuleType("services.transport_car")
    fake_transport_module.TransportCar = FakeTransportCar

    monkeypatch.setitem(sys.modules, "smartcar", fake_smartcar)
    monkeypatch.setitem(sys.modules, "services.transport_car", fake_transport_module)

    def run_remote_control(path: str) -> None:
        if path != "script/remote_control.py":
            return
        module_name = "remote_control_chain_test_module"
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(
            module_name,
            Path(__file__).resolve().parents[3]
            / "src"
            / "script"
            / "remote_control.py",
        )
        assert spec is not None
        assert spec.loader is not None
        remote_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = remote_module
        spec.loader.exec_module(remote_module)
        remote_role["value"] = remote_module.VEHICLE_ROLE

    clear_vehicle_role()
    _load_boot_module(
        monkeypatch,
        d8=1,
        d9=0,
        button1=1,
        button2=1,
        execfile_impl=run_remote_control,
    )

    assert remote_role["value"] == "main"


def test_boot_invalid_role_combination_safe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非法角色拨码组合应安全失败, 不进入任何脚本."""

    module, exec_calls, _chdir_calls, print_calls = _load_boot_module(
        monkeypatch,
        d8=1,
        d9=1,
        button1=1,
        button2=1,
    )

    with pytest.raises(ValueError):
        module.decode_vehicle_role(1, 1)

    assert exec_calls == []
    assert print_calls == ["Invalid vehicle role switch combination: D8=1, D9=1"]


def test_boot_all_low_role_combination_safe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D8/D9 同时为低电平时应安全失败, 不进入任何脚本."""

    module, exec_calls, _chdir_calls, print_calls = _load_boot_module(
        monkeypatch,
        d8=0,
        d9=0,
        button1=1,
        button2=1,
    )

    with pytest.raises(ValueError):
        module.decode_vehicle_role(0, 0)

    assert exec_calls == []
    assert print_calls == ["Invalid vehicle role switch combination: D8=0, D9=0"]


def test_boot_both_buttons_long_press_safe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """双按钮同时长按时应安全失败, 不进入任何脚本."""

    _module, exec_calls, _chdir_calls, print_calls = _load_boot_module(
        monkeypatch,
        d8=1,
        d9=0,
        button1=0,
        button2=0,
    )

    assert exec_calls == []
    assert print_calls == ["Both boot buttons are long-pressed"]
