"""源码重构后的目录布局约束测试."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_dirs_moved_under_src() -> None:
    """业务目录应全部迁移到 src 下."""
    for name in (
        "config",
        "control",
        "filters",
        "hardware",
        "services",
        "storage",
        "utils",
    ):
        assert (ROOT / "src" / name).is_dir()
        assert not (ROOT / name).exists()


def test_root_scripts_archived_under_src() -> None:
    """根目录脚本应归档到 src/script，boot 特例在 src 根下."""
    assert (ROOT / "src" / "boot.py").is_file()
    assert not (ROOT / "boot.py").exists()

    for name in (
        "calibrate_gyro.py",
        "pid_identify.py",
        "remote_control.py",
        "test.py",
        "yaw_sender.py",
    ):
        assert (ROOT / "src" / "script" / name).is_file()
        assert not (ROOT / name).exists()
