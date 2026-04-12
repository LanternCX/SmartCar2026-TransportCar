"""@brief 视觉状态机数据类型与基础数值 helper."""


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


class VisionStateConfig:
    def __init__(
        self,
        target_center_x_px,
        target_bottom_px,
        angle_kp,
        dist_kp,
        dx_kp,
        push_dx_kp,
        push_dy_m,
        push_distance_m,
        push_angle_deg,
        angle_deadzone_px,
        angle_reentry_px,
        dist_deadzone_px,
        dx_deadzone_px,
        heading_tolerance_deg,
        stable_frames,
        max_dx_m,
        max_dy_m,
        max_d_angle_deg,
        done_hold_ms,
    ):
        self.target_center_x_px = float(target_center_x_px)
        self.target_bottom_px = float(target_bottom_px)
        self.angle_kp = float(angle_kp)
        self.dist_kp = float(dist_kp)
        self.dx_kp = float(dx_kp)
        self.push_dx_kp = float(push_dx_kp)
        self.push_dy_m = float(push_dy_m)
        self.push_distance_m = float(push_distance_m)
        self.push_angle_deg = float(push_angle_deg)
        self.angle_deadzone_px = float(angle_deadzone_px)
        self.angle_reentry_px = float(angle_reentry_px)
        self.dist_deadzone_px = float(dist_deadzone_px)
        self.dx_deadzone_px = float(dx_deadzone_px)
        self.heading_tolerance_deg = float(heading_tolerance_deg)
        self.stable_frames = int(stable_frames)
        self.max_dx_m = float(max_dx_m)
        self.max_dy_m = float(max_dy_m)
        self.max_d_angle_deg = float(max_d_angle_deg)
        self.done_hold_ms = int(done_hold_ms)


class VisionMachineInputs:
    def __init__(
        self,
        observation,
        heading_deg,
        odom_x,
        odom_y,
        now_ms,
        target_role=None,
        obstacle_summary=None,
    ):
        self.observation = observation
        self.heading_deg = float(heading_deg)
        self.odom_x = float(odom_x)
        self.odom_y = float(odom_y)
        self.now_ms = int(now_ms)
        self.target_role = None if target_role is None else str(target_role)
        self.obstacle_summary = obstacle_summary


class VisionControlIntent:
    def __init__(self, active, dx_body, dy_body, d_angle_deg, rear_only_mode):
        self.active = bool(active)
        self.dx_body = float(dx_body)
        self.dy_body = float(dy_body)
        self.d_angle_deg = float(d_angle_deg)
        self.rear_only_mode = bool(rear_only_mode)


class VisionStepResult:
    def __init__(self, state: int, intent: VisionControlIntent):
        self.state = int(state)
        self.intent = intent
