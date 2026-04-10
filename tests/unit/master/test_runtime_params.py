def test_master_runtime_params_exposes_required_keys() -> None:
    import master.runtime_params as runtime_params

    expected = {
        "CONTROL_TICK_MS",
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
