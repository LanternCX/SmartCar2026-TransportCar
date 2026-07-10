"""辅车本地视觉任务参数编码

@file src/role/task_sync.py
"""

from micropython import const  # pyright: ignore[reportMissingImports]


ASSISTANT_ORBIT_MODE_NORMAL = const(0)
ASSISTANT_ORBIT_MODE_AVOID_NEGATIVE = const(1)
ASSISTANT_ORBIT_MODE_AVOID_POSITIVE = const(2)
_ASSISTANT_ORBIT_MODES = (
    ASSISTANT_ORBIT_MODE_NORMAL,
    ASSISTANT_ORBIT_MODE_AVOID_NEGATIVE,
    ASSISTANT_ORBIT_MODE_AVOID_POSITIVE,
)


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


def pack_assistant_orbit_arg(mode, object_id):
    """按辅车绕行状态打包绕行模式和物体编号"""

    mode = int(mode)
    if mode not in _ASSISTANT_ORBIT_MODES:
        raise ValueError
    return pack_task_arg(mode, _validate_object_id(object_id))


def unpack_assistant_orbit_mode(arg):
    """按辅车绕行状态读取有名绕行模式"""

    mode = unpack_task_arg_config(arg)
    if mode not in _ASSISTANT_ORBIT_MODES:
        raise ValueError
    return mode


def unpack_assistant_orbit_object_id(arg):
    """按辅车绕行状态读取物体编号"""

    return unpack_task_arg_object_id(arg)


def pack_assistant_avoidance_shift_arg(distance_cm, object_id):
    """按辅车避障平移状态打包厘米距离和物体编号"""

    distance_cm = int(distance_cm)
    if not 1 <= distance_cm <= 255:
        raise ValueError
    return pack_task_arg(distance_cm, _validate_object_id(object_id))


def unpack_assistant_avoidance_shift_distance_cm(arg):
    """按辅车避障平移状态读取厘米距离"""

    distance_cm = unpack_task_arg_config(arg)
    if distance_cm == 0:
        raise ValueError
    return distance_cm


def unpack_assistant_avoidance_shift_object_id(arg):
    """按辅车避障平移状态读取物体编号"""

    return unpack_task_arg_object_id(arg)
