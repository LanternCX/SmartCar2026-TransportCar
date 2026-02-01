import math


class Quaternion:
    def __init__(self, w=1.0, x=0.0, y=0.0, z=0.0):
        self.w = w
        self.x = x
        self.y = y
        self.z = z

    def normalize(self):
        norm = math.sqrt(
            self.w * self.w + self.x * self.x + self.y * self.y + self.z * self.z
        )
        if norm == 0:
            return
        inv_norm = 1.0 / norm
        self.w *= inv_norm
        self.x *= inv_norm
        self.y *= inv_norm
        self.z *= inv_norm

    def update(self, gx, gy, gz, dt):
        # Quaternion kinematics: q_dot = 0.5 * q * omega
        # omega = (0, gx, gy, gz)
        # Using standard multiplication order for passive rotation or frame update

        q0, q1, q2, q3 = self.w, self.x, self.y, self.z

        # dQ = 0.5 * Q * Omega
        dq0 = 0.5 * (-q1 * gx - q2 * gy - q3 * gz)
        dq1 = 0.5 * (q0 * gx + q2 * gz - q3 * gy)
        dq2 = 0.5 * (q0 * gy - q1 * gz + q3 * gx)
        dq3 = 0.5 * (q0 * gz + q1 * gy - q2 * gx)

        self.w += dq0 * dt
        self.x += dq1 * dt
        self.y += dq2 * dt
        self.z += dq3 * dt
        self.normalize()

    def to_euler_yaw(self):
        # Return Yaw in radians
        # Yaw = atan2(2(q0q3 + q1q2), 1 - 2(q2^2 + q3^2))
        return math.atan2(
            2.0 * (self.w * self.z + self.x * self.y),
            1.0 - 2.0 * (self.y * self.y + self.z * self.z),
        )

    def to_euler_angles(self):
        """
        Return (roll, pitch, yaw) in radians.
        Assuming Z-Y-X convention commonly used.
        """
        w, x, y, z = self.w, self.x, self.y, self.z

        # Roll (x-axis rotation)
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation)
        sinp = 2.0 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)
        else:
            pitch = math.asin(sinp)

        # Yaw (z-axis rotation)
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        return roll, pitch, yaw

    def rotate(self, v):
        """
        Rotate vector v (x, y, z) by this quaternion.
        v_new = q * v * q_conj
        """
        vx, vy, vz = v
        w, x, y, z = self.w, self.x, self.y, self.z

        # Pre-calculate common terms
        ww = w * w
        xx = x * x
        yy = y * y
        zz = z * z
        wx = w * x
        wy = w * y
        wz = w * z
        xy = x * y
        xz = x * z
        yz = y * z

        # Apply rotation matrix derived from quaternion
        # col 0
        rx = (1 - 2 * (yy + zz)) * vx + 2 * (xy - wz) * vy + 2 * (xz + wy) * vz
        # col 1
        ry = 2 * (xy + wz) * vx + (1 - 2 * (xx + zz)) * vy + 2 * (yz - wx) * vz
        # col 2
        rz = 2 * (xz - wy) * vx + 2 * (yz + wx) * vy + (1 - 2 * (xx + yy)) * vz

        return rx, ry, rz

    def rotate_inv(self, v):
        """
        Rotate vector v by inverse of this quaternion (q_conj).
        v_new = q_conj * v * q
        Used for Body -> World transformation if q represents World -> Body.
        """
        vx, vy, vz = v
        # Conjugate quaternion: w, -x, -y, -z
        w, x, y, z = self.w, -self.x, -self.y, -self.z

        # Same formula as rotate, using conjugated components
        ww = w * w
        xx = x * x
        yy = y * y
        zz = z * z
        wx = w * x
        wy = w * y
        wz = w * z
        xy = x * y
        xz = x * z
        yz = y * z

        rx = (1 - 2 * (yy + zz)) * vx + 2 * (xy - wz) * vy + 2 * (xz + wy) * vz
        ry = 2 * (xy + wz) * vx + (1 - 2 * (xx + zz)) * vy + 2 * (yz - wx) * vz
        rz = 2 * (xz - wy) * vx + 2 * (yz + wx) * vy + (1 - 2 * (xx + yy)) * vz

        return rx, ry, rz

    def from_euler(self, roll, pitch, yaw):
        """
        Initialize quaternion from Euler angles (radians).
        Sequence: Z-Y-X (Yaw, Pitch, Roll)
        """
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)

        self.w = cr * cp * cy + sr * sp * sy
        self.x = sr * cp * cy - cr * sp * sy
        self.y = cr * sp * cy + sr * cp * sy
        self.z = cr * cp * sy - sr * sp * cy
        self.normalize()
