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
    assert hw_bundle["motors"]["l"].port_name == "PWM_D4_DIR_D5"
    assert hw_bundle["motors"]["r"].port_name == "PWM_D6_DIR_D7"
    assert encoder_pins == {
        "m": ("D15", "D16", True),
        "l": ("C0", "C1", True),
        "r": ("C2", "C3", True),
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


def test_master_state_module_owns_cross_cycle_state() -> None:
    from master.state import MasterControlState, MasterRuntimeState

    runtime_state = MasterRuntimeState()
    control_state = MasterControlState()

    assert hasattr(runtime_state, "heading_deg")
    assert hasattr(control_state, "yaw_integral")


def test_master_runtime_process_state_owns_cross_cycle_state() -> None:
    import master.motion_runtime as runtime

    state = runtime.create_runtime_state(hw_bundle=None)

    assert hasattr(state, "heading_deg")
    assert hasattr(state, "odom")
    assert hasattr(state, "target_heading_deg")
    assert hasattr(state, "heading_target_ready")


def test_master_runtime_process_state_uses_clear_public_type_name() -> None:
    import master.motion_runtime as runtime

    state = runtime.create_runtime_state(hw_bundle=None)

    assert type(state).__name__ == "MotionRuntimeState"


def test_master_motion_runtime_legacy_actions_forward_to_process_functions(
    monkeypatch,
) -> None:
    import master.motion_runtime as runtime

    legacy_runtime = runtime.MotionRuntime()
    calls = []

    def _fake_apply_motion_target(state, target):
        calls.append(("apply", state, dict(target)))
        return {"kind": "hold"}

    def _fake_resolve_heading_hold_target_from_state(
        state, current_heading_deg, hw_bundle=None, cycle_token=None
    ):
        calls.append(
            (
                "heading",
                state,
                float(current_heading_deg),
                hw_bundle,
                cycle_token,
            )
        )
        return {"kind": "vel", "vx": 0.0, "vy": 0.0, "omega": 1.0}

    def _fake_run_motion_cycle(state, hw_bundle=None, cycle_token=None):
        calls.append(("loop", state, hw_bundle, cycle_token))
        return {"target": {"kind": "hold"}}

    monkeypatch.setattr(runtime, "apply_motion_target", _fake_apply_motion_target)
    monkeypatch.setattr(
        runtime,
        "resolve_heading_hold_target_from_state",
        _fake_resolve_heading_hold_target_from_state,
        raising=False,
    )
    monkeypatch.setattr(runtime, "run_motion_cycle", _fake_run_motion_cycle)

    legacy_runtime.apply_self_target({"kind": "hold"})
    token = object()
    legacy_runtime.update_heading_hold(current_heading_deg=12.0, cycle_token=token)
    legacy_runtime.execute_control_loop(cycle_token=token)

    assert calls == [
        ("apply", legacy_runtime, {"kind": "hold"}),
        ("heading", legacy_runtime, 12.0, legacy_runtime.hw_bundle, token),
        ("loop", legacy_runtime, legacy_runtime.hw_bundle, token),
    ]


def test_master_motion_runtime_reuses_process_state_shape() -> None:
    import master.motion_runtime as runtime

    legacy_runtime = runtime.MotionRuntime()

    assert isinstance(legacy_runtime, runtime.MotionRuntimeState)
