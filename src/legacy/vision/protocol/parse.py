"""@brief 视觉协议 payload 解析辅助函数."""

from vision.protocol.batch import (
    clear_invalid_batch,
    clear_pending_frame,
    commit_frame,
    commit_pending_frame,
    has_invalid_batch,
    is_invalid_batch,
    set_invalid_batch,
)


def parse_line_items(line: str):
    """@brief 将单行协议文本解析为键值对列表."""
    parts = [part.strip() for part in str(line).split(",") if part.strip()]
    if not parts:
        return None
    parsed_items = []
    for part in parts:
        if "=" not in part:
            return []
        key, value_text = part.split("=", 1)
        parsed_items.append((key.strip().lower(), value_text.strip()))
    return parsed_items


def is_reserved_payload(protocol_cls, line: str) -> bool:
    """@brief 判断一行报文是否属于视觉协议保留载荷."""
    parsed_items = parse_line_items(line)
    if parsed_items is None:
        return False
    saw_visual_key = False
    for key, _value_text in parsed_items:
        if not key:
            return saw_visual_key
        if key in protocol_cls._VISUAL_KEYS:
            saw_visual_key = True
    return saw_visual_key


def try_parse_observation(protocol, line: str, source: str, now_ms: int):
    """@brief 尝试从指定来源解析一帧视觉观测."""
    if source != "uart6":
        return protocol._parse_result_type(False, None)
    if not is_reserved_payload(type(protocol), line):
        return protocol._parse_result_type(False, None)
    parsed_items = parse_line_items(line)
    if parsed_items is None:
        return protocol._parse_result_type(False, None)
    if parsed_items == []:
        return protocol._parse_result_type(True, None)
    keys = {}
    for key, value_text in parsed_items:
        if key in keys:
            return protocol._parse_result_type(True, None)
        keys[key] = value_text
    if "frame_end" in keys:
        camera_id = keys.get("camera_id")
        frame_id = keys.get("frame_id")
        if camera_id is None or frame_id is None:
            clear_pending_frame(protocol)
            return protocol._parse_result_type(True, None)
        if has_invalid_batch(protocol):
            if is_invalid_batch(protocol, camera_id, frame_id):
                return protocol._parse_result_type(True, None)
            clear_invalid_batch(protocol)
        if protocol._pending_camera_id != str(
            camera_id
        ) or protocol._pending_frame_id != str(frame_id):
            if protocol._pending_camera_id is not None:
                clear_pending_frame(protocol)
                return protocol._parse_result_type(True, None)
            clear_invalid_batch(protocol)
            commit_frame(protocol, str(camera_id), str(frame_id), [], now_ms)
            return protocol._parse_result_type(True, None)
        commit_pending_frame(protocol, now_ms)
        return protocol._parse_result_type(True, protocol.runtime.latest_observation)

    is_multi_detection = all(
        key in keys for key in ("camera_id", "frame_id", "category")
    )
    if is_multi_detection:
        required_keys = (
            "camera_id",
            "frame_id",
            "category",
            "left",
            "top",
            "right",
            "bottom",
        )
        if tuple(sorted(keys.keys())) != tuple(sorted(required_keys)):
            return protocol._parse_result_type(True, None)
        try:
            observation = protocol._observation_type(
                left=float(keys["left"]),
                top=float(keys["top"]),
                right=float(keys["right"]),
                bottom=float(keys["bottom"]),
                timestamp_ms=now_ms,
                camera_id=keys["camera_id"],
                frame_id=keys["frame_id"],
                category=keys["category"],
            )
        except ValueError:
            return protocol._parse_result_type(True, None)
        if (
            observation.right <= observation.left
            or observation.bottom <= observation.top
        ):
            return protocol._parse_result_type(True, None)
        camera_id = str(keys["camera_id"])
        frame_id = str(keys["frame_id"])
        if has_invalid_batch(protocol):
            if is_invalid_batch(protocol, camera_id, frame_id):
                return protocol._parse_result_type(True, None)
            clear_invalid_batch(protocol)
        if protocol._pending_camera_id is not None and (
            protocol._pending_camera_id != camera_id
            or protocol._pending_frame_id != frame_id
        ):
            set_invalid_batch(
                protocol,
                pending_camera_id=protocol._pending_camera_id,
                pending_frame_id=protocol._pending_frame_id,
                jumped_camera_id=camera_id,
                jumped_frame_id=frame_id,
            )
            return protocol._parse_result_type(True, None)
        if protocol._pending_camera_id is None:
            protocol._pending_camera_id = camera_id
            protocol._pending_frame_id = frame_id
            slot = protocol._slot_for_camera(camera_id)
            slot.pending_frame_id = frame_id
            slot.pending_items = []
        protocol._ensure_pending_detections().append(observation)
        return protocol._parse_result_type(True, observation)

    if len(parsed_items) != 4:
        return protocol._parse_result_type(True, None)
    values = {}
    for key, value_text in parsed_items:
        if key not in protocol._BBOX_KEYS or key in values:
            return protocol._parse_result_type(True, None)
        try:
            values[key] = float(value_text)
        except ValueError:
            return protocol._parse_result_type(True, None)
    if values["right"] <= values["left"] or values["bottom"] <= values["top"]:
        return protocol._parse_result_type(True, None)
    observation = protocol._observation_type(
        left=values["left"],
        top=values["top"],
        right=values["right"],
        bottom=values["bottom"],
        timestamp_ms=now_ms,
    )
    protocol.runtime.latest_observation = observation
    protocol.runtime.latest_frame = None
    return protocol._parse_result_type(True, observation)
