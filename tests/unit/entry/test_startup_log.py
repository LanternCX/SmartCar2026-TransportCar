"""日志工具测试.

@file tests/unit/entry/test_startup_log.py
"""

from utils import startup_log


def test_log_prints_consistent_text(capsys) -> None:
    """日志工具必须直接打印到标准输出."""

    startup_log.cnt = 0

    message = startup_log.log("remote_control", "ticker started")
    output = capsys.readouterr().out

    assert message == "0 remote_control: ticker started"
    assert output.endswith("\n")
    assert message in output
    assert startup_log.cnt == 1
