"""诊断查询处理器 contract 测试."""

from typing import Any, cast

import pytest

from services.commanding.handlers import (
    query_enc,
    query_health,
    query_imu,
    query_motor,
    query_tick,
    query_vision,
)
from services.diagnostics import format_query_response
from tests.fakes.fake_context import FakeCommandContext


pytestmark = pytest.mark.contract


class _FacadeOnlyDiagnostics:
    """仅通过 facade 提供诊断数据的测试假对象."""

    def __init__(self, snapshots):
        self._snapshots = snapshots

    def build_health_snapshot(self):
        return self._snapshots["health"]

    def build_tick_snapshot(self):
        return self._snapshots["tick"]

    def build_imu_snapshot(self):
        return self._snapshots["imu"]

    def build_encoder_snapshot(self):
        return self._snapshots["enc"]

    def build_motor_snapshot(self):
        return self._snapshots["motor"]

    def build_vision_snapshot(self):
        return self._snapshots["vision"]


class _DirectResponseDiagnostics:
    """仅提供直出响应的诊断 facade 假对象."""

    def build_health_query_response(self):
        return "?health=alive:1,uptime_ms:1,lock:0,rear:0,oom_count:0,oom_stage:none,last_err:none,vision_state:IDLE\r\n"

    def build_tick_query_response(self):
        return "?tick=count:1,last_us:2,max_us:3,avg_us:4,overrun:0\r\n"

    def build_vision_query_response(self):
        return "?vision=state:IDLE,obs_age_ms:none,obs_left:none,obs_top:none,obs_right:none,obs_bottom:none,obs_center_x:none,obs_center_y:none,target_x:none,target_y:none,target_angle:none\r\n"

    def build_health_snapshot(self):
        raise AssertionError("health snapshot path should not run")

    def build_tick_snapshot(self):
        raise AssertionError("tick snapshot path should not run")

    def build_vision_snapshot(self):
        raise AssertionError("vision snapshot path should not run")


def test_query_health_formats_runtime_health() -> None:
    ctx = FakeCommandContext()
    cast(Any, ctx).get_diagnostics_facade = lambda: _FacadeOnlyDiagnostics(
        {
            "health": {
                "alive": 1,
                "uptime_ms": 1500,
                "lock": 1,
                "rear": 1,
                "oom_count": 3,
                "oom_stage": "format",
                "last_err": "none",
                "vision_state": "ALIGN_DX",
            }
        }
    )

    query_health.handle(ctx)

    assert ctx.uart6.messages == [
        "?health=alive:1,uptime_ms:1500,lock:1,rear:1,oom_count:3,oom_stage:format,last_err:none,vision_state:ALIGN_DX\r\n"
    ]


def test_query_health_can_reply_on_uart3() -> None:
    ctx = FakeCommandContext(reply_uart_name="uart3")
    cast(Any, ctx).get_diagnostics_facade = lambda: _FacadeOnlyDiagnostics(
        {
            "health": {
                "alive": 1,
                "uptime_ms": 1500,
                "lock": 0,
                "rear": 0,
                "oom_count": 0,
                "oom_stage": "none",
                "last_err": "none",
                "vision_state": "IDLE",
            }
        }
    )

    query_health.handle(ctx)

    assert ctx.uart3.messages == [
        "?health=alive:1,uptime_ms:1500,lock:0,rear:0,oom_count:0,oom_stage:none,last_err:none,vision_state:IDLE\r\n"
    ]
    assert ctx.uart6.messages == []


def test_query_health_tick_and_vision_prefer_direct_facade_response_path() -> None:
    facade = _DirectResponseDiagnostics()

    ctx_health = FakeCommandContext()
    cast(Any, ctx_health).get_diagnostics_facade = lambda: facade
    query_health.handle(ctx_health)

    ctx_tick = FakeCommandContext()
    cast(Any, ctx_tick).get_diagnostics_facade = lambda: facade
    query_tick.handle(ctx_tick)

    ctx_vision = FakeCommandContext()
    cast(Any, ctx_vision).get_diagnostics_facade = lambda: facade
    query_vision.handle(ctx_vision)

    assert ctx_health.uart6.messages == [facade.build_health_query_response()]
    assert ctx_tick.uart6.messages == [facade.build_tick_query_response()]
    assert ctx_vision.uart6.messages == [facade.build_vision_query_response()]


