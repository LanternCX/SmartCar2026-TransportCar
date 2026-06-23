"""LSP 契约测试."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_pyright_typecheck_passes() -> None:
    """仓库的 Pyright 检查必须通过."""

    result = subprocess.run(
        ["uv", "run", "--group", "type", "pyright"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        "Pyright 检查失败\n"
        "stdout:\n%s\n"
        "stderr:\n%s"
    ) % (result.stdout, result.stderr)
