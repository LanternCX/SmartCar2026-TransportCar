"""辅车运动学边界.

@file src/assistant/ctrl/kinematics.py
"""

import math


def build_planar_target(dx, dy):
    return {"dx": float(dx), "dy": float(dy)}


def inverse_kinematics(dx, dy, omega):
    vx = float(dy)
    vy = float(dx)
    omega_value = float(omega)
    inv_3 = 1.0 / 3.0
    sqrt3_3 = math.sqrt(3.0) * inv_3
    return {
        "m": (-2.0 * inv_3 * vx) + (omega_value * inv_3),
        "l": (vx * inv_3) + (sqrt3_3 * vy) + (omega_value * inv_3),
        "r": (vx * inv_3) - (sqrt3_3 * vy) + (omega_value * inv_3),
    }
