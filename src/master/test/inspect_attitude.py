"""legacy 姿态链观察脚本.

@file src/master/test/inspect_attitude.py
"""

from seekfree import IMU660RX
from smartcar import ticker
import math
import time

TICK_MS = 10
GYRO_SCALE = 16.384
GYRO_OFFSET_FILE = "/flash/gyro_offset.txt"


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
        q0, q1, q2, q3 = self.w, self.x, self.y, self.z
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
        return math.atan2(
            2.0 * (self.w * self.z + self.x * self.y),
            1.0 - 2.0 * (self.y * self.y + self.z * self.z),
        )


def format_attitude_line(tick, dt_s, quat, heading_est_deg, yaw_deg, gyro_deg_s):
    return (
        "tick=%d dt_s=%.6f quat=(%.6f,%.6f,%.6f,%.6f) "
        "heading_est_deg=%.3f yaw_deg=%.3f gyro_deg_s=(%.3f,%.3f,%.3f)"
    ) % (
        int(tick),
        float(dt_s),
        float(quat[0]),
        float(quat[1]),
        float(quat[2]),
        float(quat[3]),
        float(heading_est_deg),
        float(yaw_deg),
        float(gyro_deg_s[0]),
        float(gyro_deg_s[1]),
        float(gyro_deg_s[2]),
    )


def _load_offsets():
    offsets = [0.0] * 6
    try:
        with open(GYRO_OFFSET_FILE, "r") as handle:
            content = handle.read().strip()
        parts = content.split(",")
        if len(parts) == 6:
            offsets = [float(part) for part in parts]
        elif content:
            offsets[5] = float(content)
    except Exception:
        pass
    return offsets


def _normalize_gyro_deg_s(gx_deg_s, gy_deg_s, gz_deg_s):
    return (
        round(float(gx_deg_s), 1),
        round(float(gy_deg_s), 1),
        round(float(gz_deg_s), 1),
    )


def main():
    imu = IMU660RX()
    imu_data = imu.get()
    imu_offsets = _load_offsets()
    q_est = Quaternion()
    last_yaw_rad = 0.0
    heading_est_deg = 0.0
    pit_flag = False

    def pit_handler(_tick):
        nonlocal pit_flag
        pit_flag = True

    pit1 = ticker(1)
    pit1.capture_list(imu)
    pit1.callback(pit_handler)
    pit1.start(TICK_MS)
    last_time_us = time.ticks_us()
    tick = 0

    try:
        while True:
            if not pit_flag:
                continue
            pit_flag = False
            tick += 1

            current_time_us = time.ticks_us()
            dt_us = time.ticks_diff(current_time_us, last_time_us)
            last_time_us = current_time_us
            dt_s = dt_us / 1000000.0

            if imu_data:
                gx_raw = float(imu_data[3]) - float(imu_offsets[3])
                gy_raw = float(imu_data[4]) - float(imu_offsets[4])
                gz_raw = float(imu_data[5]) - float(imu_offsets[5])
            else:
                gx_raw = 0.0
                gy_raw = 0.0
                gz_raw = 0.0

            gx_deg_s, gy_deg_s, gz_deg_s = _normalize_gyro_deg_s(
                gx_raw / GYRO_SCALE,
                gy_raw / GYRO_SCALE,
                gz_raw / GYRO_SCALE,
            )

            rad_scale = math.pi / 180.0
            q_est.update(
                gx_deg_s * rad_scale,
                gy_deg_s * rad_scale,
                gz_deg_s * rad_scale,
                dt_s,
            )

            curr_yaw_rad = q_est.to_euler_yaw()
            delta_yaw = curr_yaw_rad - last_yaw_rad
            if delta_yaw > math.pi:
                delta_yaw -= 2.0 * math.pi
            elif delta_yaw < -math.pi:
                delta_yaw += 2.0 * math.pi
            last_yaw_rad = curr_yaw_rad
            heading_est_deg += math.degrees(delta_yaw)

            print(
                format_attitude_line(
                    tick=tick,
                    dt_s=dt_s,
                    quat=(q_est.w, q_est.x, q_est.y, q_est.z),
                    heading_est_deg=heading_est_deg,
                    yaw_deg=math.degrees(curr_yaw_rad),
                    gyro_deg_s=(gx_deg_s, gy_deg_s, gz_deg_s),
                )
            )
    finally:
        pit1.stop()


if __name__ == "__main__":
    main()
