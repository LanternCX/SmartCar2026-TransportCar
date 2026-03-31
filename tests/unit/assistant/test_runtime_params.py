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
    from assistant.ctrl.chassis import ChassisRuntime

    old_timeout = runtime_params.FOLLOW_TIMEOUT_MS
    runtime_params.FOLLOW_TIMEOUT_MS = 10
    try:
        runtime = ChassisRuntime()
        runtime.apply_command(
            type(
                "Cmd",
                (),
                {"kind": "follow", "seq": 1, "valid": 1, "dx": 0.0, "dy": 0.0},
            )(),
            now_ms=0,
        )
        reply = runtime.tick(now_ms=20)
    finally:
        runtime_params.FOLLOW_TIMEOUT_MS = old_timeout

    assert reply == "DONE"
    assert runtime.state.timeout is True


def test_assistant_runtime_uses_runtime_param_output_limit() -> None:
    import assistant.runtime_params as runtime_params
    from assistant.ctrl.chassis import ChassisRuntime
    from assistant.protocol import parse_command

    old_limit = runtime_params.FOLLOW_OUTPUT_LIMIT
    runtime_params.FOLLOW_OUTPUT_LIMIT = 123
    try:
        runtime = ChassisRuntime(timeout_ms=runtime_params.FOLLOW_TIMEOUT_MS)
        runtime.apply_command(
            parse_command("follow=1,seq=1,valid=1,dx=999.0,dy=0.0"), now_ms=0
        )
    finally:
        runtime_params.FOLLOW_OUTPUT_LIMIT = old_limit

    assert runtime.state.velocity_command[0] <= 123


def test_assistant_runtime_reads_runtime_pid_and_filter_params() -> None:
    import assistant.runtime_params as runtime_params
    from assistant.ctrl.chassis import ChassisRuntime

    old_pid_map = runtime_params.PID_MAP
    old_window = runtime_params.SPEED_FILTER_WINDOW
    old_diff = runtime_params.SPEED_DIFF_MAX_DELTA
    old_alpha = runtime_params.GYRO_LPF_ALPHA
    runtime_params.PID_MAP = {"m": (1, 2, 3), "l": (4, 5, 6), "r": (7, 8, 9)}
    runtime_params.SPEED_FILTER_WINDOW = 9
    runtime_params.SPEED_DIFF_MAX_DELTA = 1.5
    runtime_params.GYRO_LPF_ALPHA = 0.5
    try:
        runtime = ChassisRuntime(timeout_ms=runtime_params.FOLLOW_TIMEOUT_MS)
    finally:
        runtime_params.PID_MAP = old_pid_map
        runtime_params.SPEED_FILTER_WINDOW = old_window
        runtime_params.SPEED_DIFF_MAX_DELTA = old_diff
        runtime_params.GYRO_LPF_ALPHA = old_alpha

    assert runtime.pid_map == {"m": (1, 2, 3), "l": (4, 5, 6), "r": (7, 8, 9)}
    assert runtime.speed_filter_window == 9
    assert runtime.speed_diff_max_delta == 1.5
    assert runtime.gyro_lpf_alpha == 0.5
