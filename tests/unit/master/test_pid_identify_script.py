def test_pid_identify_script_supports_direct_board_imports() -> None:
    from pathlib import Path

    content = Path("src/master/script/pid_identify.py").read_text(encoding="utf-8")

    assert "from machine import Pin" in content
    assert "from seekfree import MOTOR_CONTROLLER" in content
    assert "from smartcar import encoder, ticker" in content
    assert "DualWindowRegressionFilter" in content
    assert "LowPassFilter" in content


def test_pid_identify_script_has_direct_run_guard() -> None:
    from pathlib import Path

    content = Path("src/master/script/pid_identify.py").read_text(encoding="utf-8")

    assert 'if __name__ == "__main__"' in content


def test_format_ident_text_writes_gain_tau_lines() -> None:
    from master.script.pid_identify import format_ident_text

    text = format_ident_text(
        {
            "m": (1.25, 0.5),
            "l": (None, None),
            "r": (2.5, 0.75),
        }
    )

    assert text == "m 1.250000 0.500000\nr 2.500000 0.750000\n"


def test_build_ident_filter_bank_uses_legacy_filter_params(monkeypatch) -> None:
    import master.script.pid_identify as script

    captured = {"alphas": [], "windows": []}

    class FakeLowPassFilter:
        def __init__(self, alpha, initial=0.0):
            captured["alphas"].append((float(alpha), float(initial)))

    class FakeDualWindowRegressionFilter:
        def __init__(self, tick_ms, long_window, short_window, combine_w=0.65):
            captured["windows"].append(
                (int(tick_ms), int(long_window), int(short_window), float(combine_w))
            )

    monkeypatch.setattr(script, "LowPassFilter", FakeLowPassFilter)
    monkeypatch.setattr(
        script, "DualWindowRegressionFilter", FakeDualWindowRegressionFilter
    )

    bank = script.build_ident_filter_bank(tick_ms=5, wheel_names=("m", "l", "r"))

    assert tuple(bank.keys()) == ("m", "l", "r")
    assert captured["alphas"] == [
        (0.5, 0.0),
        (0.9, 0.0),
        (0.5, 0.0),
        (0.9, 0.0),
        (0.5, 0.0),
        (0.9, 0.0),
    ]
    assert captured["windows"] == [
        (5, 30, 8, 0.65),
        (5, 30, 8, 0.65),
        (5, 30, 8, 0.65),
    ]


def test_filter_ident_speed_uses_legacy_scale_divided_by_three() -> None:
    import master.script.pid_identify as script

    class FakeLowPassFilter:
        def __init__(self, multiplier):
            self.multiplier = float(multiplier)

        def update(self, value):
            return float(value) * self.multiplier

    class FakeDualFilter:
        def update(self, value):
            return (float(value) + 3.0, 0.0, 0.0)

    speed = script.filter_ident_speed(
        {
            "input_lpf": FakeLowPassFilter(2.0),
            "dual_filter": FakeDualFilter(),
            "output_lpf": FakeLowPassFilter(1.0),
        },
        6.0,
    )

    assert speed == 5.0


def test_pid_identify_uses_legacy_encoder_mapping() -> None:
    from master.script.pid_identify import LEGACY_ENCODER_PINS

    assert LEGACY_ENCODER_PINS == {
        "m": ("D15", "D16", True),
        "l": ("C2", "C3", True),
        "r": ("C0", "C1", True),
    }


def test_pid_identify_uses_legacy_motor_mapping() -> None:
    from master.script.pid_identify import LEGACY_MOTOR_PORTS

    assert LEGACY_MOTOR_PORTS == {
        "m": ("PWM_C30_DIR_C31", False),
        "l": ("PWM_D6_DIR_D7", True),
        "r": ("PWM_D4_DIR_D5", False),
    }


