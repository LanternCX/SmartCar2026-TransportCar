"""主车底座主数据链运行时.

@file src/master/motion_runtime.py
"""

import math

from . import config, runtime_params


def _clamp(value, lower, upper):
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def _load_ident_lookup(path):
    lookup = {}
    try:
        with open(path, "r") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 3:
                    continue
                try:
                    lookup[str(parts[0])] = (float(parts[1]), float(parts[2]))
                except ValueError:
                    continue
    except OSError:
        return {}
    return lookup


def _load_gyro_offsets(path):
    offsets = [0.0] * 6
    try:
        with open(path, "r") as handle:
            content = handle.read().strip()
    except OSError:
        return tuple(offsets)
    if not content:
        return tuple(offsets)
    parts = content.split(",")
    try:
        if len(parts) == 6:
            for index in range(6):
                offsets[index] = float(parts[index])
        else:
            offsets[5] = float(content)
    except ValueError:
        return tuple([0.0] * 6)
    return tuple(offsets)


def _heading_chain_ready(hw_bundle):
    if hw_bundle is None:
        return False
    imu = hw_bundle.get("imu")
    if imu is None:
        return False
    return any(
        getattr(imu, name, None) is not None
        for name in ("read_calibrated", "heading_deg", "read_raw")
    )


def _encoder_chain_ready(hw_bundle):
    if hw_bundle is None:
        return False
    encoders = hw_bundle.get("encoders")
    if encoders is None:
        return False
    for name in ("m", "l", "r"):
        port = encoders.get(name)
        if port is None:
            return False
        if (
            getattr(port, "read_and_clear", None) is None
            and getattr(port, "read", None) is None
        ):
            return False
    return True


def base_chain_ready(hw_bundle):
    return _heading_chain_ready(hw_bundle) and _encoder_chain_ready(hw_bundle)


class _LowPassFilter:
    def __init__(self, alpha, initial=0.0):
        self.alpha = float(alpha)
        self.state = float(initial)
        self.initialized = False

    def update(self, value):
        value = float(value)
        if not self.initialized:
            self.state = value
            self.initialized = True
            return self.state
        self.state = ((1.0 - self.alpha) * self.state) + (self.alpha * value)
        return self.state


