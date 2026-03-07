"""视觉状态机与相对控制意图转换."""

import math

from services.vision_protocol import VisionObservation


def _clamp(value: float, lower: float, upper: float) -> float:
    """将数值限制在给定区间内."""
    return max(lower, min(upper, value))


def normalize_angle(angle_deg: float) -> float:
    """将角度规范到 (-180, 180] 区间."""
    while angle_deg > 180.0:
        angle_deg -= 360.0
    while angle_deg <= -180.0:
        angle_deg += 360.0
    return angle_deg


class SMState:
    """视觉状态机状态常量."""

    IDLE = 0
    ALIGN_ANGLE = 1
    ALIGN_DIST = 2
    ALIGN_DX = 3
    ORBITING = 4
    PUSHING = 5
    RETURNING = 6
    DONE = 7


class VisionStateConfig:
    """视觉状态机参数集合."""

    def __init__(
        self,
        target_x_px: float,
        target_y_px: float,
        angle_kp: float,
        dist_kp: float,
        dx_kp: float,
        push_dx_kp: float,
        push_dy_m: float,
        push_distance_m: float,
        push_angle_deg: float,
        angle_deadzone_px: float,
        angle_reentry_px: float,
        dist_deadzone_px: float,
        dx_deadzone_px: float,
        heading_tolerance_deg: float,
        stable_frames: int,
        max_dx_m: float,
        max_dy_m: float,
        max_d_angle_deg: float,
        done_hold_ms: int,
    ):
        """保存状态机所需全部控制参数."""
        self.target_x_px = float(target_x_px)
        self.target_y_px = float(target_y_px)
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
    """单次状态机计算的输入快照."""

    def __init__(
        self,
        observation,
        heading_deg: float,
        odom_x: float,
        odom_y: float,
        now_ms: int,
    ):
        """保存视觉、姿态、里程计与时间输入."""
        self.observation = observation
        self.heading_deg = float(heading_deg)
        self.odom_x = float(odom_x)
        self.odom_y = float(odom_y)
        self.now_ms = int(now_ms)


class VisionControlIntent:
    """视觉状态机输出的相对控制意图."""

    def __init__(
        self,
        active: bool,
        dx_body: float,
        dy_body: float,
        d_angle_deg: float,
        rear_only_mode: bool,
    ):
        """保存本周期相对位置与姿态目标."""
        self.active = bool(active)
        self.dx_body = float(dx_body)
        self.dy_body = float(dy_body)
        self.d_angle_deg = float(d_angle_deg)
        self.rear_only_mode = bool(rear_only_mode)


class VisionResolvedTarget:
    """由相对控制意图换算得到的绝对目标."""

    def __init__(self, x: float, y: float, angle_deg: float, rear_only_mode: bool):
        """保存本周期绝对位置与角度目标."""
        self.x = float(x)
        self.y = float(y)
        self.angle_deg = float(angle_deg)
        self.rear_only_mode = bool(rear_only_mode)


class VisionStepResult:
    """单步状态机输出结果."""

    def __init__(self, state: int, intent: VisionControlIntent):
        """保存状态与控制意图."""
        self.state = int(state)
        self.intent = intent


def resolve_relative_intent(
    intent: VisionControlIntent, odom_x: float, odom_y: float, heading_deg: float
):
    """将相对控制意图转换为本周期绝对目标."""
    if not intent.active:
        return None

    theta_rad = math.radians(heading_deg)
    cos_t = math.cos(theta_rad)
    sin_t = math.sin(theta_rad)
    target_x = odom_x + intent.dx_body * cos_t - intent.dy_body * sin_t
    target_y = odom_y + intent.dx_body * sin_t + intent.dy_body * cos_t
    target_angle = normalize_angle(heading_deg + intent.d_angle_deg)
    return VisionResolvedTarget(target_x, target_y, target_angle, intent.rear_only_mode)


