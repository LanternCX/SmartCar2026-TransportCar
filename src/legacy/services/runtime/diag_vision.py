"""@brief 诊断 facade 的视觉快照构造器."""

from services.runtime.diag_format import (
    VISION_SNAPSHOT_FIELDS,
    format_query_value,
    select_snapshot_fields,
)


def _empty_vision_snapshot(state_name: str):
    """@brief 构造默认视觉快照骨架.

    @param state_name 当前视觉状态名
    @return dict 含固定字段的空快照
    """
    return {
        "state": state_name,
        "obs_age_ms": None,
        "obs_left": None,
        "obs_top": None,
        "obs_right": None,
        "obs_bottom": None,
        "obs_center_x": None,
        "obs_center_y": None,
        "target_x": None,
        "target_y": None,
        "target_angle": None,
    }


def _resolve_owner_vision_snapshot(facade):
    """@brief 从 owner 当前状态构造视觉快照.

    @param facade DiagnosticsFacade 实例
    @return dict 视觉查询字段快照
    """
    snapshot = _empty_vision_snapshot(facade._get_vision_state_name())
    vision_runtime = facade._get_vision_runtime()
    if vision_runtime is None:
        coordinator = getattr(facade._runtime, "vision_coordinator", None)
        if coordinator is None:
            return snapshot
        return select_snapshot_fields(
            coordinator.build_snapshot(facade._now_ms()),
            VISION_SNAPSHOT_FIELDS,
        )

    observation = getattr(vision_runtime, "selected_input", None)
    if observation is not None:
        observation = getattr(observation, "observation", None)
    if observation is None:
        observation = getattr(vision_runtime, "latest_observation", None)
    if observation is not None:
        snapshot["obs_age_ms"] = int(facade._now_ms()) - int(observation.timestamp_ms)
        snapshot["obs_left"] = float(observation.left)
        snapshot["obs_top"] = float(observation.top)
        snapshot["obs_right"] = float(observation.right)
        snapshot["obs_bottom"] = float(observation.bottom)
        snapshot["obs_center_x"] = float(observation.center_x)
        snapshot["obs_center_y"] = float(observation.center_y)

    resolved_target = getattr(vision_runtime, "resolved_target", None)
    if resolved_target is not None:
        snapshot["target_x"] = float(resolved_target.x)
        snapshot["target_y"] = float(resolved_target.y)
        snapshot["target_angle"] = float(resolved_target.angle_deg)
    return snapshot


def build_vision_snapshot(facade):
    """@brief 返回视觉摘要快照.

    @param facade DiagnosticsFacade 实例
    @return dict 视觉查询字段快照
    """
    return select_snapshot_fields(
        _resolve_owner_vision_snapshot(facade),
        VISION_SNAPSHOT_FIELDS,
    )


def build_vision_query_response(facade):
    """@brief 直接构造 vision 查询响应.

    @param facade DiagnosticsFacade 实例
    @return str 串口查询响应文本
    """
    snapshot = _resolve_owner_vision_snapshot(facade)
    return (
        "?vision=state:%s,obs_age_ms:%s,obs_left:%s,obs_top:%s,obs_right:%s,"
        "obs_bottom:%s,obs_center_x:%s,obs_center_y:%s,target_x:%s,target_y:%s,"
        "target_angle:%s\r\n"
    ) % (
        format_query_value(snapshot.get("state")),
        format_query_value(snapshot.get("obs_age_ms")),
        format_query_value(snapshot.get("obs_left")),
        format_query_value(snapshot.get("obs_top")),
        format_query_value(snapshot.get("obs_right")),
        format_query_value(snapshot.get("obs_bottom")),
        format_query_value(snapshot.get("obs_center_x")),
        format_query_value(snapshot.get("obs_center_y")),
        format_query_value(snapshot.get("target_x")),
        format_query_value(snapshot.get("target_y")),
        format_query_value(snapshot.get("target_angle")),
    )
