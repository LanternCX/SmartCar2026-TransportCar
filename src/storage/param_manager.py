"""@file param_manager.py
@brief 辨识参数与陀螺仪零偏的加载工具

此模块提供从文件系统加载电机辨识参数和IMU零偏的功能,
支持六轴零偏格式和单轴零偏格式
"""
from control.pid_store import load_ident_params


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
        with open(path, "r") as f:
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
