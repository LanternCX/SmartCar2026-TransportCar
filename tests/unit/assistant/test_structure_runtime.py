from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_assistant_runtime_exposes_new_structure_packages() -> None:
    runtime_root = PROJECT_ROOT / "src" / "assistant"

    for name in ("hw", "ctrl", "script"):
        assert (runtime_root / name).is_dir()


def test_assistant_hw_modules_and_bundle_entry_are_importable() -> None:
    from assistant.app import build_hw_bundle
    from assistant.hw import encoders, imu, motors, uart

    assert build_hw_bundle is not None
    assert uart is not None
    assert motors is not None
    assert encoders is not None
    assert imu is not None


def test_assistant_hw_bundle_uses_legacy_confirmed_mapping() -> None:
    from assistant.app import build_hw_bundle

    hw_bundle = build_hw_bundle()

    assert hw_bundle["uart"]["uart3"].uart_id == 2
    assert hw_bundle["motors"]["m"].port_name == "PWM_C30_DIR_C31"
    assert hw_bundle["motors"]["l"].port_name == "PWM_D4_DIR_D5"
    assert hw_bundle["motors"]["r"].port_name == "PWM_D6_DIR_D7"
    assert hw_bundle["encoders"]["m"].phase_a_pin == "D15"
    assert hw_bundle["encoders"]["l"].phase_a_pin == "C0"
    assert hw_bundle["encoders"]["r"].phase_a_pin == "C2"


def test_assistant_script_entries_exist() -> None:
    from assistant.script import calibrate_gyro, pid_identify

    assert pid_identify is not None
    assert calibrate_gyro is not None


def test_assistant_ctrl_chassis_is_importable() -> None:
    from assistant.ctrl.chassis import ChassisRuntime, CoreRuntime

    assert CoreRuntime is not None
    assert ChassisRuntime is not None


def test_assistant_ctrl_modules_are_importable() -> None:
    from assistant.ctrl import attitude, filters, ident, kinematics, pid, storage

    assert filters is not None
    assert pid is not None
    assert kinematics is not None
    assert attitude is not None
    assert ident is not None
    assert storage is not None
