"""辅车本地视觉任务参数编码

@file src/role/task_sync.py
"""


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
