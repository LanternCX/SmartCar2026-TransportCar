"""run_stage2_smoke 单元测试."""

import subprocess

from tools import run_stage2_smoke


def test_main_supports_explicit_src_root_source_dir(monkeypatch):
    """命令行应显式接受单一 src 运行根目录."""

    seen = {}

    def fake_run_probe(port, source_dir):
        seen["port"] = port
        seen["source_dir"] = source_dir
        return run_stage2_smoke.Stage2RunResult("ok", "ok", {})

    monkeypatch.setattr(run_stage2_smoke, "run_probe", fake_run_probe)
    monkeypatch.setattr(run_stage2_smoke, "_print_result", lambda result: None)

    exit_code = run_stage2_smoke.main(["--port", "/dev/ttyUSB0", "--source-dir", "src"])

    assert exit_code == 0
    assert seen == {"port": "/dev/ttyUSB0", "source_dir": "src"}


def test_build_probe_commands_include_explicit_source_dir_selector():
    """命令链应显式携带运行根目录选择。"""

    commands = run_stage2_smoke.build_probe_commands("/dev/ttyUSB0", source_dir="src")

    assert len(commands) == 5
    for command in commands:
        assert command[:4] == ["python3", "-m", "tools.run_stage2_smoke", "mpy-cli"]
        assert "--source-dir" in command
        assert command[command.index("--source-dir") + 1] == "src"


def test_run_probe_uses_explicit_source_dir_commands(monkeypatch):
    """执行 smoke 时应通过命令链显式传入运行根目录。"""

    monkeypatch.setattr(run_stage2_smoke.time, "sleep", lambda _: None)

    commands = []

    def fake_run_command(command):
        commands.append(command)
        if "run" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "STAGE2 status status=ok reason=ok\n"
                    "STAGE2 smoke mode=lite init=0 queries=1 step=0 tick_count=1 snapshots=none\n"
                    "STAGE2 queries count=3 missing=none\n"
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(run_stage2_smoke, "_run_command", fake_run_command)

    result = run_stage2_smoke.run_probe("/dev/ttyUSB0", source_dir="src")

    assert result.status == "ok"
    assert len(commands) == 5
    assert all("--source-dir" in command for command in commands)
    assert all(
        command[command.index("--source-dir") + 1] == "src" for command in commands
    )
