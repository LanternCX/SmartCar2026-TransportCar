"""辅车本地视觉任务参数编码

@file src/role/task_sync.py
"""

from micropython import const  # pyright: ignore[reportMissingImports]


_ASSISTANT_ORBIT_OFFSET_BIAS = const(90)


def pack_task_arg(config_id, object_id):
    """把视觉配置号与物体编号打包进单个 i16 参数槽位"""

    packed = (int(config_id) & 0xFF) | ((int(object_id) & 0xFF) << 8)
    if packed >= 0x8000:
        packed -= 0x10000
    return packed


def unpack_task_arg_config(arg):
    """读取任务参数中的视觉配置号"""

    return int(arg) & 0xFF


def unpack_task_arg_object_id(arg):
    """读取任务参数中的物体编号"""

    return (int(arg) >> 8) & 0xFF


def _validate_object_id(object_id):
    object_id = int(object_id)
    if not 0 <= object_id <= 255:
        raise ValueError
    return object_id


def pack_assistant_orbit_arg(offset_deg, object_id):
    """按辅车绕行状态打包相对推动角度和物体编号"""

    offset_deg = float(offset_deg)
    if not -90.0 <= offset_deg <= 90.0:
        raise ValueError
    if offset_deg >= 0.0:
        offset_deg = int(offset_deg + 0.5)
    else:
        offset_deg = int(offset_deg - 0.5)
    return pack_task_arg(
        offset_deg + _ASSISTANT_ORBIT_OFFSET_BIAS,
        _validate_object_id(object_id),
    )


def unpack_assistant_orbit_offset_deg(arg):
    """按辅车绕行状态读取相对推动角度"""

    encoded = unpack_task_arg_config(arg)
    if encoded > _ASSISTANT_ORBIT_OFFSET_BIAS * 2:
        raise ValueError
    return encoded - _ASSISTANT_ORBIT_OFFSET_BIAS


def unpack_assistant_orbit_object_id(arg):
    """按辅车绕行状态读取物体编号"""

    return unpack_task_arg_object_id(arg)
