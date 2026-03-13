"""Contract tests for motion-related command handlers."""

import pytest

from config.params import V_CMD_MAX
from services.commanding.handlers import (
    cmd_angle,
    cmd_d_angle,
    cmd_dx,
    cmd_dy,
    cmd_omega,
    cmd_print,
    cmd_rear,
    cmd_vx,
    cmd_vy,
    cmd_x,
    cmd_y,
)
from tests.fakes.fake_context import FakeCommandContext


pytestmark = pytest.mark.contract


def test_vx_vy_omega_apply_clamp_and_respect_lock():
    ctx = FakeCommandContext()
    last_cmd = ctx.session.last_cmd
    cmd_vx.handle(ctx, V_CMD_MAX * 2)
    cmd_vy.handle(ctx, -V_CMD_MAX * 2)
    cmd_omega.handle(ctx, 12.5)
    assert last_cmd["vx"] == V_CMD_MAX
    assert last_cmd["vy"] == -V_CMD_MAX
    assert last_cmd["omega"] == 12.5

    ctx.session.command_lock = True
    cmd_vx.handle(ctx, 1.0)
    cmd_vy.handle(ctx, 1.0)
    cmd_omega.handle(ctx, 1.0)
    assert last_cmd["vx"] == V_CMD_MAX
    assert last_cmd["vy"] == -V_CMD_MAX
    assert last_cmd["omega"] == 12.5


def test_x_y_and_angle_commands_update_position_intent():
    ctx = FakeCommandContext()
    ctx.session.last_cmd.update({"vx": 3.0, "vy": -2.0})
    cmd_x.handle(ctx, 1.5)
    cmd_y.handle(ctx, -0.7)
    cmd_angle.handle(ctx, 45.0)
    assert ctx.session.last_cmd["x"] == 1.5
    assert ctx.session.last_cmd["y"] == -0.7
    assert ctx.session.last_cmd["angle"] == 45.0
    assert "vx" not in ctx.session.last_cmd
    assert "vy" not in ctx.session.last_cmd


def test_relative_motion_commands_store_pending_values():
    ctx = FakeCommandContext()
    cmd_dx.handle(ctx, 0.1)
    cmd_dy.handle(ctx, -0.2)
    cmd_d_angle.handle(ctx, 15.0)
    assert ctx.session.pending_dx == 0.1
    assert ctx.session.pending_dy == -0.2
    assert ctx.session.pending_d_angle == 15.0


def test_relative_motion_commands_ignore_when_locked():
    ctx = FakeCommandContext()
    ctx.session.command_lock = True
    cmd_dx.handle(ctx, 1.0)
    cmd_dy.handle(ctx, 2.0)
    cmd_d_angle.handle(ctx, 3.0)
    assert ctx.session.pending_dx is None
    assert ctx.session.pending_dy is None
    assert ctx.session.pending_d_angle is None


def test_rear_mode_toggle_updates_state_and_logs():
    ctx = FakeCommandContext()
    cmd_rear.handle(ctx, 1)
    assert ctx.session.rear_only_mode is True
    assert ctx.session.rear_mode_changed is True
    assert ctx.uart3.messages[-1] == "Rear Only Mode: True\r\n"

    cmd_rear.handle(ctx, 1)
    assert ctx.session.rear_mode_changed is False


def test_print_command_always_writes_uart3():
    ctx = FakeCommandContext()
    ctx.session.command_lock = True
    cmd_print.handle(ctx, "hello")
    assert ctx.uart3.messages == ["hello\r\n"]


def test_relative_command_handlers_write_command_session_only() -> None:
    from services.commanding.handlers import cmd_d_angle as new_cmd_d_angle
    from services.commanding.handlers import cmd_dx as new_cmd_dx
    from services.commanding.handlers import cmd_dy as new_cmd_dy

    ctx = FakeCommandContext()

    new_cmd_dx.handle(ctx, 0.1)
    new_cmd_dy.handle(ctx, -0.2)
    new_cmd_d_angle.handle(ctx, 30.0)

    assert ctx.session.pending_dx == 0.1
    assert ctx.session.pending_dy == -0.2
    assert ctx.session.pending_d_angle == 30.0


def test_fake_context_exposes_explicit_state_owners_instead_of_context_proxies() -> (
    None
):
    ctx = FakeCommandContext()

    for name in (
        "heading_est",
        "heading_target",
        "yaw_pid",
        "yaw_integral",
        "q_est",
        "last_yaw_rad",
        "gyro_lpf",
        "wheel_states",
        "odometry",
    ):
        assert hasattr(type(ctx), name) is False