class _SpikeMedianFilter:
    def __init__(self, window):
        self.window = max(3, int(window) or 3)
        if self.window % 2 == 0:
            self.window += 1
        self.buf = []

    def update(self, value):
        if len(self.buf) >= self.window:
            self.buf.pop(0)
        self.buf.append(float(value))
        ordered = sorted(self.buf)
        return ordered[len(ordered) // 2]


class _DiffLimitFilter:
    def __init__(self, max_delta):
        self.max_delta = abs(float(max_delta))
        self.prev = None

    def update(self, value):
        value = float(value)
        if self.prev is None:
            self.prev = value
            return value
        lower = self.prev - self.max_delta
        upper = self.prev + self.max_delta
        value = _clamp(value, lower, upper)
        self.prev = value
        return value


class _DualWindowRegressionFilter:
    def __init__(self, tick_ms, long_window, short_window, combine_w=0.65):
        self.tick_ms = int(tick_ms)
        self.long_window = int(long_window)
        self.short_window = int(short_window)
        self.combine_w = float(combine_w)
        self.sample_idx = 0
        self.long_values = []
        self.short_values = []

    @staticmethod
    def _predict(window, next_t):
        count = len(window)
        if count == 0:
            return 0.0
        if count == 1:
            return float(window[0][1])
        sum_t = 0.0
        sum_t2 = 0.0
        sum_y = 0.0
        sum_ty = 0.0
        for stamp, value in window:
            stamp = float(stamp)
            value = float(value)
            sum_t += stamp
            sum_t2 += stamp * stamp
            sum_y += value
            sum_ty += stamp * value
        denom = (count * sum_t2) - (sum_t * sum_t)
        if denom == 0.0:
            return float(window[-1][1])
        slope = ((count * sum_ty) - (sum_t * sum_y)) / denom
        intercept = (sum_y - (slope * sum_t)) / count
        return (slope * next_t) + intercept

    def update(self, value):
        stamp = float(self.sample_idx * self.tick_ms)
        self.sample_idx += 1
        pair = (stamp, float(value))
        self.long_values.append(pair)
        self.short_values.append(pair)
        if len(self.long_values) > self.long_window:
            self.long_values.pop(0)
        if len(self.short_values) > self.short_window:
            self.short_values.pop(0)
        next_t = float(self.sample_idx * self.tick_ms)
        long_pred = self._predict(self.long_values, next_t)
        short_pred = self._predict(self.short_values, next_t)
        return (short_pred * self.combine_w) + (long_pred * (1.0 - self.combine_w))


class _Quaternion:
    def __init__(self):
        self.w = 1.0
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0

    def update(self, gx, gy, gz, dt_s):
        q0 = self.w
        q1 = self.x
        q2 = self.y
        q3 = self.z
        dq0 = 0.5 * (-q1 * gx - q2 * gy - q3 * gz)
        dq1 = 0.5 * (q0 * gx + q2 * gz - q3 * gy)
        dq2 = 0.5 * (q0 * gy - q1 * gz + q3 * gx)
        dq3 = 0.5 * (q0 * gz + q1 * gy - q2 * gx)
        self.w += dq0 * dt_s
        self.x += dq1 * dt_s
        self.y += dq2 * dt_s
        self.z += dq3 * dt_s
        norm = math.sqrt(
            (self.w * self.w)
            + (self.x * self.x)
            + (self.y * self.y)
            + (self.z * self.z)
        )
        if norm == 0.0:
            self.w = 1.0
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
            return
        inv_norm = 1.0 / norm
        self.w *= inv_norm
        self.x *= inv_norm
        self.y *= inv_norm
        self.z *= inv_norm

    def yaw_rad(self):
        return math.atan2(
            2.0 * ((self.w * self.z) + (self.x * self.y)),
            1.0 - (2.0 * ((self.y * self.y) + (self.z * self.z))),
        )


class _OmniKinematics:
    def __init__(self):
        self.wheel_diameter = 0.060
        self.gear_ratio = 30.0
        self.encoder_ppr = 7.0
        self.counts_per_rev = self.encoder_ppr * self.gear_ratio * 4.0
        self.m_per_pulse = (self.wheel_diameter * math.pi) / self.counts_per_rev

    def pulses_to_m(self, pulses):
        return float(pulses) * self.m_per_pulse

    def velocity_pulses_to_m_s(self, pulse_speed, dt_s):
        return self.pulses_to_m(pulse_speed) / float(dt_s)

    def forward_kinematics(self, vm, vl, vr):
        vx = (0.5 * (float(vl) + float(vr))) - float(vm)
        vy = (math.sqrt(3.0) * 0.5) * (float(vl) - float(vr))
        omega = float(vl) + float(vr) + float(vm)
        return (vx, vy, omega)

    def inverse_kinematics(self, vx, vy, omega):
        inv_3 = 1.0 / 3.0
        sqrt3_3 = math.sqrt(3.0) * inv_3
        return {
            "m": (-2.0 * inv_3 * float(vx)) + (float(omega) * inv_3),
            "l": (float(vx) * inv_3) + (sqrt3_3 * float(vy)) + (float(omega) * inv_3),
            "r": (float(vx) * inv_3) - (sqrt3_3 * float(vy)) + (float(omega) * inv_3),
        }


class _Odometry:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0

    def update(self, vx_robot, vy_robot, heading_rad, dt_s):
        cos_heading = math.cos(float(heading_rad))
        sin_heading = math.sin(float(heading_rad))
        world_x = (float(vx_robot) * cos_heading) - (float(vy_robot) * sin_heading)
        world_y = (float(vx_robot) * sin_heading) + (float(vy_robot) * cos_heading)
        self.x += world_x * float(dt_s)
        self.y += world_y * float(dt_s)
        return (self.x, self.y)


class _SpeedController:
    def __init__(self, output_limit, plant_gain=None, plant_tau=None):
        self.output_limit = float(output_limit)
        self.plant_gain = plant_gain
        self.plant_tau = plant_tau
        self.kp = 0.0
        self.ki = 0.0
        self.ki2 = 0.0
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_target = 0.0

    def set_gains(self, kp, ki, ki2=0.0):
        self.kp = float(kp)
        self.ki = float(ki)
        self.ki2 = float(ki2)

    def _feedforward(self, target, dt_s):
        if self.plant_gain is None or float(self.plant_gain) <= 0.0:
            return 0.0
        if dt_s <= 0.0:
            dt_s = 1.0
        dr_dt = (float(target) - self.prev_target) / float(dt_s)
        tau_term = (float(self.plant_tau or 0.0)) * dr_dt
        return (float(target) + tau_term) / float(self.plant_gain)

    def update(self, target, now, dt_s):
        if dt_s <= 0.0:
            dt_s = 1.0
        err = float(target) - float(now)
        dp = self.kp * (err - self.prev_error)
        di = self.ki * err * float(dt_s)
        i2 = self.ki2 * (err * abs(err))
        self.output = _clamp(
            self.output + dp + di + i2,
            -self.output_limit,
            self.output_limit,
        )
        total = _clamp(
            self.output + self._feedforward(target, dt_s),
            -self.output_limit,
            self.output_limit,
        )
        self.prev_error = err
        self.prev_target = float(target)
        return total

    def reset(self):
        self.output = 0.0
        self.prev_error = 0.0
        self.prev_target = 0.0


class MotionRuntime:
    """负责主车底座主数据链 owner.

    @brief 持有 IMU、编码器、里程和航向角保持链路, 供 app 在每个周期读取, 不承担视觉状态机职责。
    """

    def __init__(self, hw_bundle=None):
        self.hw_bundle = hw_bundle
        self.pid_map = dict(runtime_params.PID_MAP)
        self.last_target = {"kind": "hold"}
        self.last_applied_target = {
            "kind": "hold",
            "vx": 0.0,
            "vy": 0.0,
            "omega": 0.0,
        }
        self._control_seq = 0
        self.heading_hold_enabled = True
        self.yaw_kp = float(runtime_params.YAW_KP)
        self.yaw_ki = float(runtime_params.YAW_KI)
        self.yaw_i_max = float(runtime_params.YAW_I_MAX)
        self.auto_omega_max = float(runtime_params.AUTO_OMEGA_MAX)
        self.tick_ms = int(runtime_params.CONTROL_TICK_MS)
        self.tick_s = float(self.tick_ms) / 1000.0
        self.gyro_scale = float(config.GYRO_SCALE)
        self.target_heading_deg = 0.0
        self._yaw_integral = 0.0
        self._heading_target_ready = False
        self.ident_lookup = _load_ident_lookup(config.IDENT_RESULTS_FILE)
        self.imu_offsets = _load_gyro_offsets(config.GYRO_OFFSET_FILE)
        self.imu_raw = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self.imu_calibrated = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self.encoder_ticks = {"m": 0.0, "l": 0.0, "r": 0.0}
        self.wheel_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
        self.target_wheel_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
        self.motor_duties = {"m": 0, "l": 0, "r": 0}
        self.heading_est_deg = 0.0
        self.yaw_rate_deg_s = 0.0
        self.odom = [0.0, 0.0]
        self.q_est = _Quaternion()
        self.kinematics = _OmniKinematics()
        self.odometry = _Odometry()
        self.gyro_lpf = _LowPassFilter(runtime_params.GYRO_LPF_ALPHA, initial=0.0)
        self._wheel_filters = {}
        self._wheel_controllers = {}
        for name in ("m", "l", "r"):
            gains = self.pid_map.get(name, (0.0, 0.0, 0.0))
            plant_gain, plant_tau = self.ident_lookup.get(name, (None, None))
            self._wheel_filters[name] = {
                "spike": _SpikeMedianFilter(runtime_params.SPEED_FILTER_WINDOW),
                "diff": _DiffLimitFilter(runtime_params.SPEED_DIFF_MAX_DELTA),
                "reg": _DualWindowRegressionFilter(
                    tick_ms=self.tick_ms,
                    long_window=runtime_params.LONG_WINDOW,
                    short_window=runtime_params.SHORT_WINDOW,
                ),
            }
            controller = _SpeedController(
                output_limit=runtime_params.MAX_DUTY,
                plant_gain=plant_gain,
                plant_tau=plant_tau,
            )
            controller.set_gains(gains[0], gains[1], gains[2])
            self._wheel_controllers[name] = controller
        self._last_yaw_rad = 0.0
        self._last_cycle_token = None
        self._last_base_snapshot = None
        imu = self._imu_port()
        if imu is not None:
            apply_offsets = getattr(imu, "apply_offsets", None)
            if apply_offsets is not None:
                apply_offsets(self.imu_offsets)

    def _imu_port(self):
        if self.hw_bundle is None:
            return None
        return self.hw_bundle.get("imu")

    def _encoder_bundle(self):
        if self.hw_bundle is None:
            return None
        return self.hw_bundle.get("encoders")

    def _motor_bundle(self):
        if self.hw_bundle is None:
            return None
        return self.hw_bundle.get("motors")

    def _heading_chain_ready(self):
        return _heading_chain_ready(self.hw_bundle)

    def _encoder_chain_ready(self):
        return _encoder_chain_ready(self.hw_bundle)

    def _base_chain_ready(self):
        return base_chain_ready(self.hw_bundle)

    def _capture_heading_target(self):
        self.target_heading_deg = float(self.heading_est_deg)
        self._yaw_integral = 0.0
        self._heading_target_ready = True

    def _ensure_heading_target(self):
        if not self._heading_target_ready:
            self._capture_heading_target()

    def _compute_heading_correction(self, heading_deg):
        if not self.heading_hold_enabled:
            return 0.0
        error = float(self.target_heading_deg) - float(heading_deg)
        self._yaw_integral += error
        self._yaw_integral = _clamp(self._yaw_integral, -self.yaw_i_max, self.yaw_i_max)
        omega = (error * self.yaw_kp) + (self._yaw_integral * self.yaw_ki)
        return _clamp(omega, -self.auto_omega_max, self.auto_omega_max)

    def _apply_motor_output(self, vx, vy, omega):
        wheel_targets = self.kinematics.inverse_kinematics(
            float(vy), float(vx), float(omega)
        )
        limit = float(runtime_params.FOLLOW_OUTPUT_LIMIT)
        motors = self._motor_bundle()
        for name in ("m", "l", "r"):
            raw = _clamp(float(wheel_targets.get(name, 0.0)), -limit, limit)
            self.target_wheel_speeds[name] = raw
            duty = int(
                self._wheel_controllers[name].update(
                    raw,
                    self.wheel_speeds.get(name, 0.0),
                    self.tick_s,
                )
            )
            self.motor_duties[name] = duty
            if motors is None:
                continue
            motor = motors.get(name)
            if motor is not None:
                motor.set_duty(duty)

    def _resolve_applied_target(self, target, heading_deg):
        kind = str(target.get("kind", "hold"))
        if kind == "vel":
            vx = float(target.get("vx", 0.0))
            vy = float(target.get("vy", 0.0))
            omega = float(target.get("omega", 0.0)) + self._compute_heading_correction(
                heading_deg
            )
            return {
                "kind": "vel",
                "vx": vx,
                "vy": vy,
                "omega": _clamp(omega, -self.auto_omega_max, self.auto_omega_max),
            }
        return {
            "kind": "hold",
            "vx": 0.0,
            "vy": 0.0,
            "omega": self._compute_heading_correction(heading_deg),
        }

    def _read_imu_sample(self):
        imu = self._imu_port()
        heading_override = None
        if imu is None:
            self.imu_raw = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            self.imu_calibrated = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            return heading_override

        read_calibrated = getattr(imu, "read_calibrated", None)
        if read_calibrated is not None:
            self.imu_calibrated = tuple(read_calibrated())
            self.imu_raw = tuple(getattr(imu, "last_raw", self.imu_calibrated))
            return heading_override
        if hasattr(imu, "heading_deg"):
            heading_override = float(imu.heading_deg())
            self.imu_raw = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            self.imu_calibrated = self.imu_raw
            return heading_override
        read_raw = getattr(imu, "read_raw", None)
        if read_raw is None:
            self.imu_raw = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            self.imu_calibrated = self.imu_raw
            return heading_override
        self.imu_raw = tuple(read_raw())
        calibrated = []
        for index, value in enumerate(self.imu_raw):
            calibrated.append(float(value) - float(self.imu_offsets[index]))
        self.imu_calibrated = tuple(calibrated)
        return heading_override

    def _read_encoder_ticks(self):
        encoders = self._encoder_bundle()
        if encoders is None:
            return {"m": 0.0, "l": 0.0, "r": 0.0}

        raw_ticks = {}
        for name in ("m", "l", "r"):
            port = encoders.get(name)
            if port is None:
                raw_ticks[name] = 0.0
                continue
            reader = getattr(port, "read_and_clear", None)
            if reader is not None:
                raw_ticks[name] = float(reader())
                continue
            read_ticks = getattr(port, "read", None)
            if read_ticks is None:
                raw_ticks[name] = 0.0
                continue
            raw_ticks[name] = float(read_ticks())
            clearer = getattr(port, "clear", None)
            if clearer is not None:
                clearer()
        return raw_ticks

    def refresh_base_chain(self, cycle_token=None):
        if cycle_token is not None and cycle_token is self._last_cycle_token:
            if self._last_base_snapshot is None:
                return {}
            return dict(self._last_base_snapshot)

        heading_override = self._read_imu_sample()

        gx_raw = float(self.imu_calibrated[3])
        gy_raw = float(self.imu_calibrated[4])
        gz_raw = float(self.imu_calibrated[5])
        gx_rad_s = math.radians(gx_raw / self.gyro_scale)
        gy_rad_s = math.radians(gy_raw / self.gyro_scale)
        gz_rad_s = math.radians(gz_raw / self.gyro_scale)
        self.q_est.update(gx_rad_s, gy_rad_s, gz_rad_s, self.tick_s)
        curr_yaw_rad = self.q_est.yaw_rad()
        delta_yaw = curr_yaw_rad - self._last_yaw_rad
        if delta_yaw > math.pi:
            delta_yaw -= 2.0 * math.pi
        elif delta_yaw < -math.pi:
            delta_yaw += 2.0 * math.pi
        self._last_yaw_rad = curr_yaw_rad
        self.heading_est_deg += math.degrees(delta_yaw)
        self.yaw_rate_deg_s = self.gyro_lpf.update(gz_raw / self.gyro_scale)
        if heading_override is not None:
            self.heading_est_deg = float(heading_override)
            self._last_yaw_rad = math.radians(self.heading_est_deg)
        self._ensure_heading_target()

        raw_ticks = self._read_encoder_ticks()
        self.encoder_ticks = dict(raw_ticks)

        for name in ("m", "l", "r"):
            filtered = self._wheel_filters[name]["spike"].update(raw_ticks[name])
            filtered = self._wheel_filters[name]["diff"].update(filtered)
            filtered = self._wheel_filters[name]["reg"].update(filtered)
            self.wheel_speeds[name] = float(filtered)

        vm = self.kinematics.velocity_pulses_to_m_s(self.wheel_speeds["m"], self.tick_s)
        vl = self.kinematics.velocity_pulses_to_m_s(self.wheel_speeds["l"], self.tick_s)
        vr = self.kinematics.velocity_pulses_to_m_s(self.wheel_speeds["r"], self.tick_s)
        vx_robot, vy_robot, _ = self.kinematics.forward_kinematics(vm, vl, vr)
        odom_x, odom_y = self.odometry.update(
            vx_robot,
            vy_robot,
            math.radians(self.heading_est_deg),
            self.tick_s,
        )
        self.odom[0] = odom_x
        self.odom[1] = odom_y
        snapshot = {
            "imu_raw": tuple(self.imu_raw),
            "encoder_ticks": dict(self.encoder_ticks),
            "heading_est_deg": float(self.heading_est_deg),
            "odom": (float(self.odom[0]), float(self.odom[1])),
            "yaw_rate_deg_s": float(self.yaw_rate_deg_s),
            "base_ok": 1 if self._base_chain_ready() else 0,
        }
        self._last_cycle_token = cycle_token
        self._last_base_snapshot = dict(snapshot)
        return snapshot

    def apply_self_target(self, target):
        self.last_target = dict(target)
        kind = str(self.last_target.get("kind", "hold"))
        if kind != "vel":
            self.last_target = {"kind": "hold"}
            if self._heading_target_ready:
                self._capture_heading_target()
        return dict(self.last_target)

    def next_control_seq(self):
        self._control_seq += 1
        return self._control_seq

    def update_heading_hold(self, current_heading_deg, cycle_token=None):
        target = dict(self.last_target)
        heading_deg = float(current_heading_deg)
        if self._imu_port() is not None:
            self.refresh_base_chain(cycle_token=cycle_token)
            heading_deg = float(self.heading_est_deg)
        applied_target = self._resolve_applied_target(target, heading_deg)
        self.last_applied_target = dict(applied_target)
        return applied_target

    def execute_control_loop(self, cycle_token=None):
        self.refresh_base_chain(cycle_token=cycle_token)
        applied_target = self._resolve_applied_target(
            self.last_target, self.heading_est_deg
        )
        self.last_applied_target = dict(applied_target)
        self._apply_motor_output(
            applied_target.get("vx", 0.0),
            applied_target.get("vy", 0.0),
            applied_target.get("omega", 0.0),
        )
        return {
            "target": dict(self.last_applied_target),
            "heading_est_deg": float(self.heading_est_deg),
            "yaw_rate_deg_s": float(self.yaw_rate_deg_s),
            "odom": (float(self.odom[0]), float(self.odom[1])),
        }
