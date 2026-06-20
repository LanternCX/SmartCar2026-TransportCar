"""按车辆角色选择硬件接线映射的测试."""

import importlib
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))


class _RecordingMotorController:
    PWM_C30_DIR_C31 = "PWM_C30_DIR_C31"
    PWM_D4_DIR_D5 = "PWM_D4_DIR_D5"
    PWM_D6_DIR_D7 = "PWM_D6_DIR_D7"

    def __init__(self, channel, frequency, duty=0, invert=False):
        self.channel = channel
        self.frequency = frequency
        self.initial_duty = duty
        self.invert = invert


class _RecordingEncoder:
    def __init__(self, pin_a, pin_b, invert):
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.invert = invert


def _load_hardware_modules(monkeypatch):
    seekfree = ModuleType("seekfree")
    setattr(seekfree, "MOTOR_CONTROLLER", _RecordingMotorController)
    monkeypatch.setitem(sys.modules, "seekfree", seekfree)

    smartcar = ModuleType("smartcar")
    setattr(smartcar, "encoder", _RecordingEncoder)
    monkeypatch.setitem(sys.modules, "smartcar", smartcar)

    sys.modules.pop("hardware.motors", None)
    sys.modules.pop("hardware.encoders", None)
    motors = importlib.import_module("hardware.motors")
    encoders = importlib.import_module("hardware.encoders")
    return motors, encoders


def test_master_role_uses_old_hardware_mapping(monkeypatch) -> None:
    motors_module, encoders_module = _load_hardware_modules(monkeypatch)

    motors = motors_module.create_motors("master")
    encoders = encoders_module.create_encoders("master")

    assert motors["m"].channel == _RecordingMotorController.PWM_C30_DIR_C31
    assert motors["m"].invert is False
    assert motors["l"].channel == _RecordingMotorController.PWM_D4_DIR_D5
    assert motors["l"].invert is False
    assert motors["r"].channel == _RecordingMotorController.PWM_D6_DIR_D7
    assert motors["r"].invert is True
    assert (encoders["m"].pin_a, encoders["m"].pin_b) == ("D15", "D16")
    assert (encoders["l"].pin_a, encoders["l"].pin_b) == ("C0", "C1")
    assert (encoders["r"].pin_a, encoders["r"].pin_b) == ("C2", "C3")


def test_assistant_role_uses_new_hardware_mapping(monkeypatch) -> None:
    motors_module, encoders_module = _load_hardware_modules(monkeypatch)

    motors = motors_module.create_motors("assistant")
    encoders = encoders_module.create_encoders("assistant")

    assert motors["m"].channel == _RecordingMotorController.PWM_D4_DIR_D5
    assert motors["m"].invert is True
    assert motors["l"].channel == _RecordingMotorController.PWM_D6_DIR_D7
    assert motors["l"].invert is True
    assert motors["r"].channel == _RecordingMotorController.PWM_C30_DIR_C31
    assert motors["r"].invert is True
    assert (encoders["m"].pin_a, encoders["m"].pin_b) == ("D13", "D14")
    assert (encoders["l"].pin_a, encoders["l"].pin_b) == ("D15", "D16")
    assert (encoders["r"].pin_a, encoders["r"].pin_b) == ("C2", "C3")
