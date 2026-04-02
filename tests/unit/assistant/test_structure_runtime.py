from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


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
    encoder_pins = {
        name: (port.phase_a_pin, port.phase_b_pin, port.invert)
        for name, port in hw_bundle["encoders"].items()
    }

    assert hw_bundle["uart"]["uart3"].uart_id == 2
    assert hw_bundle["motors"]["m"].port_name == "PWM_C30_DIR_C31"
    assert hw_bundle["motors"]["l"].port_name == "PWM_D4_DIR_D5"
    assert hw_bundle["motors"]["r"].port_name == "PWM_D6_DIR_D7"
    assert encoder_pins == {
        "m": ("D15", "D16", True),
        "l": ("C0", "C1", True),
        "r": ("C2", "C3", True),
    }


def test_assistant_script_entries_exist() -> None:
    from assistant.script import calibrate_gyro, pid_identify

    assert pid_identify is not None
    assert calibrate_gyro is not None


def test_assistant_control_layer_does_not_own_cross_cycle_state() -> None:
    import assistant.ctrl.chassis as chassis_module

    assert not hasattr(chassis_module, "ChassisRuntime"), (
        "控制层只保留单周期控制，不应继续暴露整周期运行时"
    )
    assert not hasattr(chassis_module, "CoreRuntime"), (
        "控制层不应继续暴露长期状态 owner"
    )


def test_assistant_ctrl_modules_are_importable() -> None:
    from assistant.ctrl import attitude, filters, ident, kinematics, pid, storage

    assert filters is not None
    assert pid is not None
    assert kinematics is not None
    assert attitude is not None
    assert ident is not None
    assert storage is not None
