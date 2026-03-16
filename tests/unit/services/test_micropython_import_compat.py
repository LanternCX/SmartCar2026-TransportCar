"""验证关键运行时模块在缺少 typing 时仍可导入."""

import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def test_runtime_modules_import_without_typing_module() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    src_path = str(repo_root / "src")
    host_os = __import__("os")
    script = """
import builtins
import sys

real_import = builtins.__import__

def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == 'typing' or name.startswith('typing.'):
        raise ImportError("no module named 'typing'")
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = blocked_import

modules = [
    'services.commanding.router',
    'diagnostics.manager',
    'diagnostics.sink',
    'services.commanding.handlers.cmd_log_profile',
    'services.commanding.handlers.cmd_log_level',
    'services.commanding.handlers.cmd_log_filter',
    'services.commanding.handlers.cmd_log_modules',
    'services.commanding.handlers.cmd_log_color',
    'services.commanding.handlers.cmd_log_reset',
    'services.commanding.handlers.query_log',
]

for module_name in modules:
    __import__(module_name)
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        env={**dict(host_os.environ), "PYTHONPATH": src_path},
    )

    assert result.returncode == 0, result.stderr or result.stdout
