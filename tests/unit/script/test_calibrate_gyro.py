"""`script.calibrate_gyro` 行为回归测试."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = PROJECT_ROOT / "src" / "script" / "calibrate_gyro.py"
SRC = PROJECT_ROOT / "src"


def _load_calibrate_gyro_module():
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    state = {
        "saved": False,
        "saved_path": None,
        "saved_offsets": None,
        "led": None,
    }

    for name in (
        "machine",
        "seekfree",
        "storage",
        "storage.param_manager",
        "time",
    ):
        sys.modules.pop(name, None)

    machine = ModuleType("machine")

    class Pin:
        OUT = "out"

        def __init__(self, _pin_id, _mode, value=None, **_kwargs) -> None:
            self._value = value
            state["led"] = self

        def toggle(self) -> None:
            if state["saved"]:
                raise AssertionError("保存完成后不应继续闪烁")
            self._value = not self._value

        def value(self, x=None):
            if x is None:
                return self._value
            self._value = x

    setattr(machine, "Pin", Pin)
    sys.modules["machine"] = machine

    seekfree = ModuleType("seekfree")

    class IMU660RX:
        def read(self) -> None:
            return None

        def get(self):
            return [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

    setattr(seekfree, "IMU660RX", IMU660RX)
    sys.modules["seekfree"] = seekfree

    storage_pkg = ModuleType("storage")
    storage_pkg.__path__ = []  # type: ignore[attr-defined]
    sys.modules["storage"] = storage_pkg

    storage_param_manager = ModuleType("storage.param_manager")

    def save_gyro_offsets(path, offsets) -> None:
        state["saved"] = True
        state["saved_path"] = path
        state["saved_offsets"] = list(offsets)

    setattr(storage_param_manager, "save_gyro_offsets", save_gyro_offsets)
    sys.modules["storage.param_manager"] = storage_param_manager

    time_module = ModuleType("time")
    setattr(time_module, "sleep_ms", lambda _delay_ms: None)
    setattr(time_module, "ticks_ms", lambda: 0)
    sys.modules["time"] = time_module

    spec = spec_from_file_location("test_calibrate_gyro_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return state


def test_calibrate_gyro_keeps_led_on_after_save() -> None:
    """保存完成后应停止闪烁并保持常亮."""

    state = _load_calibrate_gyro_module()

    assert state["saved_path"] == "/flash/gyro_offset.txt"
    assert state["saved_offsets"] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert state["led"] is not None
    assert state["led"].value() is False
