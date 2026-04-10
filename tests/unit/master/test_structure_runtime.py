def test_master_hw_bundle_uses_confirmed_mapping() -> None:
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
    assert hw_bundle["motors"]["l"].port_name == "PWM_D6_DIR_D7"
    assert hw_bundle["motors"]["l"].invert is True
    assert hw_bundle["motors"]["r"].port_name == "PWM_D4_DIR_D5"
    assert hw_bundle["motors"]["r"].invert is False
    assert encoder_pins == {
        "m": ("D15", "D16", True),
        "l": ("C2", "C3", True),
        "r": ("C0", "C1", True),
    }


def test_master_runtime_process_entry_drives_one_cycle() -> None:
    import importlib

    import master.motion_runtime as runtime

    class FakeHeading:
        def heading_deg(self):
            return 12.5

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    hw_bundle = {
        "imu": FakeHeading(),
        "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
    }

    create_runtime_state = getattr(runtime, "create_runtime_state")
    run_base_cycle = getattr(runtime, "run_base_cycle")
    state = create_runtime_state(hw_bundle=hw_bundle)
    snapshot = run_base_cycle(state, hw_bundle=hw_bundle, cycle_token=object())

    assert snapshot["heading_est_deg"] == 12.5
    assert snapshot["odom"] == (0.0, 0.0)


def test_master_runtime_process_state_owns_cross_cycle_state() -> None:
    import master.motion_runtime as runtime

    state = runtime.create_runtime_state(hw_bundle=None)

    assert hasattr(state, "heading_deg")
    assert hasattr(state, "odom")
    assert hasattr(state, "target_heading_deg")
    assert hasattr(state, "heading_target_ready")


def test_master_runtime_process_state_exposes_heading_stability_fields() -> None:
    import master.motion_runtime as runtime

    state = runtime.create_runtime_state(hw_bundle=None)

    assert hasattr(state, "yaw_kd")
    assert hasattr(state, "hold_speed_eps")


def test_master_runtime_process_state_uses_clear_public_type_name() -> None:
    import master.motion_runtime as runtime

    state = runtime.create_runtime_state(hw_bundle=None)

    assert type(state).__name__ == "MotionRuntimeState"


def test_master_motion_runtime_module_no_longer_exposes_legacy_object_shell() -> None:
    import master.motion_runtime as runtime

    assert not hasattr(runtime, "MotionRuntime")
