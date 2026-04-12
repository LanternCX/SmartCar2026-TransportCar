"""启动日志工具测试.

@file tests/unit/test_startup_log.py
"""

from utils.startup_log import startup_log


def test_startup_log_prints_consistent_boot_prefix(capsys) -> None:
    """启动日志工具必须直接打印到标准输出."""

    message = startup_log("remote_control", "ticker started")

    assert message == "[boot] remote_control: ticker started"
    assert capsys.readouterr().out == "[boot] remote_control: ticker started\n"
