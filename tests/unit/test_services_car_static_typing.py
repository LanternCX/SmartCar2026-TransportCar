"""services.car 静态类型门禁测试."""

from pathlib import Path
import subprocess

import pytest


pytestmark = pytest.mark.unit


def test_services_car_pyright_clean() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    command = [
        "python3",
        "-m",
        "pyright",
        "src/services/car",
        "src/services/stage2_smoke/full.py",
        "src/script/remote_control.py",
        "tools/stage2_full_trace_probe.py",
        "tools/device_observe_probe.py",
    ]

    result = subprocess.run(
        command,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