def test_summarize_ident_buffer_reports_first_last_and_tail_avg() -> None:
    import master.script.pid_identify as script

    buffers = script.create_ident_buffers(("m",), 8)
    for index, value in enumerate((0.0, 1.0, 2.0, 3.0, 4.0), start=1):
        script.push_ident_sample("m", index * 5, value, buffers, max_samples=8)

    summary = script.summarize_ident_buffer(
        "m", buffers, max_samples=8, preview_count=2
    )

    assert summary == {
        "count": 5,
        "first": ((5.0, 0.0), (10.0, 1.0)),
        "last": ((20.0, 3.0), (25.0, 4.0)),
        "min": 0.0,
        "max": 4.0,
        "tail_avg": 2.0,
    }


def test_pid_identify_main_prints_failure_summary_before_raising(
    tmp_path, monkeypatch, capsys
) -> None:
    import master.script.pid_identify as script

    callback_ref = {"fn": None}

    class FakeTicker:
        def capture_list(self, *items):
            return None

        def callback(self, fn):
            callback_ref["fn"] = fn

        def start(self, _tick_ms):
            return None

        def stop(self):
            return None

    class FakeEncoderPort:
        def __init__(self, values):
            self.values = list(values)
            self.index = 0

        def get(self):
            value = self.values[min(self.index, len(self.values) - 1)]
            self.index += 1
            return value

    class FakeMotorPort:
        def duty(self, _duty):
            return None

    class FakeLed:
        def toggle(self):
            return None

    class FakeSwitch:
        def value(self):
            return 1

    encoders = {
        "m": FakeEncoderPort((0.0, 0.0, 1.0, 2.0)),
        "l": FakeEncoderPort((0.0, 1.0, 2.0, 3.0)),
        "r": FakeEncoderPort((0.0, 2.0, 3.0, 4.0)),
    }

    monkeypatch.setattr(
        script, "_read_board_drivers", lambda: {"ticker": lambda _channel: FakeTicker()}
    )
    monkeypatch.setattr(script, "build_ident_encoder_bundle", lambda _drivers: encoders)
    monkeypatch.setattr(
        script,
        "build_ident_motor_bundle",
        lambda _drivers: {name: FakeMotorPort() for name in ("m", "l", "r")},
    )
    monkeypatch.setattr(script, "build_ident_status_led", lambda _drivers: FakeLed())
    monkeypatch.setattr(
        script, "build_ident_stop_switch", lambda _drivers: FakeSwitch()
    )
    monkeypatch.setattr(
        script,
        "build_ident_filter_bank",
        lambda tick_ms, wheel_names: {name: object() for name in wheel_names},
    )
    monkeypatch.setattr(
        script,
        "filter_ident_speed",
        lambda _filter_state, raw_ticks: float(raw_ticks),
    )
    monkeypatch.setattr(
        script, "identify_wheel_from_buffer", lambda *args, **kwargs: (None, None)
    )
    monkeypatch.setattr(script.gc, "collect", lambda: _trigger_callback(callback_ref))

    import pytest

    with pytest.raises(RuntimeError, match="参数辨识失败"):
        script.main(
            duration_ms=20, tick_ms=5, file_path=str(tmp_path / "ident_params.txt")
        )

    output = capsys.readouterr().out
    assert "m debug" in output
    assert "first=" in output
    assert "last=" in output
    assert "tail_avg=" in output


