"""可选 lock 命令语义测试."""

import sys
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

import services.commands as _commands  # noqa: F401 触发命令注册

from services.command_policy import build_command_health_fields, finalize_command_route
from services.command_router import router


class _CaptureUart:
    def __init__(self) -> None:
        self.messages = []

    def write(self, text) -> None:
        self.messages.append(text)


class _Odom:
    def __init__(self, x=1.0, y=2.0) -> None:
        self.x = float(x)
        self.y = float(y)

    def reset(self) -> None:
        self.x = 0.0
        self.y = 0.0


class _Resettable:
    def __init__(self) -> None:
        self.reset_count = 0

    def reset(self, *_args) -> None:
        self.reset_count += 1


class _Quat:
    def __init__(self) -> None:
        self.w = 0.5
        self.x = 1.0
        self.y = 2.0
        self.z = 3.0


class _RouteContext:
    def __init__(self) -> None:
        self.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self.command_lock = False
        self.command_mode = "none"
        self.lock_start_time = 0
        self.rear_only_mode = False
        self.last_rear_mode = False
        self._rear_mode_changed = False
        self._pending_dx: Optional[float] = None
        self._pending_dy: Optional[float] = None
        self._pending_d_angle: Optional[float] = None
        self._pending_lock: Optional[bool] = None
        self.heading_est = 0.0
        self.heading_target = 0.0
        self.odometry = _Odom()
        self.uart3 = _CaptureUart()
        self.yaw_pid = _Resettable()
        self.gyro_lpf = _Resettable()
        self.q_est = _Quat()
        self.last_yaw_rad = 9.0
        self.yaw_integral = 7.0
        self.wheel_states = []

    def _get_active_rear_only_mode(self):
        return self.rear_only_mode

    def _finalize_route(self, dispatched) -> None:
        finalize_command_route(self, dispatched, now_ms=4321)


def test_lock_zero_keeps_relative_command_unlocked() -> None:
    ctx = _RouteContext()

    assert router.route("dx=0.10,dy=-0.20,lock=0", ctx) is True

    assert ctx.command_lock is False
    assert ctx.command_mode == "unlocked"
    assert ctx.last_cmd["x"] == 1.10
    assert ctx.last_cmd["y"] == 1.80


def test_lock_one_sets_locked_mode_and_resets_lock_timer() -> None:
    ctx = _RouteContext()

    assert router.route("dx=0.10,lock=1", ctx) is True

    assert ctx.command_lock is True
    assert ctx.command_mode == "locked"
    assert ctx.lock_start_time == 4321


def test_new_unlocked_packet_preempts_previous_locked_target() -> None:
    ctx = _RouteContext()

    assert router.route("dx=0.10,lock=1", ctx) is True
    assert router.route("dx=-0.05,dy=0.04,lock=0", ctx) is True

    assert ctx.command_lock is False
    assert ctx.command_mode == "unlocked"
    assert ctx.last_cmd["x"] == 0.95
    assert ctx.last_cmd["y"] == 2.04


def test_rear_and_relative_move_share_same_lock_zero_packet() -> None:
    ctx = _RouteContext()

    assert router.route("rear=1,dx=0.02,dy=0.03,lock=0", ctx) is True

    assert ctx.rear_only_mode is True
    assert ctx.command_mode == "unlocked"
    assert ctx.last_cmd["x"] == 1.02
    assert ctx.last_cmd["y"] == 2.03


def test_velocity_packet_clears_position_targets_and_exits_command_mode() -> None:
    ctx = _RouteContext()

    assert router.route("dx=0.10,dy=0.10,lock=0", ctx) is True
    assert router.route("vy=12", ctx) is True

    assert "x" not in ctx.last_cmd
    assert "y" not in ctx.last_cmd
    assert ctx.last_cmd["vy"] == 12.0
    assert ctx.command_mode == "none"


def test_health_fields_include_command_mode() -> None:
    ctx = _RouteContext()
    ctx.command_lock = False
    ctx.command_mode = "unlocked"
    ctx.rear_only_mode = True

    assert build_command_health_fields(ctx) == {
        "lock": 0,
        "rear": 1,
        "command_mode": "unlocked",
    }


def test_angle_packet_clears_omega_target() -> None:
    ctx = _RouteContext()
    ctx.last_cmd["omega"] = 15.0

    assert router.route("angle=90", ctx) is True

    assert ctx.last_cmd["angle"] == 90.0
    assert "omega" not in ctx.last_cmd
    assert ctx.command_mode == "locked"


def test_omega_packet_clears_angle_target_and_exits_command_mode() -> None:
    ctx = _RouteContext()

    assert router.route("angle=45,lock=1", ctx) is True
    assert router.route("omega=12", ctx) is True

    assert "angle" not in ctx.last_cmd
    assert ctx.last_cmd["omega"] == 12.0
    assert ctx.command_mode == "none"
    assert ctx.command_lock is False


def test_velocity_packet_clears_angle_target_and_exits_command_mode() -> None:
    ctx = _RouteContext()

    assert router.route("angle=45,lock=1", ctx) is True
    assert router.route("vx=12", ctx) is True

    assert "angle" not in ctx.last_cmd
    assert ctx.last_cmd["vx"] == 12.0
    assert ctx.command_mode == "none"
    assert ctx.command_lock is False


def test_reset_clears_command_mode_and_pending_lock() -> None:
    ctx = _RouteContext()

    assert router.route("dx=0.10,lock=1", ctx) is True
    ctx._pending_lock = True
    ctx.command_mode = "locked"

    assert router.route("reset", ctx) is True

    assert ctx.command_mode == "none"
    assert ctx._pending_lock is None
    assert ctx.command_lock is False
