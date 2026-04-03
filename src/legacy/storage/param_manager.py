"""辨识参数与陀螺仪零偏的加载工具."""
from control.pid_store import load_ident_params
 


def load_ident_lookup(path, logger=None):
    """加载各轮子的系统增益和时间常数.
    
    参数:
        path: 辨识参数文件路径.
        logger: 日志回调函数(可选).
    
    返回:
        字典 {轮子名 -> (gain, tau)}.
    """
    meta = load_ident_params(path)
    lookup = {}
    for name, vals in meta.items():
        lookup[name] = (vals.get("gain"), vals.get("tau"))
    if logger:
        logger("Loaded ident params: %s" % lookup)
    return lookup


def load_gyro_offsets(path, logger=None):
    """加载 IMU 六轴零偏或遗留的单轴陀螺仪零偏.
    
    支持两种格式:
    - 新格式:六个逗号分隔的浮点数(加速度X/Y/Z, 陀螺仪X/Y/Z).
    - 遗留格式:单个浮点数(仅陀螺仪Z轴偏移).
    
    参数:
        path: 零偏文件路径.
        logger: 日志回调函数(可选).
    
    返回:
        长度为 6 的列表,表示 [accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z] 的零偏.
        若文件不存在或无效,返回全 0.
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
                    logger("Loaded Legacy Gyro Offset: %.4f" % offsets[5])
    except (OSError, ValueError):
        if logger:
            logger("Gyro Offset file not found or invalid, using 0.0")
    return offsets