def test_pid_identify_main_samples_and_saves_ident_results(
    tmp_path, monkeypatch
) -> None:
    import master.script.pid_identify as script

    ticker_state = {"tick_ms": None, "captured": None, "started": 0, "stopped": 0}
    callback_ref = {"fn": None}

    class FakeTicker:
        def capture_list(self, *items):
            ticker_state["captured"] = items

        def callback(self, fn):
            callback_ref["fn"] = fn

        def start(self, tick_ms):
            ticker_state["tick_ms"] = tick_ms
            ticker_state["started"] += 1

        def stop(self):
            ticker_state["stopped"] += 1

    class FakeEncoderPort:
        def __init__(self, values):
            self.values = list(values)
            self.index = 0

        def get(self):
            value = self.values[min(self.index, len(self.values) - 1)]
            self.index += 1
            return value

    class FakeMotorPort:
        def __init__(self):
            self.calls = []

        def duty(self, duty):
            self.calls.append(int(duty))

    class FakeLed:
        def toggle(self):
            return None

    class FakeSwitch:
        def value(self):
            return 1

    motors = {name: FakeMotorPort() for name in ("m", "l", "r")}
    encoders = {
        "m": FakeEncoderPort((1, 2, 3, 4)),
        "l": FakeEncoderPort((2, 3, 4, 5)),
        "r": FakeEncoderPort((3, 4, 5, 6)),
    }

    monkeypatch.setattr(
        script, "_read_board_drivers", lambda: {"ticker": lambda _channel: FakeTicker()}
    )
    monkeypatch.setattr(script, "build_ident_encoder_bundle", lambda _drivers: encoders)
    monkeypatch.setattr(script, "build_ident_motor_bundle", lambda _drivers: motors)
    monkeypatch.setattr(script, "build_ident_status_led", lambda _drivers: FakeLed())
    monkeypatch.setattr(
        script, "build_ident_stop_switch", lambda _drivers: FakeSwitch()
    )
    monkeypatch.setattr(
        script,
        "build_ident_filter_bank",
        lambda tick_ms, wheel_names: {name: object() for name in wheel_names},
    )
    monkeypatch.setattr(
        script,
        "filter_ident_speed",
        lambda _filter_state, raw_ticks: float(raw_ticks),
    )
    monkeypatch.setattr(
        script,
        "identify_wheel_from_buffer",
        lambda name, buffers, step_duty, max_samples=None: (
            float(
                min(
                    int(buffers[name]["count"]),
                    int(max_samples or buffers[name]["count"]),
                )
            ),
            float(
                buffers[name]["t"][
                    (int(buffers[name]["count"]) - 1)
                    % int(max_samples or len(buffers[name]["t"]))
                ]
            )
            / 1000.0,
        ),
    )
    monkeypatch.setattr(script.gc, "collect", lambda: _trigger_callback(callback_ref))

    output_file = tmp_path / "ident_params.txt"
    text = script.main(
        duration_ms=20, step_duty=200, tick_ms=5, file_path=str(output_file)
    )

    assert text == ("m 4.000000 0.020000\nl 4.000000 0.020000\nr 4.000000 0.020000\n")
    assert output_file.read_text(encoding="utf-8") == text
    assert ticker_state == {
        "tick_ms": 5,
        "captured": tuple(encoders[name] for name in ("m", "l", "r")),
        "started": 1,
        "stopped": 1,
    }
    assert all(motor.calls == [200, 200, 200, 200, 0] for motor in motors.values())


def _trigger_callback(callback_ref) -> None:
    callback = callback_ref["fn"]
    if callback is not None:
        callback(None)


