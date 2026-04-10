def test_master_motion_runtime_process_entry_reads_yaw_runtime_params() -> None:
    import master.runtime_params as runtime_params
    import master.motion_runtime as runtime

    old_kp = runtime_params.YAW_KP
    runtime_params.YAW_KP = 0.42
    try:
        state = runtime.create_runtime_state(hw_bundle=None)
    finally:
        runtime_params.YAW_KP = old_kp

    assert state.yaw_kp == 0.42


def test_master_motion_runtime_process_entry_reads_yaw_stability_params() -> None:
    import master.runtime_params as runtime_params
    import master.motion_runtime as runtime

    old_kd = getattr(runtime_params, "YAW_KD", None)
    old_eps = getattr(runtime_params, "HOLD_SPEED_EPS", None)
    setattr(runtime_params, "YAW_KD", 0.08)
    setattr(runtime_params, "HOLD_SPEED_EPS", 0.25)
    try:
        state = runtime.create_runtime_state(hw_bundle=None)
    finally:
        if old_kd is None:
            delattr(runtime_params, "YAW_KD")
        else:
            setattr(runtime_params, "YAW_KD", old_kd)
        if old_eps is None:
            delattr(runtime_params, "HOLD_SPEED_EPS")
        else:
            setattr(runtime_params, "HOLD_SPEED_EPS", old_eps)

    assert state.yaw_kd == 0.08
    assert state.hold_speed_eps == 0.25


def test_master_motion_runtime_logs_loaded_ident_lookup(monkeypatch) -> None:
    import master.motion_runtime as runtime

    captured = []
    ident_lookup = {
        "m": (0.00055, 0.01),
        "l": (0.000581, 0.01),
        "r": (0.000551, 0.01),
    }

    monkeypatch.setattr(runtime, "_load_ident_lookup", lambda path: dict(ident_lookup))
    monkeypatch.setattr(runtime, "_load_gyro_offsets", lambda path: (0.0,) * 6)
    monkeypatch.setattr(
        runtime,
        "_debug_print",
        lambda stage, **payload: captured.append((stage, dict(payload))),
    )

    runtime.create_runtime_state(hw_bundle=None)

    assert (
        "ident_lookup_loaded",
        {
            "path": runtime.config.IDENT_RESULTS_FILE,
            "wheel_ident": ident_lookup,
        },
    ) in captured


def test_master_motion_runtime_run_motion_cycle_tracks_latest_target() -> None:
    import master.motion_runtime as runtime

    state = runtime.create_runtime_state(hw_bundle=None)

    applied = runtime.apply_motion_target(state, {"kind": "hold"})

    assert applied == {"kind": "hold"}
    assert state.last_target == {"kind": "hold"}


def test_master_motion_runtime_run_motion_cycle_allocates_monotonic_control_seq() -> (
    None
):
    import master.motion_runtime as runtime

    state = runtime.create_runtime_state(hw_bundle=None)

    assert runtime.next_motion_control_seq(state) == 1
    assert runtime.next_motion_control_seq(state) == 2


def test_master_motion_runtime_base_ok_requires_heading_and_encoder_chain() -> None:
    import master.motion_runtime as runtime

    class FakeHeading:
        def heading_deg(self):
            return 0.0

    class FakeEncoder:
        def read_and_clear(self):
            return 0.0

    missing_state = runtime.create_runtime_state(hw_bundle={"imu": FakeHeading()})
    complete_state = runtime.create_runtime_state(
        hw_bundle={
            "imu": FakeHeading(),
            "encoders": {name: FakeEncoder() for name in ("m", "l", "r")},
        }
    )

    missing_snapshot = runtime.run_base_cycle(
        missing_state, hw_bundle=missing_state.hw_bundle, cycle_token=object()
    )
    complete_snapshot = runtime.run_base_cycle(
        complete_state, hw_bundle=complete_state.hw_bundle, cycle_token=object()
    )

    assert missing_snapshot["base_ok"] == 0
    assert complete_snapshot["base_ok"] == 1
