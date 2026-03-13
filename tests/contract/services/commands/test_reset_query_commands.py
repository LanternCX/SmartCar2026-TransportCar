"""reset 与 query 命令处理器契约测试."""

import pytest

from services.commanding.handlers import cmd_reset, query_lock, query_pos
from tests.fakes.fake_context import FakeCommandContext


pytestmark = pytest.mark.contract


def test_reset_command_restores_core_runtime_state():
    ctx = FakeCommandContext()
    odometry = ctx.chassis_state.odometry
    yaw_pid = ctx.chassis_state.yaw_pid
    q_est = ctx.chassis_state.q_est
    gyro_lpf = ctx.chassis_state.gyro_lpf
    assert odometry is not None
    assert yaw_pid is not None
    assert q_est is not None
    assert gyro_lpf is not None
    ctx.session.command_lock = True
    ctx.session.rear_only_mode = True
    ctx.session.last_rear_mode = True
    ctx.session.rear_mode_changed = True
    ctx.chassis_state.heading_est = 10.0
    ctx.chassis_state.heading_target = -8.0
    ctx.chassis_state.yaw_integral = 9.0
    ctx.chassis_state.last_yaw_rad = 7.0
    ctx.session.last_cmd = {"vx": 5.0, "vy": -2.0, "omega": 3.0, "x": 1.0}
    ctx.session.pending_dx = 1.0
    ctx.session.pending_dy = 2.0
    ctx.session.pending_d_angle = 3.0

    cmd_reset.handle(ctx, None)

    assert odometry.reset_called is True
    assert ctx.chassis_state.heading_est == 0.0
    assert ctx.chassis_state.heading_target == 0.0
    assert yaw_pid.reset_called is True
    assert ctx.chassis_state.yaw_integral == 0.0
    assert (
        q_est.w,
        q_est.x,
        q_est.y,
        q_est.z,
    ) == (1.0, 0.0, 0.0, 0.0)
    assert ctx.chassis_state.last_yaw_rad == 0.0
    assert gyro_lpf.last_reset_value == 0.0
    assert all(state["duty"] == 0.0 for state in ctx.chassis_state.wheel_states)
    assert all(
        state["controller"].reset_called for state in ctx.chassis_state.wheel_states
    )
    assert ctx.session.last_cmd == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert ctx.session.command_lock is False
    assert ctx.session.rear_only_mode is False
    assert ctx.session.last_rear_mode is False
    assert ctx.session.rear_mode_changed is False
    assert ctx.session.pending_dx is None
    assert ctx.session.pending_dy is None
    assert ctx.session.pending_d_angle is None
    assert ctx.vision_coordinator.clear_runtime_called is True


def test_query_lock_writes_state():
    ctx = FakeCommandContext()
    ctx.session.command_lock = True
    query_lock.handle(ctx)
    assert ctx.uart6.messages == ["?lock=1\r\n"]


def test_query_lock_can_reply_on_uart3() -> None:
    ctx = FakeCommandContext(reply_uart_name="uart3")
    ctx.session.command_lock = True

    query_lock.handle(ctx)

    assert ctx.uart3.messages == ["?lock=1\r\n"]
    assert ctx.uart6.messages == []


def test_query_pos_formats_position_and_heading():
    ctx = FakeCommandContext()
    odometry = ctx.chassis_state.odometry
    assert odometry is not None
    odometry.x = 1.23456
    odometry.y = -2.34567
    ctx.chassis_state.heading_est = 30.1289
    query_pos.handle(ctx)
    assert ctx.uart6.messages == ["?pos=1.235,-2.346,30.13\r\n"]


def test_query_pos_can_reply_on_uart3() -> None:
    ctx = FakeCommandContext(reply_uart_name="uart3")
    odometry = ctx.chassis_state.odometry
    assert odometry is not None
    odometry.x = 1.23456
    odometry.y = -2.34567
    ctx.chassis_state.heading_est = 30.1289

    query_pos.handle(ctx)

    assert ctx.uart3.messages == ["?pos=1.235,-2.346,30.13\r\n"]
    assert ctx.uart6.messages == []


def test_query_handlers_can_reply_without_transport_private_query_state() -> None:
    from services.commanding.handlers import query_lock as new_query_lock
    from services.commanding.handlers import query_pos as new_query_pos

    ctx = FakeCommandContext(reply_uart_name="uart3")
    ctx.session.command_lock = True
    odometry = ctx.chassis_state.odometry
    assert odometry is not None
    odometry.x = 1.23456
    odometry.y = -2.34567
    ctx.chassis_state.heading_est = 30.1289

    new_query_lock.handle(ctx)
    new_query_pos.handle(ctx)

    assert ctx.uart3.messages == ["?lock=1\r\n", "?pos=1.235,-2.346,30.13\r\n"]
    assert ctx.uart6.messages == []


def test_fake_context_no_longer_exposes_context_snapshot_wrappers() -> None:
    ctx = FakeCommandContext()

    assert hasattr(ctx, "build_health_snapshot") is False
    assert hasattr(ctx, "build_tick_snapshot") is False
    assert hasattr(ctx, "build_imu_snapshot") is False
    assert hasattr(ctx, "build_encoder_snapshot") is False
    assert hasattr(ctx, "build_motor_snapshot") is False
    assert hasattr(ctx, "build_vision_snapshot") is False
