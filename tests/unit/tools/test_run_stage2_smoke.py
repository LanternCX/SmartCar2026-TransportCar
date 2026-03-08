"""Stage 2 裸片 smoke 执行器单元测试."""

import pytest

import tools.run_stage2_smoke as stage2_runner
from tools.run_stage2_smoke import build_probe_commands, parse_probe_output


pytestmark = pytest.mark.unit


def test_build_mpy_cli_commands_include_stage2_probe_paths() -> None:
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
    assert commands[1][0:2] == ["mpy-cli", "deploy"]
    assert commands[2][0:2] == ["mpy-cli", "upload"]
    assert commands[3][0:2] == ["mpy-cli", "run"]
    assert commands[4][0:2] == ["mpy-cli", "delete"]
    assert ".agent/stage2_smoke_probe.py" in commands[2]
    assert ".agent/stage2_smoke_probe.py" in commands[3]
    assert ".agent/stage2_smoke_probe.py" in commands[4]


def test_parse_probe_output_marks_success_when_smoke_summary_is_complete() -> None:
    result = parse_probe_output(
        "STAGE2 status=ok\n"
        "STAGE2 queries count=6 missing=none\n"
        "STAGE2 smoke mode=full init=1 queries=1 step=1 tick_count=1 snapshots=health;tick;imu;enc;motor;vision\n"
    )

    assert result.status == "ok"
    assert result.reason == "ok"
    assert result.details["smoke"]["queries"] == "1"
    assert result.details["smoke"]["step"] == "1"
    assert result.details["queries"]["missing"] == "none"


def test_parse_probe_output_accepts_lite_mode_when_query_chain_is_ok() -> None:
    result = parse_probe_output(
        "STAGE2 status=ok\n"
        "STAGE2 queries count=6 missing=none\n"
        "STAGE2 smoke mode=lite init=0 queries=1 step=0 tick_count=0 snapshots=none\n"
    )

    assert result.status == "ok"
    assert result.details["smoke"]["mode"] == "lite"


def test_parse_probe_output_marks_probe_failure_on_stage2_fail_line() -> None:
    result = parse_probe_output("STAGE2 status=fail reason=import_error\n")

    assert result.status == "probe_failed"
    assert result.reason == "import_error"


def test_parse_probe_output_marks_probe_failure_when_smoke_line_missing() -> None:
    result = parse_probe_output("STAGE2 status=ok\n")

    assert result.status == "probe_failed"
    assert "smoke" in result.reason


def test_parse_probe_output_marks_probe_failure_when_query_probe_missing() -> None:
    result = parse_probe_output(
        "STAGE2 status=ok\n"
        "STAGE2 queries count=6 missing=none\n"
        "STAGE2 smoke init=1 queries=0 step=1 tick_count=1 snapshots=health;tick;imu;enc;motor;vision\n"
    )

    assert result.status == "probe_failed"
    assert "query" in result.reason


def test_run_probe_waits_between_deploy_upload_and_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = []
    sleeps = []

    class FakeCompletedProcess:
        def __init__(self, stdout="", returncode=0):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    def fake_run(command):
        commands.append(command[:2])
        if command[1] == "run":
            return FakeCompletedProcess(
                "STAGE2 status=ok\n"
                "STAGE2 queries count=6 missing=none\n"
                "STAGE2 smoke init=1 queries=1 step=1 tick_count=1 snapshots=health;tick;imu;enc;motor;vision\n"
            )
        return FakeCompletedProcess()

    class FakeTime:
        @staticmethod
        def sleep(seconds):
            sleeps.append(seconds)

    monkeypatch.setattr(stage2_runner, "_run_command", fake_run)
    monkeypatch.setattr(stage2_runner, "time", FakeTime, raising=False)

    result = stage2_runner.run_probe("/dev/cu.usbmodem1101")

    assert result.status == "ok"
    assert commands == [
        ["mpy-cli", "plan"],
        ["mpy-cli", "deploy"],
        ["mpy-cli", "upload"],
        ["mpy-cli", "run"],
        ["mpy-cli", "delete"],
    ]
    assert len(sleeps) >= 2
