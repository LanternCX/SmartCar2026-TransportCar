"""板端测试入口分发约束.

@file tests/unit/script/test_board_test_entry.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = PROJECT_ROOT / "src" / "script" / "test.py"
SRC = PROJECT_ROOT / "src"


def load_board_test_entry_module():
    """按文件路径加载板端测试入口."""

    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    sys.modules.pop("config", None)
    sys.modules.pop("config.startup", None)
    spec = spec_from_file_location("board_test_entry", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # pyright: ignore[reportAttributeAccessIssue]
    return module


def test_test_entry_registers_odometry_one_meter_script() -> None:
    """板端测试入口必须能分发到里程计一米标定脚本."""

    module = load_board_test_entry_module()

    assert module.TEST_MODULES["odometry_one_meter"] == (
        "script.test.odometry_one_meter"
    )


def test_test_entry_registers_odometry_forward_one_meter_script() -> None:
    """板端测试入口必须能分发到里程计纵向一米标定脚本."""

    module = load_board_test_entry_module()

    assert module.TEST_MODULES["odometry_forward_one_meter"] == (
        "script.test.odometry_forward_one_meter"
    )


def test_startup_config_defaults_to_normal_mode() -> None:
    """启动配置默认不进入板端测试入口."""

    module = load_board_test_entry_module()

    assert module.startup_params.STARTUP_TEST_MODE is False
