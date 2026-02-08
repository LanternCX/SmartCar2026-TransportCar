"""辨识参数与陀螺仪零偏的加载工具。"""
from control.pid_store import load_ident_params


def load_ident_lookup(path, logger=None):
    """加载各轮子的 (gain, tau) 映射"""
    meta = load_ident_params(path)
    lookup = {}
    for name, vals in meta.items():
        lookup[name] = (vals.get("gain"), vals.get("tau"))
    if logger:
        logger("Loaded ident params: %s" % lookup)
    return lookup


def load_gyro_offsets(path, logger=None):
    """加载 IMU 六轴零偏"""
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
