"""里程计纵向距离标定脚本约束.

@file tests/unit/script/test_odometry_forward_one_meter_test.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = (
    PROJECT_ROOT / "src" / "script" / "test" / "odometry_forward_one_meter.py"
)


def load_test_script_module():
    """按文件路径加载里程计纵向一米标定脚本."""

    spec = spec_from_file_location("odometry_forward_one_meter_test_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # pyright: ignore[reportAttributeAccessIssue]
    return module


class _Odom:
    """记录测试车体的里程计结果."""

    def __init__(self) -> None:
        self.x = 0.0
        self.y = 1.0


class _FakeCar:
    """记录标定脚本对车体运行时的调用."""

    def __init__(self) -> None:
        self.odometry = _Odom()
        self.command_lock = False
        self.events = []
        self.steps = 0

    def reset_control_state(self) -> None:
        self.events.append(("reset_control_state",))
        self.odometry.x = 0.0
        self.odometry.y = 0.0

    def set_relative_translation_target(
        self,
        dx,
        dy,
        hold_heading_deg=None,
        max_speed_cmd=None,
    ) -> None:
        self.events.append(
            (
                "set_relative_translation_target",
                float(dx),
                float(dy),
                hold_heading_deg,
                max_speed_cmd,
            )
        )
        self.command_lock = True

    def step(self):
        self.events.append(("step",))
        self.steps += 1
        self.odometry.x = 0.1
        if self.steps >= 2:
            self.command_lock = False
        return True

    def stop(self) -> None:
        self.events.append(("stop",))


def test_forward_distance_calibration_runs_x_positive_target_and_stops() -> None:
    """横向标定脚本复位后只下发车体系 x+ 右移目标并在完成后停车."""

    module = load_test_script_module()
    car = _FakeCar()
    logs = []

    result = module.run_forward_one_meter_calibration(
        car,
        sleep_ms=lambda _delay_ms: None,
        now_ms=lambda: 0,
        log_fn=lambda stage, detail="": logs.append((stage, detail)),
    )

    assert result == "done"
    assert car.events[0] == ("reset_control_state",)
    assert car.events[1][0] == "set_relative_translation_target"
    assert car.events[1][1] == pytest.approx(module.TARGET_DISTANCE_M)
    assert car.events[1][2] == pytest.approx(0.0)
    assert car.events[1][3] == pytest.approx(0.0)
    assert car.events[1][4] == pytest.approx(module.TARGET_MAX_SPEED_CMD)
    assert car.events[-1] == ("stop",)
    expected_detail = (
        "result=done target_x=%.3f x=0.100 y=0.000 err_x=%.3f err_y=0.000"
        % (float(module.TARGET_DISTANCE_M), float(module.TARGET_DISTANCE_M) - 0.1)
    )
    assert logs == [
        (
            "odometry_forward_one_meter",
            expected_detail,
        )
    ]
