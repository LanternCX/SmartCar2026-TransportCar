"""@brief 视觉协议批次缓存与提交辅助函数."""


def clear_pending_frame(protocol) -> None:
    """@brief 清空尚未结束的检测批次缓存."""
    camera_id = protocol._pending_camera_id
    if camera_id is not None:
        slot = protocol._slot_for_camera(camera_id)
        slot.pending_items = None
        slot.pending_frame_id = None
    protocol._pending_camera_id = None
    protocol._pending_frame_id = None


def set_invalid_batch(
    protocol,
    pending_camera_id: str,
    pending_frame_id: str,
    jumped_camera_id: str,
    jumped_frame_id: str,
) -> None:
    """@brief 标记因批次跳变而整体失效的旧批次与跳变批次."""
    clear_pending_frame(protocol)
    protocol._invalid_pending_camera_id = str(pending_camera_id)
    protocol._invalid_pending_frame_id = str(pending_frame_id)
    protocol._invalid_jumped_camera_id = str(jumped_camera_id)
    protocol._invalid_jumped_frame_id = str(jumped_frame_id)


def clear_invalid_batch(protocol) -> None:
    """@brief 清空失效批次标记."""
    protocol._invalid_pending_camera_id = None
    protocol._invalid_pending_frame_id = None
    protocol._invalid_jumped_camera_id = None
    protocol._invalid_jumped_frame_id = None


def has_invalid_batch(protocol) -> bool:
    """@brief 判断当前是否处于批次失效窗口."""
    return protocol._invalid_pending_camera_id is not None


def is_invalid_batch(protocol, camera_id: str, frame_id: str) -> bool:
    """@brief 判断当前帧标识是否处于失效批次."""
    normalized_camera_id = str(camera_id)
    normalized_frame_id = str(frame_id)
    return (
        protocol._invalid_pending_camera_id == normalized_camera_id
        and protocol._invalid_pending_frame_id == normalized_frame_id
    ) or (
        protocol._invalid_jumped_camera_id == normalized_camera_id
        and protocol._invalid_jumped_frame_id == normalized_frame_id
    )


def commit_frame(protocol, camera_id: str, frame_id: str, detections, now_ms: int):
    """@brief 提交一帧检测集合并更新兼容观测入口."""
    frame = protocol._frame_type(
        camera_id=camera_id,
        frame_id=frame_id,
        detections=detections,
        timestamp_ms=now_ms,
    )
    slot = protocol._slot_for_camera(camera_id)
    slot.frame = frame
    slot.timestamp_ms = int(now_ms)
    protocol.runtime.latest_frame = frame
    protocol.runtime.latest_observation = (
        frame.detections[-1] if frame.detections else None
    )
    return frame


def commit_pending_frame(protocol, now_ms: int):
    """@brief 在收到显式结束标记后提交当前批次."""
    camera_id = protocol._pending_camera_id
    frame_id = protocol._pending_frame_id
    if camera_id is None or frame_id is None:
        clear_pending_frame(protocol)
        return None
    detections = protocol._get_pending_detections()
    frame = commit_frame(
        protocol,
        camera_id=camera_id,
        frame_id=frame_id,
        detections=[] if detections is None else detections,
        now_ms=now_ms,
    )
    clear_pending_frame(protocol)
    return frame


def clear_runtime(protocol) -> None:
    """@brief 清空当前缓存的视觉观测."""
    protocol.runtime.latest_observation = None
    protocol.runtime.latest_frame = None
    protocol.runtime.cam_a.frame = None
    protocol.runtime.cam_a.pending_items = None
    protocol.runtime.cam_a.pending_frame_id = None
    protocol.runtime.cam_a.timestamp_ms = None
    protocol.runtime.cam_b.frame = None
    protocol.runtime.cam_b.pending_items = None
    protocol.runtime.cam_b.pending_frame_id = None
    protocol.runtime.cam_b.timestamp_ms = None
    clear_pending_frame(protocol)
    clear_invalid_batch(protocol)
