"""@brief 视觉协议查询辅助函数."""


def normalize_camera_id(camera_id: str) -> str:
    """@brief 归一化相机标识文本.

    @param camera_id 相机标识
    @return 归一化后的相机标识
    """
    return str(camera_id).strip().lower()


def build_frame_query(camera_id: str) -> str:
    """@brief 构造单相机当前帧查询串."""
    return "?frame=%s" % normalize_camera_id(camera_id)


def is_query_for_camera(line: str, camera_id: str) -> bool:
    """@brief 判断当前查询是否点名指定相机."""
    normalized = normalize_camera_id(camera_id)
    return str(line).strip().lower() == "?frame=%s" % normalized


def is_reserved_query(line: str) -> bool:
    """@brief 判断查询是否保留给视觉协议."""
    text = str(line).strip().lower()
    if not text.startswith("?frame="):
        return False
    return bool(text.split("=", 1)[1].strip())
