"""底盘姿态估计与里程计更新."""

import math

from config.params import GYRO_SCALE


class AttitudeEstimator:
    """封装 IMU、航向和里程计更新顺序."""

    def update_attitude(self, state, dt_s):
        """按既有顺序更新 IMU、姿态和里程计."""
        state.imu_data = state.imu.get()
        if state.imu_data:
            gx_raw = float(state.imu_data[3]) - state.imu_offsets[3]
            gy_raw = float(state.imu_data[4]) - state.imu_offsets[4]
            gz_raw = float(state.imu_data[5]) - state.imu_offsets[5]
        else:
            gx_raw = 0.0
            gy_raw = 0.0
            gz_raw = 0.0
        state.last_gz_raw = gz_raw

        rad_scale = (math.pi / 180.0) / GYRO_SCALE
        gx = gx_raw * rad_scale
        gy = gy_raw * rad_scale
        gz = gz_raw * rad_scale
        state.q_est.update(gx, gy, gz, dt_s)

        curr_yaw_rad = state.q_est.to_euler_yaw()
        delta_yaw = curr_yaw_rad - state.last_yaw_rad
        if delta_yaw > math.pi:
            delta_yaw -= 2.0 * math.pi
        elif delta_yaw < -math.pi:
            delta_yaw += 2.0 * math.pi
        state.last_yaw_rad = curr_yaw_rad

        state.yaw_rate = state.gyro_lpf.update(gz * (180.0 / math.pi))

        vm_pulse = state.wheel_states[0]["filtered_speed"]
        vl_pulse = state.wheel_states[1]["filtered_speed"]
        vr_pulse = state.wheel_states[2]["filtered_speed"]

        vm_mps = state.kinematics.velocity_pulses_to_m_s(vm_pulse, dt_s)
        vl_mps = state.kinematics.velocity_pulses_to_m_s(vl_pulse, dt_s)
        vr_mps = state.kinematics.velocity_pulses_to_m_s(vr_pulse, dt_s)
        vx_rob_mps, vy_rob_mps, _ = state.kinematics.forward_kinematics(
            vm_mps, vl_mps, vr_mps
        )

        state.odometry.update(
            vx_rob_mps, vy_rob_mps, math.radians(state.heading_est), dt_s
        )
        state.heading_est += math.degrees(delta_yaw)
