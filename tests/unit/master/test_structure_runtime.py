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
