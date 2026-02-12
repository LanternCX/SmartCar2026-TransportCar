"""指令解析与查询响应，行为与原版保持一致。"""
import math
from control.pid_math import clamp
from config.params import V_CMD_MAX


def parse_command(cmd_str):
    """
    解析键值对命令字符串，返回字典或 None。
    """
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return None

    if cmd_str == "reset":
        return {"reset": True}

    parts = cmd_str.split(",")
    cmd = {}
    for part in parts:
        if "=" not in part:
            continue
        key, val_str = part.split("=", 1)
        key = key.strip().lower()

        if key == "print":
            cmd["print"] = val_str.strip()
            continue

        try:
            val = float(val_str.strip())
        except ValueError:
            continue

        if key == "vx":
            cmd["vx"] = clamp(val, -V_CMD_MAX, V_CMD_MAX)
        elif key == "rear":
            cmd["rear"] = val != 0
        elif key == "vy":
            cmd["vy"] = clamp(val, -V_CMD_MAX, V_CMD_MAX)
        elif key == "dx":
            cmd["dx"] = val
        elif key == "dy":
            cmd["dy"] = val
        elif key in ("omega", "w"):
            cmd["omega"] = clamp(val, -V_CMD_MAX, V_CMD_MAX)
        elif key in ("angle", "yaw"):
            cmd["angle"] = val
        elif key in ("d_angle", "dyaw", "da"):
            cmd["d_angle"] = val
        elif key == "x":
            cmd["x"] = val
        elif key == "y":
            cmd["y"] = val
        elif key == "reset":
            cmd["reset"] = val != 0

    return cmd if cmd else None


def handle_query(token, odometry, heading_est, command_lock, uart6):
    token = token.strip().lower()
    if token == "pos":
        uart6.write("?pos=%.3f,%.3f,%.2f\r\n" % (odometry.x, odometry.y, heading_est))
    elif token == "lock":
        uart6.write("?lock=%d\r\n" % (1 if command_lock else 0))
    else:
        uart6.write("?unknown=%s\r\n" % token)