def test_pid_identify_main_caps_buffer_depth_to_legacy_limit(
    tmp_path, monkeypatch
) -> None:
    import master.script.pid_identify as script

    captured = {"max_samples": 0}
    callback_ref = {"fn": None}

    class FakeTicker:
        def capture_list(self, *items):
            return None

        def callback(self, fn):
            callback_ref["fn"] = fn

        def start(self, _tick_ms):
            return None

        def stop(self):
            return None

    class FakeEncoderPort:
        def get(self):
            return 1.0

    class FakeMotorPort:
        def duty(self, _duty):
            return None

    class FakeLed:
        def toggle(self):
            return None

    class FakeSwitch:
        def value(self):
            return 1

    monkeypatch.setattr(
        script, "_read_board_drivers", lambda: {"ticker": lambda _channel: FakeTicker()}
    )
    monkeypatch.setattr(
        script,
        "build_ident_encoder_bundle",
        lambda _drivers: {name: FakeEncoderPort() for name in ("m", "l", "r")},
    )
    monkeypatch.setattr(
        script,
        "build_ident_motor_bundle",
        lambda _drivers: {name: FakeMotorPort() for name in ("m", "l", "r")},
    )
    monkeypatch.setattr(script, "build_ident_status_led", lambda _drivers: FakeLed())
    monkeypatch.setattr(
        script, "build_ident_stop_switch", lambda _drivers: FakeSwitch()
    )
    monkeypatch.setattr(
        script, "identify_wheel_from_buffer", lambda *args, **kwargs: (1.0, 0.1)
    )
    monkeypatch.setattr(
        script,
        "build_ident_filter_bank",
        lambda tick_ms, wheel_names: {name: object() for name in wheel_names},
    )
    monkeypatch.setattr(
        script,
        "filter_ident_speed",
        lambda _filter_state, raw_ticks: float(raw_ticks),
    )
    monkeypatch.setattr(script.gc, "collect", lambda: _trigger_callback(callback_ref))

    original_create_ident_buffers = script.create_ident_buffers

    def _create_ident_buffers(names, max_samples):
        captured["max_samples"] = int(max_samples)
        return original_create_ident_buffers(names, max_samples)

    monkeypatch.setattr(script, "create_ident_buffers", _create_ident_buffers)

    output_file = tmp_path / "ident_params.txt"
    script.main(duration_ms=4000, tick_ms=5, file_path=str(output_file))

    assert captured["max_samples"] == 600


def test_resolve_ident_plan_matches_legacy_default_run() -> None:
    from master.script.pid_identify import resolve_ident_plan

    plan = resolve_ident_plan(duration_ms=4000, tick_ms=5)

    assert plan == {
        "duration_ms": 4000,
        "sample_count": 800,
        "buffer_samples": 600,
    }


def test_pid_identify_main_does_not_materialize_sample_list(
    tmp_path, monkeypatch
) -> None:
    import master.script.pid_identify as script

    callback_ref = {"fn": None}

    class FakeTicker:
        def capture_list(self, *items):
            return None

        def callback(self, fn):
            callback_ref["fn"] = fn

        def start(self, _tick_ms):
            return None

        def stop(self):
            return None

    class FakeEncoderPort:
        def get(self):
            return 1.0

    class FakeMotorPort:
        def duty(self, _duty):
            return None

    class FakeLed:
        def toggle(self):
            return None

    class FakeSwitch:
        def value(self):
            return 1

    monkeypatch.setattr(
        script, "_read_board_drivers", lambda: {"ticker": lambda _channel: FakeTicker()}
    )
    monkeypatch.setattr(
        script,
        "build_ident_encoder_bundle",
        lambda _drivers: {name: FakeEncoderPort() for name in ("m", "l", "r")},
    )
    monkeypatch.setattr(
        script,
        "build_ident_motor_bundle",
        lambda _drivers: {name: FakeMotorPort() for name in ("m", "l", "r")},
    )
    monkeypatch.setattr(script, "build_ident_status_led", lambda _drivers: FakeLed())
    monkeypatch.setattr(
        script, "build_ident_stop_switch", lambda _drivers: FakeSwitch()
    )
    monkeypatch.setattr(
        script, "identify_wheel_from_buffer", lambda *args, **kwargs: (1.0, 0.1)
    )
    monkeypatch.setattr(
        script,
        "build_ident_filter_bank",
        lambda tick_ms, wheel_names: {name: object() for name in wheel_names},
    )
    monkeypatch.setattr(
        script,
        "filter_ident_speed",
        lambda _filter_state, raw_ticks: float(raw_ticks),
    )
    monkeypatch.setattr(script.gc, "collect", lambda: _trigger_callback(callback_ref))

    output_file = tmp_path / "ident_params.txt"
    text = script.main(duration_ms=20, tick_ms=5, file_path=str(output_file))

    assert text == ("m 1.000000 0.100000\nl 1.000000 0.100000\nr 1.000000 0.100000\n")
