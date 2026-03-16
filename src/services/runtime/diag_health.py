"""@brief 诊断 facade 的健康与 tick 快照构造器."""

from services.runtime.diag_format import (
    HEALTH_SNAPSHOT_FIELDS,
    TICK_SNAPSHOT_FIELDS,
    format_query_value,
    select_snapshot_fields,
)


def build_health_snapshot(facade):
    """@brief 返回健康摘要快照.

    @param facade DiagnosticsFacade 实例
    @return dict 健康状态字段快照
    """
    runtime = facade._runtime
    return select_snapshot_fields(
        {
            "alive": 1,
            "uptime_ms": max(0, facade._now_ms() - int(runtime.boot_time_ms)),
            "lock": 1 if facade._get_command_lock() else 0,
            "rear": 1 if facade._get_rear_only_mode() else 0,
            "oom_count": int(getattr(runtime, "oom_count", 0) or 0),
            "oom_stage": getattr(runtime, "last_oom_stage", None),
            "last_err": runtime.last_exception_text,
            "vision_state": facade._get_vision_state_name(),
        },
        HEALTH_SNAPSHOT_FIELDS,
    )


def build_health_query_response(facade):
    """@brief 直接构造 health 查询响应.

    @param facade DiagnosticsFacade 实例
    @return str 串口查询响应文本
    """
    runtime = facade._runtime
    return (
        "?health=alive:%d,uptime_ms:%d,lock:%d,rear:%d,oom_count:%d,"
        "oom_stage:%s,last_err:%s,vision_state:%s\r\n"
    ) % (
        1,
        max(0, facade._now_ms() - int(runtime.boot_time_ms)),
        1 if facade._get_command_lock() else 0,
        1 if facade._get_rear_only_mode() else 0,
        int(getattr(runtime, "oom_count", 0) or 0),
        format_query_value(getattr(runtime, "last_oom_stage", None)),
        format_query_value(runtime.last_exception_text),
        format_query_value(facade._get_vision_state_name()),
    )


def build_tick_snapshot(runtime):
    """@brief 返回 tick 统计快照.

    @param runtime 运行时 owner 视图
    @return dict tick 统计字段快照
    """
    avg_us = 0
    if runtime.tick_count > 0:
        avg_us = int(runtime.loop_dt_total_us / runtime.tick_count)
    return select_snapshot_fields(
        {
            "count": int(runtime.tick_count),
            "last_us": int(runtime.last_loop_dt_us),
            "max_us": int(runtime.max_loop_dt_us),
            "avg_us": avg_us,
            "overrun": int(runtime.loop_overrun_count),
        },
        TICK_SNAPSHOT_FIELDS,
    )


def build_tick_query_response(runtime):
    """@brief 直接构造 tick 查询响应.

    @param runtime 运行时 owner 视图
    @return str 串口查询响应文本
    """
    avg_us = 0
    if runtime.tick_count > 0:
        avg_us = int(runtime.loop_dt_total_us / runtime.tick_count)
    return "?tick=count:%d,last_us:%d,max_us:%d,avg_us:%d,overrun:%d\r\n" % (
        int(runtime.tick_count),
        int(runtime.last_loop_dt_us),
        int(runtime.max_loop_dt_us),
        int(avg_us),
        int(runtime.loop_overrun_count),
    )
