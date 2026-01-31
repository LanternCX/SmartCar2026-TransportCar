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
