from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_master_runtime_exposes_new_structure_packages() -> None:
    runtime_root = PROJECT_ROOT / "src" / "master"

    for name in ("hw", "ctrl", "vision", "script"):
        assert (runtime_root / name).is_dir()


def test_master_hw_modules_and_bundle_entry_are_importable() -> None:
    from master.app import build_hw_bundle
    from master.hw import encoders, imu, motors, uart

    assert build_hw_bundle is not None
    assert uart is not None
    assert motors is not None
    assert encoders is not None
    assert imu is not None


def test_master_hw_bundle_uses_legacy_confirmed_mapping() -> None:
    from master.app import build_hw_bundle

    hw_bundle = build_hw_bundle()
    encoder_pins = {
        name: (port.phase_a_pin, port.phase_b_pin, port.invert)
        for name, port in hw_bundle["encoders"].items()
    }

    assert hw_bundle["uart"]["uart3"].uart_id == 2
    assert hw_bundle["uart"]["uart6"].uart_id == 5
    assert hw_bundle["uart"]["uart8"].uart_id == 7
    assert hw_bundle["motors"]["m"].port_name == "PWM_C30_DIR_C31"
    assert hw_bundle["motors"]["l"].port_name == "PWM_D4_DIR_D5"
    assert hw_bundle["motors"]["r"].port_name == "PWM_D6_DIR_D7"
    assert encoder_pins == {
        "m": ("D15", "D16", True),
        "l": ("C0", "C1", True),
        "r": ("C2", "C3", True),
    }


def test_master_vision_modules_are_importable() -> None:
    from master.vision import decision, ingress, parser, state_machine

    assert parser is not None
    assert ingress is not None
    assert state_machine is not None
    assert decision is not None


def test_master_ctrl_and_script_modules_are_importable() -> None:
    from master.ctrl import attitude, chassis, filters, ident, kinematics, pid, storage
    from master.script import calibrate_gyro, pid_identify

    assert filters is not None
    assert pid is not None
    assert kinematics is not None
    assert attitude is not None
    assert chassis is not None
    assert ident is not None
    assert storage is not None
    assert pid_identify is not None
    assert calibrate_gyro is not None
