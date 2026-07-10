"""@file param_manager.py
@brief 辨识参数、陀螺仪零偏和障碍配置的加载工具

此模块提供从文件系统加载电机辨识参数、IMU零偏和障碍配置的功能
"""
import io

from control.pid_store import load_ident_params


def _parse_obstacle_slot(line, field_size_m):
    parts = line.split(",")
    if len(parts) != 3:
        raise ValueError

    edge = parts[0].strip()
    left = float(parts[1].strip())
    right = float(parts[2].strip())

    if edge == "none":
        if left != -1.0 or right != -1.0:
            raise ValueError
        return (None, -1.0, -1.0)

    if edge not in ("top", "bottom", "left", "right"):
        raise ValueError

    if edge == "top" or edge == "bottom":
        axis_size = float(field_size_m[0])
    else:
        axis_size = float(field_size_m[1])
    if not (0.0 <= left < right <= axis_size):
        raise ValueError
    return (edge, left, right)


def load_obstacle_slots(path, field_size_m):
    """读取并严格校验固定三个障碍槽位

    @brief 将障碍配置转换为固定长度 tuple
    @param path 障碍配置文件路径
    @param field_size_m 场地尺寸, 按宽度和高度排列, 单位米
    @return 三个障碍槽位组成的 tuple
    @exception OSError 文件无法读取
    @exception ValueError 配置行数、字段或数值不符合约束
    """

    with open(path, "r") as obstacle_file:
        content = obstacle_file.read()

    if content.endswith("\n"):
        content = content[:-1]
    lines = content.split("\n")
    if len(lines) != 3:
        raise ValueError

    return (
        _parse_obstacle_slot(lines[0], field_size_m),
        _parse_obstacle_slot(lines[1], field_size_m),
        _parse_obstacle_slot(lines[2], field_size_m),
    )


def load_ident_lookup(path, logger=None):
    """@brief 加载各轮子的系统增益和时间常数

    @param path 辨识参数文件路径
    @param logger 日志回调函数(可选), 用于输出加载状态

    @return 字典 {轮子名 -> (gain, tau)}

    @note 依赖 control.pid_store 模块解析原始参数文件
    """
    meta = load_ident_params(path)
    lookup = {}
    for name, vals in meta.items():
        lookup[name] = (vals.get("gain"), vals.get("tau"))
    if logger:
        logger("Loaded ident params: %s" % lookup)
    return lookup


def load_gyro_offsets(path, logger=None):
    """@brief 加载 IMU 六轴零偏或单轴陀螺仪零偏

    支持两种零偏格式:
    - 六轴格式: 六个逗号分隔的浮点数(加速度X/Y/Z, 陀螺仪X/Y/Z)
    - 单轴格式: 单个浮点数(仅陀螺仪Z轴偏移)

    @param path 零偏文件路径
    @param logger 日志回调函数(可选), 用于输出加载状态或异常信息

    @return 长度为 6 的列表, 表示 [accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z] 的零偏
            若文件不存在或格式无效, 返回全 0 列表以避免上层模块崩溃
    """
    offsets = [0.0] * 6
    try:
        with io.open(path, "r") as f:
            content = f.read().strip()
            parts = content.split(",")
            if len(parts) == 6:
                offsets = [float(x) for x in parts]
                if logger:
                    logger("Loaded IMU Offsets: %s" % offsets)
            else:
                offsets[5] = float(content)
                if logger:
                    logger("Loaded Single Axis Gyro Offset: %.4f" % offsets[5])
    except (OSError, ValueError):
        if logger:
            logger("Gyro Offset file not found or invalid, using 0.0")
    return offsets


def save_gyro_offsets(path, offsets):
    """@brief 保存 IMU 六轴零偏

    @param path 零偏文件路径
    @param offsets 长度为 6 的零偏列表, 顺序为 [accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z]
    """
    f = io.open(path, "w")
    try:
        f.write(",".join(["%.4f" % float(value) for value in offsets]))
    finally:
        f.close()
