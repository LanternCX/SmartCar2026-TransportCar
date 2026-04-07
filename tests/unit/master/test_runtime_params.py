def test_master_runtime_params_exposes_required_keys() -> None:
    import master.runtime_params as runtime_params

    expected = {
        "FOLLOW_TIMEOUT_MS",
        "FOLLOW_CONTROL_KP_X",
        "FOLLOW_CONTROL_KP_Y",
        "FOLLOW_CENTER_DEADZONE_PX",
        "CONTROL_TICK_MS",
        "FOLLOW_OUTPUT_LIMIT",
        "PID_MAP",
        "SPEED_FILTER_WINDOW",
        "SPEED_DIFF_MAX_DELTA",
        "GYRO_LPF_ALPHA",
    }

    assert expected.issubset(set(dir(runtime_params)))
    assert set(runtime_params.PID_MAP.keys()) == {"m", "l", "r"}


def test_master_runtime_params_does_not_expose_gyro_scale_board_fact() -> None:
    import master.config as config
    import master.runtime_params as runtime_params

    assert (hasattr(config, "GYRO_SCALE"), hasattr(runtime_params, "GYRO_SCALE")) == (
        True,
        False,
    ), (
        "GYRO_SCALE 应由 config 承载，且不应继续暴露在 runtime_params；"
        f"当前 config={hasattr(config, 'GYRO_SCALE')}, "
        f"runtime_params={hasattr(runtime_params, 'GYRO_SCALE')}"
    )


def test_master_runtime_params_does_not_expose_gyro_offset_file_board_fact() -> None:
    import master.config as config
    import master.runtime_params as runtime_params

    assert (
        hasattr(config, "GYRO_OFFSET_FILE"),
        hasattr(runtime_params, "GYRO_OFFSET_FILE"),
    ) == (True, False), (
        "GYRO_OFFSET_FILE 应由 config 承载，且不应继续暴露在 runtime_params；"
        f"当前 config={hasattr(config, 'GYRO_OFFSET_FILE')}, "
        f"runtime_params={hasattr(runtime_params, 'GYRO_OFFSET_FILE')}"
    )


def test_master_runtime_params_does_not_expose_ident_results_file_board_fact() -> None:
    import master.config as config
    import master.runtime_params as runtime_params

    assert (
        hasattr(config, "IDENT_RESULTS_FILE"),
        hasattr(runtime_params, "IDENT_RESULTS_FILE"),
    ) == (True, False), (
        "IDENT_RESULTS_FILE 应由 config 承载，且不应继续暴露在 runtime_params；"
        f"当前 config={hasattr(config, 'IDENT_RESULTS_FILE')}, "
        f"runtime_params={hasattr(runtime_params, 'IDENT_RESULTS_FILE')}"
    )


def test_master_runtime_params_expose_heading_stability_keys() -> None:
    import master.runtime_params as runtime_params

    assert hasattr(runtime_params, "YAW_KD")
    assert hasattr(runtime_params, "HOLD_SPEED_EPS")


def test_master_app_uses_runtime_param_deadzone() -> None:
    import master.runtime_params as runtime_params
    from master.app import MasterApp

    old_deadzone = runtime_params.FOLLOW_CENTER_DEADZONE_PX
    runtime_params.FOLLOW_CENTER_DEADZONE_PX = 20.0
    try:
        app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
        result = app.step(
            {
                "uart": "uart6",
                "line": "v=1,s=10,x=12,y=0",
            }
        )
    finally:
        runtime_params.FOLLOW_CENTER_DEADZONE_PX = old_deadzone

    assert result["phase"] == "CENTER_HOLD"


def test_master_app_uses_runtime_param_follow_timeout() -> None:
    import master.runtime_params as runtime_params
    from master.app import MasterApp

    old_timeout = runtime_params.FOLLOW_TIMEOUT_MS
    runtime_params.FOLLOW_TIMEOUT_MS = 10
    try:
        app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
        app.step(
            {
                "uart": "uart6",
                "line": "v=1,s=1,x=12,y=0",
                "now_ms": 0,
            }
        )
        result = app.step({"now_ms": 20})
    finally:
        runtime_params.FOLLOW_TIMEOUT_MS = old_timeout

    assert result["phase"] == "MARKER_MISSING"


def test_master_app_uses_runtime_param_control_gains() -> None:
    import master.runtime_params as runtime_params
    from master.app import MasterApp

    old_kp_x = runtime_params.FOLLOW_CONTROL_KP_X
    old_kp_y = runtime_params.FOLLOW_CONTROL_KP_Y
    runtime_params.FOLLOW_CONTROL_KP_X = 2.0
    runtime_params.FOLLOW_CONTROL_KP_Y = 3.0
    try:
        app = MasterApp(active_uart="uart6", reserved_uarts=("uart8",))
        result = app.step(
            {
                "uart": "uart6",
                "line": "v=1,s=1,x=12,y=-9",
            }
        )
    finally:
        runtime_params.FOLLOW_CONTROL_KP_X = old_kp_x
        runtime_params.FOLLOW_CONTROL_KP_Y = old_kp_y

    from assistant.protocol import parse_command

    parsed = parse_command(result["assistant_command"])

    assert parsed.kind == "follow"
    assert parsed.seq == 1
    assert parsed.valid == 1
    assert parsed.dx == 24.0
    assert parsed.dy == -27.0
