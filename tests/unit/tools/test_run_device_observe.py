"""Stage 3 设备观测执行器单元测试."""

import pytest

from tools.run_device_observe import build_probe_commands, parse_probe_output


pytestmark = pytest.mark.unit


def test_build_mpy_cli_commands_include_upload_run_and_delete() -> None:
    commands = build_probe_commands(port="/dev/cu.usbmodem1101")

    assert commands[0] == [
        "mpy-cli",
        "plan",
        "--mode",
        "incremental",
        "--port",
        "/dev/cu.usbmodem1101",
        "--no-interactive",
        "--yes",
    ]
    assert commands[1][0:2] == ["mpy-cli", "upload"]
    assert commands[2][0:2] == ["mpy-cli", "run"]
    assert commands[3][0:2] == ["mpy-cli", "delete"]
    assert ".agent/device_observe_probe.py" in commands[1]
    assert ".agent/device_observe_probe.py" in commands[2]
    assert ".agent/device_observe_probe.py" in commands[3]


def test_parse_probe_output_collects_observe_snapshots() -> None:
    result = parse_probe_output(
        "OBSERVE health alive=1 uptime_ms=1500 lock=0 rear=0 last_err=none vision_state=IDLE\n"
        "OBSERVE tick count=20 last_us=5100 max_us=5200 avg_us=5005 overrun=0\n"
        "OBSERVE done status=ok\n"
    )

    assert result.status == "ok"
    assert result.reason == "ok"
    assert result.snapshots["health"]["alive"] == "1"
    assert result.snapshots["tick"]["overrun"] == "0"


def test_parse_probe_output_marks_observe_failure_on_overrun() -> None:
    result = parse_probe_output(
        "OBSERVE tick count=20 last_us=5100 max_us=9001 avg_us=5200 overrun=3\n"
        "OBSERVE done status=ok\n"
    )

    assert result.status == "observe_failed"
    assert "overrun" in result.reason


def test_parse_probe_output_marks_probe_failure_when_tick_missing() -> None:
    result = parse_probe_output("OBSERVE health alive=1 uptime_ms=1000\n")

    assert result.status == "probe_failed"
    assert "tick" in result.reason
