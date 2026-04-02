def test_assistant_runtime_params_exposes_required_keys() -> None:
    import assistant.runtime_params as runtime_params

    expected = {
        "FOLLOW_TIMEOUT_MS",
        "CONTROL_TICK_MS",
        "FOLLOW_OUTPUT_LIMIT",
        "PID_MAP",
        "SPEED_FILTER_WINDOW",
        "SPEED_DIFF_MAX_DELTA",
        "GYRO_LPF_ALPHA",
    }

    assert expected.issubset(set(dir(runtime_params)))
    assert set(runtime_params.PID_MAP.keys()) == {"m", "l", "r"}


def test_assistant_runtime_params_does_not_expose_gyro_scale_board_fact() -> None:
    import assistant.config as config
    import assistant.runtime_params as runtime_params

    assert (hasattr(config, "GYRO_SCALE"), hasattr(runtime_params, "GYRO_SCALE")) == (
        True,
        False,
    ), (
        "GYRO_SCALE 应由 config 承载，且不应继续暴露在 runtime_params；"
        f"当前 config={hasattr(config, 'GYRO_SCALE')}, "
        f"runtime_params={hasattr(runtime_params, 'GYRO_SCALE')}"
    )


def test_assistant_runtime_params_does_not_expose_gyro_offset_file_board_fact() -> None:
    import assistant.config as config
    import assistant.runtime_params as runtime_params

    assert (
        hasattr(config, "GYRO_OFFSET_FILE"),
        hasattr(runtime_params, "GYRO_OFFSET_FILE"),
    ) == (True, False), (
        "GYRO_OFFSET_FILE 应由 config 承载，且不应继续暴露在 runtime_params；"
        f"当前 config={hasattr(config, 'GYRO_OFFSET_FILE')}, "
        f"runtime_params={hasattr(runtime_params, 'GYRO_OFFSET_FILE')}"
    )


def test_assistant_runtime_params_does_not_expose_ident_results_file_board_fact() -> (
    None
):
    import assistant.config as config
    import assistant.runtime_params as runtime_params

    assert (
        hasattr(config, "IDENT_RESULTS_FILE"),
        hasattr(runtime_params, "IDENT_RESULTS_FILE"),
    ) == (True, False), (
        "IDENT_RESULTS_FILE 应由 config 承载，且不应继续暴露在 runtime_params；"
        f"当前 config={hasattr(config, 'IDENT_RESULTS_FILE')}, "
        f"runtime_params={hasattr(runtime_params, 'IDENT_RESULTS_FILE')}"
    )


def test_assistant_runtime_uses_runtime_param_follow_timeout() -> None:
    import assistant.runtime_params as runtime_params
    from assistant.app import AssistantApp

    old_timeout = runtime_params.FOLLOW_TIMEOUT_MS
    runtime_params.FOLLOW_TIMEOUT_MS = 10
    try:
        app = AssistantApp()
        app.handle_line("follow=1,seq=8,valid=1,dx=0.10,dy=0.00", now_ms=0)
        reply = app.tick(now_ms=20)
    finally:
        runtime_params.FOLLOW_TIMEOUT_MS = old_timeout

    assert reply == "TIMEOUT,last_seq=8"


def test_assistant_runtime_default_chassis_timeout_reads_runtime_params() -> None:
    import assistant.runtime_params as runtime_params
    from assistant.motion_runtime import (
        apply_runtime_command,
        create_runtime_state,
        run_base_cycle,
    )

    old_timeout = runtime_params.FOLLOW_TIMEOUT_MS
    runtime_params.FOLLOW_TIMEOUT_MS = 10
    try:
        state = create_runtime_state()
        apply_runtime_command(
            state,
            type(
                "Cmd",
                (),
                {"kind": "follow", "seq": 1, "valid": 1, "dx": 0.0, "dy": 0.0},
            )(),
            now_ms=0,
        )
        reply = run_base_cycle(state, now_ms=20)
    finally:
        runtime_params.FOLLOW_TIMEOUT_MS = old_timeout

    assert reply == "DONE"
    assert state.timeout is True


def test_assistant_runtime_uses_runtime_param_output_limit() -> None:
    import assistant.runtime_params as runtime_params
    from assistant.motion_runtime import apply_runtime_command, create_runtime_state
    from assistant.protocol import parse_command

    old_limit = runtime_params.FOLLOW_OUTPUT_LIMIT
    runtime_params.FOLLOW_OUTPUT_LIMIT = 123
    try:
        state = create_runtime_state(timeout_ms=runtime_params.FOLLOW_TIMEOUT_MS)
        apply_runtime_command(
            state, parse_command("follow=1,seq=1,valid=1,dx=999.0,dy=0.0"), now_ms=0
        )
    finally:
        runtime_params.FOLLOW_OUTPUT_LIMIT = old_limit

    assert state.velocity_command[0] <= 123


def test_assistant_runtime_reads_runtime_pid_and_filter_params() -> None:
    import assistant.runtime_params as runtime_params
    from assistant.motion_runtime import create_runtime_state

    old_pid_map = runtime_params.PID_MAP
    old_window = runtime_params.SPEED_FILTER_WINDOW
    old_diff = runtime_params.SPEED_DIFF_MAX_DELTA
    old_alpha = runtime_params.GYRO_LPF_ALPHA
    runtime_params.PID_MAP = {"m": (1, 2, 3), "l": (4, 5, 6), "r": (7, 8, 9)}
    runtime_params.SPEED_FILTER_WINDOW = 9
    runtime_params.SPEED_DIFF_MAX_DELTA = 1.5
    runtime_params.GYRO_LPF_ALPHA = 0.5
    try:
        state = create_runtime_state(timeout_ms=runtime_params.FOLLOW_TIMEOUT_MS)
    finally:
        runtime_params.PID_MAP = old_pid_map
        runtime_params.SPEED_FILTER_WINDOW = old_window
        runtime_params.SPEED_DIFF_MAX_DELTA = old_diff
        runtime_params.GYRO_LPF_ALPHA = old_alpha

    assert state.pid_map == {"m": (1, 2, 3), "l": (4, 5, 6), "r": (7, 8, 9)}
    assert state.speed_filter_window == 9
    assert state.speed_diff_max_delta == 1.5
    assert state.gyro_lpf_alpha == 0.5