def test_query_tick_formats_runtime_statistics() -> None:
    ctx = FakeCommandContext()
    cast(Any, ctx).get_diagnostics_facade = lambda: _FacadeOnlyDiagnostics(
        {
            "tick": {
                "count": 12,
                "last_us": 5010,
                "max_us": 6400,
                "avg_us": 5050,
                "overrun": 1,
            }
        }
    )

    query_tick.handle(ctx)

    assert ctx.uart6.messages == [
        "?tick=count:12,last_us:5010,max_us:6400,avg_us:5050,overrun:1\r\n"
    ]


def test_query_health_tick_and_vision_keep_minimal_surface_field_order() -> None:
    health_snapshot = {
        "vision_state": "ALIGN_DX",
        "last_err": "none",
        "oom_stage": "format",
        "oom_count": 3,
        "rear": 1,
        "lock": 1,
        "uptime_ms": 1500,
        "alive": 1,
        "debug": "drop-me",
    }
    tick_snapshot = {
        "overrun": 1,
        "avg_us": 5050,
        "max_us": 6400,
        "last_us": 5010,
        "count": 12,
        "debug": 99,
    }
    vision_snapshot = {
        "target_angle": 15.0,
        "target_y": 0.4,
        "target_x": 0.2,
        "obs_center_y": 55.0,
        "obs_center_x": 120.0,
        "obs_bottom": 90.0,
        "obs_right": 140.0,
        "obs_top": 20.0,
        "obs_left": 100.0,
        "obs_age_ms": 80,
        "state": "ALIGN_DX",
        "debug": "drop-me",
    }

    assert format_query_response("health", health_snapshot) == (
        "?health=alive:1,uptime_ms:1500,lock:1,rear:1,oom_count:3,"
        "oom_stage:format,last_err:none,vision_state:ALIGN_DX\r\n"
    )
    assert format_query_response("tick", tick_snapshot) == (
        "?tick=count:12,last_us:5010,max_us:6400,avg_us:5050,overrun:1\r\n"
    )
    assert format_query_response("vision", vision_snapshot) == (
        "?vision=state:ALIGN_DX,obs_age_ms:80,obs_left:100.0,obs_top:20.0,"
        "obs_right:140.0,obs_bottom:90.0,obs_center_x:120.0,obs_center_y:55.0,"
        "target_x:0.2,target_y:0.4,target_angle:15.0\r\n"
    )


def test_query_imu_formats_attitude_snapshot() -> None:
    ctx = FakeCommandContext()
    cast(Any, ctx).get_diagnostics_facade = lambda: _FacadeOnlyDiagnostics(
        {
            "imu": {
                "ok": 1,
                "yaw_deg": 33.3,
                "yaw_rate_dps": 12.5,
                "gz_raw": 345.0,
            }
        }
    )

    query_imu.handle(ctx)

    assert ctx.uart6.messages == [
        "?imu=ok:1,yaw_deg:33.3,yaw_rate_dps:12.5,gz_raw:345.0\r\n"
    ]


def test_query_enc_formats_encoder_snapshot() -> None:
    ctx = FakeCommandContext()
    cast(Any, ctx).get_diagnostics_facade = lambda: _FacadeOnlyDiagnostics(
        {
            "enc": {
                "m_raw": 11.0,
                "m_filt": 9.5,
                "l_raw": 12.0,
                "l_filt": 10.5,
                "r_raw": 13.0,
                "r_filt": 11.5,
            }
        }
    )

    query_enc.handle(ctx)

    assert ctx.uart6.messages == [
        "?enc=m_raw:11.0,m_filt:9.5,l_raw:12.0,l_filt:10.5,r_raw:13.0,r_filt:11.5\r\n"
    ]


