"""Contract tests for reset and query command handlers."""

import pytest

from services.commands import cmd_reset, query_lock, query_pos
from tests.fakes.fake_context import FakeCommandContext


pytestmark = pytest.mark.contract


def test_reset_command_restores_core_runtime_state():
    ctx = FakeCommandContext()
    ctx.command_lock = True
    ctx.heading_est = 10.0
    ctx.heading_target = -8.0
    ctx.yaw_integral = 9.0
    ctx.last_yaw_rad = 7.0
    ctx.last_cmd = {"vx": 5.0, "vy": -2.0, "omega": 3.0, "x": 1.0}
    ctx._pending_dx = 1.0
    ctx._pending_dy = 2.0
    ctx._pending_d_angle = 3.0

    cmd_reset.handle(ctx, None)

    assert ctx.odometry.reset_called is True
    assert ctx.heading_est == 0.0
    assert ctx.heading_target == 0.0
    assert ctx.yaw_pid.reset_called is True
    assert ctx.yaw_integral == 0.0
    assert (ctx.q_est.w, ctx.q_est.x, ctx.q_est.y, ctx.q_est.z) == (1.0, 0.0, 0.0, 0.0)
    assert ctx.last_yaw_rad == 0.0
    assert ctx.gyro_lpf.last_reset_value == 0.0
    assert all(state["duty"] == 0.0 for state in ctx.wheel_states)
    assert all(state["controller"].reset_called for state in ctx.wheel_states)
    assert ctx.last_cmd == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert ctx.command_lock is False
    assert ctx._pending_dx is None
    assert ctx._pending_dy is None
    assert ctx._pending_d_angle is None


def test_query_lock_writes_state():
    ctx = FakeCommandContext()
    ctx.command_lock = True
    query_lock.handle(ctx)
    assert ctx.uart6.messages == ["?lock=1\r\n"]


def test_query_pos_formats_position_and_heading():
    ctx = FakeCommandContext()
    ctx.odometry.x = 1.23456
    ctx.odometry.y = -2.34567
    ctx.heading_est = 30.1289
    query_pos.handle(ctx)
    assert ctx.uart6.messages == ["?pos=1.235,-2.346,30.13\r\n"]