class VisionStateMachine:
    """将视觉观测映射为相对位置式控制意图的状态机."""

    def __init__(self, config: VisionStateConfig, initial_state: int = SMState.IDLE):
        """初始化状态机运行时状态."""
        self.config = config
        self.state = initial_state
        self._stable_counter = 0
        self._push_start_x = 0.0
        self._push_start_y = 0.0
        self._done_since_ms = 0

    def start_push(self, odom_x: float, odom_y: float) -> None:
        """记录推行阶段起点."""
        self._push_start_x = float(odom_x)
        self._push_start_y = float(odom_y)

    def reset(self) -> None:
        """重置状态机到空闲态."""
        self.state = SMState.IDLE
        self._stable_counter = 0
        self._push_start_x = 0.0
        self._push_start_y = 0.0
        self._done_since_ms = 0

    def _inactive_result(self) -> VisionStepResult:
        """生成空控制结果."""
        return VisionStepResult(
            self.state,
            VisionControlIntent(
                active=False,
                dx_body=0.0,
                dy_body=0.0,
                d_angle_deg=0.0,
                rear_only_mode=False,
            ),
        )

    def _active_result(
        self, dx_body: float, dy_body: float, d_angle_deg: float, rear_only_mode: bool
    ) -> VisionStepResult:
        """生成有效控制结果."""
        return VisionStepResult(
            self.state,
            VisionControlIntent(
                active=True,
                dx_body=dx_body,
                dy_body=dy_body,
                d_angle_deg=d_angle_deg,
                rear_only_mode=rear_only_mode,
            ),
        )

    def step(self, inputs: VisionMachineInputs) -> VisionStepResult:
        """推进一轮状态机并输出本周期控制意图."""
        observation = inputs.observation

        if self.state in (SMState.ALIGN_ANGLE, SMState.ALIGN_DIST, SMState.ALIGN_DX):
            if observation is None:
                self.state = SMState.IDLE
                self._stable_counter = 0
                return self._inactive_result()

        if self.state == SMState.IDLE:
            self._stable_counter = 0
            if observation is None:
                return self._inactive_result()
            self.state = SMState.ALIGN_ANGLE

        if self.state == SMState.ALIGN_ANGLE:
            x_error = observation.x - self.config.target_x_px  # type: ignore[union-attr]
            if abs(x_error) <= self.config.angle_deadzone_px:
                self._stable_counter += 1
                if self._stable_counter >= self.config.stable_frames:
                    self.state = SMState.ALIGN_DIST
                    self._stable_counter = 0
                return self._inactive_result()

            self._stable_counter = 0
            d_angle = _clamp(
                x_error * self.config.angle_kp,
                -self.config.max_d_angle_deg,
                self.config.max_d_angle_deg,
            )
            return self._active_result(0.0, 0.0, d_angle, False)

        if self.state == SMState.ALIGN_DIST:
            x_error = observation.x - self.config.target_x_px  # type: ignore[union-attr]
            if abs(x_error) > self.config.angle_reentry_px:
                self.state = SMState.ALIGN_ANGLE
                self._stable_counter = 0
                return self._inactive_result()

            y_error = observation.y - self.config.target_y_px  # type: ignore[union-attr]
            if abs(y_error) <= self.config.dist_deadzone_px:
                self._stable_counter += 1
                if self._stable_counter >= self.config.stable_frames:
                    self.state = SMState.ALIGN_DX
                    self._stable_counter = 0
                return self._inactive_result()

            self._stable_counter = 0
            dy_body = _clamp(
                y_error * self.config.dist_kp,
                -self.config.max_dy_m,
                self.config.max_dy_m,
            )
            return self._active_result(0.0, dy_body, 0.0, False)

        if self.state == SMState.ALIGN_DX:
            x_error = observation.x - self.config.target_x_px  # type: ignore[union-attr]
            if abs(x_error) <= self.config.dx_deadzone_px:
                self._stable_counter += 1
                if self._stable_counter >= self.config.stable_frames:
                    y_error = observation.y - self.config.target_y_px  # type: ignore[union-attr]
                    heading_error = normalize_angle(
                        self.config.push_angle_deg - inputs.heading_deg
                    )
                    self._stable_counter = 0
                    if abs(y_error) > self.config.dist_deadzone_px:
                        self.state = SMState.ALIGN_DIST
                    elif abs(heading_error) <= self.config.heading_tolerance_deg:
                        self.state = SMState.PUSHING
                        self.start_push(inputs.odom_x, inputs.odom_y)
                    else:
                        self.state = SMState.ORBITING
                return self._inactive_result()

            self._stable_counter = 0
            dx_body = _clamp(
                x_error * self.config.dx_kp,
                -self.config.max_dx_m,
                self.config.max_dx_m,
            )
            return self._active_result(dx_body, 0.0, 0.0, False)

        if self.state == SMState.ORBITING:
            heading_error = normalize_angle(
                self.config.push_angle_deg - inputs.heading_deg
            )
            if abs(heading_error) <= self.config.heading_tolerance_deg:
                self.state = SMState.ALIGN_DX
                return self._inactive_result()

            d_angle = _clamp(
                heading_error,
                -self.config.max_d_angle_deg,
                self.config.max_d_angle_deg,
            )
            return self._active_result(0.0, 0.0, d_angle, True)

        if self.state == SMState.PUSHING:
            distance = math.sqrt(
                (inputs.odom_x - self._push_start_x) ** 2
                + (inputs.odom_y - self._push_start_y) ** 2
            )
            if distance >= self.config.push_distance_m:
                self.state = SMState.RETURNING
                return self._inactive_result()

            dx_body = 0.0
            if observation is not None:
                x_error = observation.x - self.config.target_x_px
                dx_body = _clamp(
                    x_error * self.config.push_dx_kp,
                    -self.config.max_dx_m,
                    self.config.max_dx_m,
                )

            heading_error = normalize_angle(
                self.config.push_angle_deg - inputs.heading_deg
            )
            d_angle = _clamp(
                heading_error,
                -self.config.max_d_angle_deg,
                self.config.max_d_angle_deg,
            )
            return self._active_result(dx_body, self.config.push_dy_m, d_angle, False)

        if self.state == SMState.RETURNING:
            return_angle = normalize_angle(self.config.push_angle_deg + 180.0)
            heading_error = normalize_angle(return_angle - inputs.heading_deg)
            if abs(heading_error) <= self.config.heading_tolerance_deg:
                self.state = SMState.DONE
                self._done_since_ms = inputs.now_ms
                return self._inactive_result()

            d_angle = _clamp(
                heading_error,
                -self.config.max_d_angle_deg,
                self.config.max_d_angle_deg,
            )
            return self._active_result(0.0, 0.0, d_angle, False)

        if self.state == SMState.DONE:
            if inputs.now_ms - self._done_since_ms >= self.config.done_hold_ms:
                self.state = SMState.IDLE
            return self._inactive_result()

        self.state = SMState.IDLE
        return self._inactive_result()