def test_query_motor_formats_target_and_duty_snapshot() -> None:
    ctx = FakeCommandContext()
    cast(Any, ctx).get_diagnostics_facade = lambda: _FacadeOnlyDiagnostics(
        {
            "motor": {
                "m_target": 15.0,
                "m_duty": 1200.0,
                "l_target": 16.0,
                "l_duty": 1300.0,
                "r_target": 17.0,
                "r_duty": 1400.0,
                "rear": 1,
            }
        }
    )

    query_motor.handle(ctx)

    assert ctx.uart6.messages == [
        "?motor=m_target:15.0,m_duty:1200.0,l_target:16.0,l_duty:1300.0,r_target:17.0,r_duty:1400.0,rear:1\r\n"
    ]


def test_query_vision_formats_target_and_observation() -> None:
    ctx = FakeCommandContext()
    cast(Any, ctx).get_diagnostics_facade = lambda: _FacadeOnlyDiagnostics(
        {
            "vision": {
                "state": "ALIGN_DX",
                "obs_age_ms": 80,
                "obs_left": 100.0,
                "obs_top": 20.0,
                "obs_right": 140.0,
                "obs_bottom": 90.0,
                "obs_center_x": 120.0,
                "obs_center_y": 55.0,
                "target_x": 0.2,
                "target_y": 0.4,
                "target_angle": 15.0,
            }
        }
    )

    query_vision.handle(ctx)

    assert ctx.uart6.messages == [
        "?vision=state:ALIGN_DX,obs_age_ms:80,obs_left:100.0,obs_top:20.0,obs_right:140.0,obs_bottom:90.0,obs_center_x:120.0,obs_center_y:55.0,target_x:0.2,target_y:0.4,target_angle:15.0\r\n"
    ]


@pytest.mark.parametrize(
    ("handler", "token", "snapshot"),
    (
        (
            query_health,
            "health",
            {
                "alive": 1,
                "uptime_ms": 1500,
                "lock": 1,
                "rear": 1,
                "last_err": "none",
                "vision_state": "ALIGN_DX",
            },
        ),
        (
            query_tick,
            "tick",
            {
                "count": 12,
                "last_us": 5010,
                "max_us": 6400,
                "avg_us": 5050,
                "overrun": 1,
            },
        ),
        (
            query_imu,
            "imu",
            {
                "ok": 1,
                "yaw_deg": 33.3,
                "yaw_rate_dps": 12.5,
                "gz_raw": 345.0,
            },
        ),
        (
            query_enc,
            "enc",
            {
                "m_raw": 11.0,
                "m_filt": 9.5,
                "l_raw": 12.0,
                "l_filt": 10.5,
                "r_raw": 13.0,
                "r_filt": 11.5,
            },
        ),
        (
            query_motor,
            "motor",
            {
                "m_target": 15.0,
                "m_duty": 1200.0,
                "l_target": 16.0,
                "l_duty": 1300.0,
                "r_target": 17.0,
                "r_duty": 1400.0,
                "rear": 1,
            },
        ),
        (
            query_vision,
            "vision",
            {
                "state": "ALIGN_DX",
                "obs_age_ms": 80,
                "obs_left": 100.0,
                "obs_top": 20.0,
                "obs_right": 140.0,
                "obs_bottom": 90.0,
                "obs_center_x": 120.0,
                "obs_center_y": 55.0,
                "target_x": 0.2,
                "target_y": 0.4,
                "target_angle": 15.0,
            },
        ),
    ),
)
def test_diag_query_handlers_only_use_diagnostics_facade_data(
    handler, token, snapshot
) -> None:
    ctx = FakeCommandContext()
    local_ctx = cast(Any, ctx)

    def _unexpected_snapshot_call():
        raise AssertionError("query handler should use diagnostics facade only")

    local_ctx.build_health_snapshot = _unexpected_snapshot_call
    local_ctx.build_tick_snapshot = _unexpected_snapshot_call
    local_ctx.build_imu_snapshot = _unexpected_snapshot_call
    local_ctx.build_encoder_snapshot = _unexpected_snapshot_call
    local_ctx.build_motor_snapshot = _unexpected_snapshot_call
    local_ctx.build_vision_snapshot = _unexpected_snapshot_call
    local_ctx.get_diagnostics_facade = lambda: _FacadeOnlyDiagnostics({token: snapshot})

    handler.handle(ctx)

    assert ctx.uart6.messages == [format_query_response(token, snapshot)]
