"""run 角色分流启动壳测试.

@file tests/unit/entry/test_run_role_dispatch.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUN_PATH = PROJECT_ROOT / "src" / "script" / "run.py"


def load_run_module(monkeypatch):
    """按文件路径加载 run 模块, 并注入最小依赖桩."""

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
    config_motion = ModuleType("config.motion")
    setattr(config_motion, "TICK_MS", 5)
    setattr(config_motion, "ROLE_STEP_MS", 100)
    setattr(config_motion, "MOTION_INPUT_STEP_MS", 15)
    setattr(config_module, "motion", config_motion)
    monkeypatch.setitem(sys.modules, "config", config_module)
    monkeypatch.setitem(sys.modules, "config.motion", config_motion)

    startup_log_module = ModuleType("utils.startup_log")
    setattr(startup_log_module, "log", lambda *_args, **_kwargs: None)
    setattr(startup_log_module, "log_exception", lambda *_args, **_kwargs: None)
    setattr(startup_log_module, "log_memory", lambda *_args, **_kwargs: None)
    monkeypatch.setitem(sys.modules, "utils.startup_log", startup_log_module)

    vehicle_role_module = ModuleType("role.vehicle_role")
    setattr(vehicle_role_module, "read_vehicle_role", lambda: "master")
    monkeypatch.setitem(sys.modules, "role.vehicle_role", vehicle_role_module)

    role_module = ModuleType("role")

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

        def has_pending_tick(self) -> bool:
            return False

        def step_control(self) -> bool:
            state["loop_steps"] += 1
            return False

        def poll_transport_rx(self) -> None:
            return None

        def step_role(self) -> bool:
            state["loop_steps"] += 1
            return False

        def step_motion_input(self) -> bool:
            state["loop_steps"] += 1
            return False

        def poll_transport_tx(self) -> None:
            return None

        def collect_garbage(self) -> None:
            return None

    setattr(role_module, "create_role_transport_car", lambda role: _FakeCar())
    monkeypatch.setitem(sys.modules, "role", role_module)

    spec = spec_from_file_location("run_entry", RUN_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # pyright: ignore[reportAttributeAccessIssue]
    return module, state


def test_run_import_does_not_create_car_or_start_ticker(monkeypatch) -> None:
    """模块导入期不应直接创建运行时对象."""

    _module, state = load_run_module(monkeypatch)

    assert state["car_created"] == 0
    assert state["ticker_started"] == 0
    assert state["loop_steps"] == 0


def test_run_main_reads_role_before_runtime_setup(monkeypatch) -> None:
    """运行入口必须先识别角色, 再装配视觉层和运行时."""

    module, _state = load_run_module(monkeypatch)
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
    setattr(module, "log", lambda *_args, **_kwargs: None)

    module.main()

    role_index = events.index("role")
    car_index = events.index(("car", "master"))
    ticker_index = events.index("ticker_create")

    assert role_index < car_index < ticker_index
    assert any(event[0] == "loop" for event in events if isinstance(event, tuple))


def test_run_main_prints_mem_info_before_ready_when_available(monkeypatch) -> None:
    """板端提供 mem_info 时，在运行时 ready 日志前输出一次。"""

    module, _state = load_run_module(monkeypatch)
    events = []
    calls = []
    micropython_module = ModuleType("micropython")
    setattr(
        micropython_module,
        "mem_info",
        lambda *args: (calls.append(args), events.append("mem_info")),
    )
    monkeypatch.setitem(sys.modules, "micropython", micropython_module)
    setattr(module, "log", lambda _stage, detail="": events.append(detail))

    module.main()

    assert events.index("mem_info") < events.index("TransportCar ready")
    assert calls == [(1,)]


def test_run_main_returns_assistant_role_and_dispatches_it(
    monkeypatch,
) -> None:
    """运行入口切到辅车角色时, 返回值和运行时装配都要保持同一个角色."""

    module, _state = load_run_module(monkeypatch)
    events = []
    setattr(module, "read_vehicle_role", lambda: "assistant")
    setattr(
        module,
        "create_role_transport_car",
        lambda role: (
            events.append(("car", role))
            or type(
                "_Car",
                (),
                {
                    "wheel_states": [{"encoder": "enc_l"}, {"encoder": "enc_r"}],
                    "imu": "imu",
                    "mark_tick": lambda self, _tick=None: None,
                    "set_ticker": lambda self, _ticker: None,
                    "has_pending_tick": lambda self: False,
                    "poll_transport_rx": lambda self: None,
                    "step_role": lambda self: False,
                    "step_motion_input": lambda self: False,
                    "poll_transport_tx": lambda self: None,
                    "collect_garbage": lambda self: None,
                },
            )()
        ),
    )
    setattr(
        module,
        "_create_ticker",
        lambda: type(
            "_Ticker",
            (),
            {
                "capture_list": lambda self, *items: None,
                "callback": lambda self, callback_fn: None,
                "start": lambda self, tick_ms: None,
            },
        )(),
    )
    setattr(module, "log", lambda *_args, **_kwargs: None)

    role = module.main()

    assert role == "assistant"
    assert ("car", "assistant") in events
    assert len(events) == 1


def test_run_main_stops_runtime_and_reraises_fatal_error(
    monkeypatch,
) -> None:
    """正式运行入口遇到未捕获异常时, 必须尽量停机并继续上抛."""

    module, _state = load_run_module(monkeypatch)
    events = []

    class _Car:
        wheel_states = [{"encoder": "enc_m"}]
        imu = "imu"

        def mark_tick(self, _tick=None) -> None:
            return None

        def set_ticker(self, _ticker) -> None:
            return None

        def has_pending_tick(self) -> bool:
            return False

        def poll_transport_rx(self) -> None:
            return None

        def step_role(self) -> bool:
            raise RuntimeError("loop boom")

        def step_motion_input(self) -> bool:
            return True

        def poll_transport_tx(self) -> None:
            return None

        def collect_garbage(self) -> None:
            return None

        def stop(self) -> None:
            events.append("car_stop")

    class _Ticker:
        def capture_list(self, *items) -> None:
            return None

        def callback(self, callback_fn) -> None:
            return None

        def start(self, tick_ms) -> None:
            events.append(("ticker_start", tick_ms))

        def stop(self) -> None:
            events.append("ticker_stop")

    setattr(module, "read_vehicle_role", lambda: "master")
    setattr(module, "create_role_transport_car", lambda role: _Car())
    setattr(module, "_create_ticker", lambda: _Ticker())
    trace_calls = []
    monkeypatch.setattr(
        module,
        "log_exception",
        lambda stage, detail, exc: trace_calls.append((stage, detail, str(exc))),
        raising=False,
    )

    with pytest.raises(RuntimeError, match="loop boom"):
        module.main()
    assert "ticker_stop" in events
    assert "car_stop" in events
    assert trace_calls == [("run", "fatal error: loop boom", "loop boom")]


def test_run_control_loop_runs_due_role_after_one_control_tick(monkeypatch) -> None:
    """底盘 tick 积压时先跑一次底盘, 到期状态机仍要运行."""

    module, _state = load_run_module(monkeypatch)
    events = []

    class _Car:
        def __init__(self) -> None:
            self.pending_ticks = 2

        def has_pending_tick(self) -> bool:
            return self.pending_ticks > 0

        def step_control(self) -> bool:
            events.append("control")
            self.pending_ticks -= 1
            return True

        def poll_transport_rx(self) -> None:
            events.append("rx")

        def step_role(self) -> bool:
            events.append("role")
            return False

        def step_motion_input(self) -> bool:
            events.append("motion")
            return False

        def poll_transport_tx(self) -> None:
            events.append("tx")

        def collect_garbage(self) -> None:
            events.append("gc")

    module._run_control_loop(_Car(), now_ms=lambda: 0)

    assert events == ["control", "gc", "rx", "role", "tx"]


def test_run_control_loop_throttles_role_cycle_to_100ms(monkeypatch) -> None:
    """状态机业务层按 100ms 运行, 通信与 gc 每轮推进."""

    module, _state = load_run_module(monkeypatch)
    events = []
    now_values = [0, 50, 100]

    class _Car:
        role_steps = 0

        def has_pending_tick(self) -> bool:
            return False

        def poll_transport_rx(self) -> None:
            events.append("rx")

        def step_role(self) -> bool:
            events.append("role")
            self.role_steps += 1
            return self.role_steps < 2

        def step_motion_input(self) -> bool:
            events.append("motion")
            return True

        def poll_transport_tx(self) -> None:
            events.append("tx")

        def collect_garbage(self) -> None:
            events.append("gc")

    module._run_control_loop(_Car(), now_ms=lambda: now_values.pop(0))

    assert events == [
        "gc",
        "rx",
        "role",
        "motion",
        "tx",
        "gc",
        "rx",
        "motion",
        "tx",
        "gc",
        "rx",
        "role",
        "tx",
    ]


def test_run_control_loop_idles_before_next_due_cycle(monkeypatch) -> None:
    """未到底盘、通信或状态机周期时, 不空转执行通信和 gc."""

    module, _state = load_run_module(monkeypatch)
    events = []
    now_values = [0, 1, 15, 100]
    monkeypatch.setattr(module, "_idle_wait", lambda: events.append("idle"))

    class _Car:
        role_steps = 0

        def has_pending_tick(self) -> bool:
            return False

        def poll_transport_rx(self) -> None:
            events.append("rx")

        def step_role(self) -> bool:
            events.append("role")
            self.role_steps += 1
            return self.role_steps < 2

        def step_motion_input(self) -> bool:
            events.append("motion")
            return True

        def poll_transport_tx(self) -> None:
            events.append("tx")

        def collect_garbage(self) -> None:
            events.append("gc")

    module._run_control_loop(_Car(), now_ms=lambda: now_values.pop(0))

    assert events == [
        "gc",
        "rx",
        "role",
        "motion",
        "tx",
        "idle",
        "gc",
        "rx",
        "motion",
        "tx",
        "gc",
        "rx",
        "role",
        "tx",
    ]


def test_run_control_loop_runs_due_role_after_rx_tick_arrives(monkeypatch) -> None:
    """通信 RX 期间出现底盘 tick 时, 到期状态机仍要运行."""

    module, _state = load_run_module(monkeypatch)
    events = []

    class _Car:
        pending_ticks = 0

        def has_pending_tick(self) -> bool:
            return self.pending_ticks > 0

        def poll_transport_rx(self) -> None:
            events.append("rx")
            self.pending_ticks = 1

        def step_control(self) -> bool:
            events.append("control")
            self.pending_ticks = 0
            return False

        def step_role(self) -> bool:
            events.append("role")
            return False

        def step_motion_input(self) -> bool:
            events.append("motion")
            return False

        def poll_transport_tx(self) -> None:
            events.append("tx")

        def collect_garbage(self) -> None:
            events.append("gc")

    module._run_control_loop(_Car(), now_ms=lambda: 0)

    assert events == ["gc", "rx", "role", "tx"]


def test_run_control_loop_requires_split_runtime_interface(monkeypatch) -> None:
    """正式入口不回退到旧 step 接口, 避免形成第二套周期语义."""

    module, _state = load_run_module(monkeypatch)

    class _Car:
        def has_pending_tick(self) -> bool:
            return False

        def poll_transport_rx(self) -> None:
            return None

        def step(self) -> bool:
            return False

    with pytest.raises(AttributeError, match="collect_garbage|step_role|step_motion_input"):
        module._run_control_loop(_Car(), now_ms=lambda: 0)
