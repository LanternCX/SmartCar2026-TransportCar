"""TransportCar Stage 2 安全模式单元测试."""

import sys
import types
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def _install_transport_stubs() -> None:
    machine = types.ModuleType("machine")

    class Pin:
        OUT = 0
        IN = 1
        PULL_UP_47K = 2

        def __init__(self, *_args, **_kwargs):
            self._value = 1

        def value(self):
            return self._value

        def toggle(self):
            return None

    class UART:
        def __init__(self, *_args, **_kwargs):
            self.messages = []

        def init(self, *_args, **_kwargs):
            return None

        def write(self, text):
            self.messages.append(text)

        def any(self):
            return 0

    setattr(machine, "Pin", Pin)
    setattr(machine, "UART", UART)
    sys.modules.setdefault("machine", machine)

    seekfree = types.ModuleType("seekfree")

    class MOTOR_CONTROLLER:
        PWM_C30_DIR_C31 = 1
        PWM_D4_DIR_D5 = 2
        PWM_D6_DIR_D7 = 3

        def __init__(self, *_args, **_kwargs):
            self.last_duty = 0

        def duty(self, value):
            self.last_duty = value

    class IMU660RX:
        def get(self):
            return [0, 0, 0, 0, 0, 0]

    setattr(seekfree, "MOTOR_CONTROLLER", MOTOR_CONTROLLER)
    setattr(seekfree, "IMU660RX", IMU660RX)
    sys.modules.setdefault("seekfree", seekfree)

    smartcar = types.ModuleType("smartcar")

    class FakeEncoder:
        def get(self):
            return 0

    def encoder(*_args, **_kwargs):
        return FakeEncoder()

    setattr(smartcar, "encoder", encoder)
    sys.modules.setdefault("smartcar", smartcar)


_install_transport_stubs()

import services.transport_car as transport_car_module  # noqa: E402
import services.stage2_smoke as stage2_smoke_module  # noqa: E402


def test_diagnostic_mode_skips_hardware_initializers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_init(*_args, **_kwargs):
        raise AssertionError("hardware init should be skipped")

    monkeypatch.setattr(transport_car_module, "create_imu", fail_init)
    monkeypatch.setattr(transport_car_module, "create_motors", fail_init)
    monkeypatch.setattr(transport_car_module, "create_encoders", fail_init)
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path, logger=None: [0.0] * 6,
    )

    car = transport_car_module.TransportCar(diagnostic_mode=True)

    assert car.diagnostic_mode is True
    assert car.imu.get() == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert sorted(state["name"] for state in car.wheel_states) == ["l", "m", "r"]


def test_diagnostic_mode_keeps_debug_query_tokens_registered() -> None:
    car = transport_car_module.TransportCar(diagnostic_mode=True)

    registered = set(car._router._query_handlers.keys())

    assert {"health", "tick", "imu", "enc", "motor", "vision"} <= registered


def test_diagnostic_mode_wires_vision_transitions_to_breakpoint_sink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path, logger=None: [0.0] * 6,
    )

    car = transport_car_module.TransportCar(diagnostic_mode=True)

    assert car.vision_state_machine._debug_sink == car._emit_vision_debug


def test_stage2_smoke_probe_collects_safe_runtime_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transport_car_module, "load_ident_lookup", lambda _path: {})
    monkeypatch.setattr(
        transport_car_module,
        "load_gyro_offsets",
        lambda _path, logger=None: [0.0] * 6,
    )

    summary = stage2_smoke_module.collect_stage2_summary()

    assert summary["status"] == "ok"
    assert summary["transport_mode"] == "full"
    assert summary["missing_queries"] == []
    assert summary["query_ok"] == 1
    assert summary["step_ok"] == 1
    assert summary["tick_count"] >= 1
    assert set(summary["snapshots"].keys()) == {
        "health",
        "tick",
        "imu",
        "enc",
        "motor",
        "vision",
    }
    assert set(summary["query_outputs"].keys()) == {
        "health",
        "tick",
        "imu",
        "enc",
        "motor",
        "vision",
    }
    assert summary["query_outputs"]["health"].startswith("?health=")


def test_stage2_smoke_probe_clears_stale_runtime_modules() -> None:
    sys.modules["control.wheel"] = types.ModuleType("control.wheel")
    sys.modules["filters.lowpass_filter"] = types.ModuleType("filters.lowpass_filter")

    stage2_smoke_module._clear_modules()

    assert "control.wheel" not in sys.modules
    assert "filters.lowpass_filter" not in sys.modules


def test_stage2_smoke_probe_launcher_stays_tiny() -> None:
    launcher = Path(__file__).resolve().parents[3] / "tools" / "stage2_smoke_probe.py"

    assert launcher.stat().st_size <= 256


def test_stage2_smoke_probe_falls_back_to_lite_mode_on_transport_memory_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        stage2_smoke_module,
        "_collect_full_transport_summary",
        lambda: (_ for _ in ()).throw(MemoryError("memory")),
    )
    monkeypatch.setattr(
        stage2_smoke_module,
        "_check_transport_source",
        lambda: (True, True),
    )

    summary = stage2_smoke_module.collect_stage2_summary()

    assert summary["status"] == "ok"
    assert summary["transport_mode"] == "lite"
    assert summary["query_ok"] == 1
    assert summary["step_ok"] == 0
    assert summary["tick_count"] == 0
