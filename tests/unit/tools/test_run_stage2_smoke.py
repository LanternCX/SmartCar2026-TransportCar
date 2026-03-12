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


def test_parse_probe_output_accepts_printed_lite_summary_dict() -> None:
    result = parse_probe_output(
        "{'status': 'ok', 'reason': 'ok', 'transport_mode': 'lite', "
        "'init_ok': 0, 'query_count': 9, 'missing_queries': [], 'query_ok': 1, "
        "'query_outputs': {'health': '?health=alive:1'}, 'step_ok': 0, "
        "'tick_count': 0, 'snapshots': {}, 'transport_source_ok': 1, 'query_uart_ok': 1}\n"
    )

    assert result.status == "ok"
    assert result.details["smoke"]["mode"] == "lite"
    assert result.details["queries"]["count"] == "9"
    assert result.details["queries"]["missing"] == "none"


def test_parse_probe_output_accepts_summary_dict_after_preview_lines() -> None:
    result = parse_probe_output(
        "执行预览: mpy-cli run --path .agent/stage2_smoke_probe.py\n"
        "连接端口: /dev/cu.usbmodem1101\n"
        "{'status': 'ok', 'reason': 'ok', 'transport_mode': 'lite', "
        "'init_ok': 0, 'query_count': 9, 'missing_queries': [], 'query_ok': 1, "
        "'query_outputs': {'health': '?health=alive:1'}, 'step_ok': 0, "
        "'tick_count': 0, 'snapshots': {}, 'transport_source_ok': 1, 'query_uart_ok': 1}\n"
    )

    assert result.status == "ok"
    assert result.details["smoke"]["mode"] == "lite"
    assert result.details["queries"]["count"] == "9"
    assert result.details["queries"]["missing"] == "none"


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


def test_run_probe_tolerates_incremental_delete_miss_during_deploy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCompletedProcess:
        def __init__(self, stdout="", stderr="", returncode=0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    outputs = {
        "plan": FakeCompletedProcess(),
        "deploy": FakeCompletedProcess(
            stdout=(
                "INFO upload ok\n"
                "ERROR 删除失败 [2/3]: :services/command_router.py | "
                "mpremote: rm: services/command_router.py: No such file or directory.\n"
                "ERROR 删除失败 [3/3]: :services/commander.py | "
                "mpremote: rm: services/commander.py: No such file or directory.\n"
            ),
            returncode=1,
        ),
        "upload": FakeCompletedProcess(),
        "run": FakeCompletedProcess(
            "STAGE2 status=ok\n"
            "STAGE2 queries count=9 missing=none\n"
            "STAGE2 smoke mode=full init=1 queries=1 step=1 tick_count=1 snapshots=health;tick;imu;enc;motor;vision\n"
        ),
        "delete": FakeCompletedProcess(),
    }

    monkeypatch.setattr(
        stage2_runner,
        "_run_command",
        lambda command: outputs[command[1]],
    )
    monkeypatch.setattr(stage2_runner.time, "sleep", lambda _seconds: None)

    result = stage2_runner.run_probe("/dev/cu.usbmodem1101")

    assert result.status == "ok"


def test_run_probe_keeps_real_deploy_failures_as_deploy_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCompletedProcess:
        def __init__(self, stdout="", stderr="", returncode=0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    outputs = {
        "plan": FakeCompletedProcess(),
        "deploy": FakeCompletedProcess(
            stdout="ERROR 删除失败 [1/1]: :services/transport_car.py | permission denied\n",
            returncode=1,
        ),
    }

    monkeypatch.setattr(
        stage2_runner,
        "_run_command",
        lambda command: outputs[command[1]],
    )

    result = stage2_runner.run_probe("/dev/cu.usbmodem1101")

    assert result.status == "deploy_failed"
    assert "permission denied" in result.reason


def test_run_probe_tolerates_wrapped_delete_miss_lines_in_deploy_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCompletedProcess:
        def __init__(self, stdout="", stderr="", returncode=0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    deploy_stdout = (
        "INFO 开始删除\n"
        "ERROR 删除失败\n"
        "[2/87]: :services/command_router.py | mpremote: rm:\n"
        "services/command_router.py: No such file or directory.\n"
        "部署完成: success=52 failure=35\n"
        "部署完成, 但存在失败项:\n"
        "- delete :services/command_router.py -> No such file or directory.\n"
        "- delete :services/commander.py -> No such file or directory.\n"
    )
    outputs = {
        "plan": FakeCompletedProcess(),
        "deploy": FakeCompletedProcess(stdout=deploy_stdout, returncode=1),
        "upload": FakeCompletedProcess(),
        "run": FakeCompletedProcess(
            "STAGE2 status=ok\n"
            "STAGE2 queries count=9 missing=none\n"
            "STAGE2 smoke mode=full init=1 queries=1 step=1 tick_count=1 snapshots=health;tick;imu;enc;motor;vision\n"
        ),
        "delete": FakeCompletedProcess(),
    }

    monkeypatch.setattr(
        stage2_runner, "_run_command", lambda command: outputs[command[1]]
    )
    monkeypatch.setattr(stage2_runner.time, "sleep", lambda _seconds: None)

    result = stage2_runner.run_probe("/dev/cu.usbmodem1101")

    assert result.status == "ok"
