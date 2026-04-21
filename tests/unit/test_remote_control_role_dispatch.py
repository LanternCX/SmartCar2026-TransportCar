"""remote_control 角色分流启动壳测试.

@file tests/unit/test_remote_control_role_dispatch.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REMOTE_CONTROL_PATH = PROJECT_ROOT / "src" / "script" / "remote_control.py"


def load_remote_control_module(monkeypatch):
    """按文件路径加载 remote_control 模块, 并注入最小依赖桩."""

    state = {"car_created": 0, "ticker_started": 0, "loop_steps": 0}

    smartcar_module = ModuleType("smartcar")

    class _FakeTicker:
        def __init__(self, _index) -> None:
            self.capture_items = []
            self.callback_fn = None

        def capture_list(self, *items) -> None:
            self.capture_items = list(items)

        def callback(self, callback_fn) -> None:
            self.callback_fn = callback_fn

        def start(self, _tick_ms) -> None:
            state["ticker_started"] += 1

        def stop(self) -> None:
            return None

    setattr(smartcar_module, "ticker", _FakeTicker)
    monkeypatch.setitem(sys.modules, "smartcar", smartcar_module)

    config_module = ModuleType("config")
    config_params = ModuleType("config.params")
    setattr(config_params, "TICK_MS", 5)
    setattr(config_module, "params", config_params)
    monkeypatch.setitem(sys.modules, "config", config_module)
    monkeypatch.setitem(sys.modules, "config.params", config_params)

    startup_log_module = ModuleType("utils.startup_log")
    setattr(startup_log_module, "startup_log", lambda *_args, **_kwargs: None)
    monkeypatch.setitem(sys.modules, "utils.startup_log", startup_log_module)

    vehicle_role_module = ModuleType("vision.vehicle_role")
    setattr(vehicle_role_module, "read_vehicle_role", lambda: "master")
    monkeypatch.setitem(sys.modules, "vision.vehicle_role", vehicle_role_module)

    vision_module = ModuleType("vision")

    class _FakeCar:
        def __init__(self) -> None:
            state["car_created"] += 1
            self.wheel_states = [
                {"encoder": "enc_m"},
                {"encoder": "enc_l"},
                {"encoder": "enc_r"},
            ]
            self.imu = "imu"
            self.ticker = None

        def mark_tick(self, _tick=None) -> None:
            return None

        def set_ticker(self, ticker_obj) -> None:
            self.ticker = ticker_obj

        def step(self) -> bool:
            state["loop_steps"] += 1
            return False

    setattr(vision_module, "create_role_transport_car", lambda role: _FakeCar())
    monkeypatch.setitem(sys.modules, "vision", vision_module)

    spec = spec_from_file_location("remote_control_entry", REMOTE_CONTROL_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, state


def test_remote_control_import_does_not_create_car_or_start_ticker(monkeypatch) -> None:
    """模块导入期不应直接创建运行时对象."""

    _module, state = load_remote_control_module(monkeypatch)

    assert state["car_created"] == 0
    assert state["ticker_started"] == 0
    assert state["loop_steps"] == 0


def test_remote_control_main_reads_role_before_runtime_setup(monkeypatch) -> None:
    """运行入口必须先识别角色, 再装配视觉层和运行时."""

    module, _state = load_remote_control_module(monkeypatch)
    events = []
    setattr(module, "read_vehicle_role", lambda: events.append("role") or "master")
    setattr(
        module,
        "create_role_transport_car",
        lambda role: (
            events.append(("car", role))
            or type(
                "_Car",
                (),
                {
                    "wheel_states": [{"encoder": "enc_m"}],
                    "imu": "imu",
                    "mark_tick": lambda self, _tick=None: None,
                    "set_ticker": lambda self, ticker_obj: events.append(
                        ("ticker_set", ticker_obj)
                    ),
                },
            )()
        ),
    )
    setattr(
        module,
        "_create_ticker",
        lambda: (
            events.append("ticker_create")
            or type(
                "_Ticker",
                (),
                {
                    "capture_list": lambda self, *items: events.append(
                        ("capture", items)
                    ),
                    "callback": lambda self, callback_fn: events.append(
                        ("callback", callback_fn)
                    ),
                    "start": lambda self, tick_ms: events.append(("start", tick_ms)),
                },
            )()
        ),
    )
    setattr(module, "_run_control_loop", lambda car: events.append(("loop", car)))
    setattr(module, "startup_log", lambda *_args, **_kwargs: None)

    module.main()

    role_index = events.index("role")
    car_index = events.index(("car", "master"))
    ticker_index = events.index("ticker_create")

    assert role_index < car_index < ticker_index
    assert any(event[0] == "loop" for event in events if isinstance(event, tuple))
