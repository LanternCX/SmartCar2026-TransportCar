"""视觉状态机与相对控制意图转换."""

import math

from services.vision_protocol import VisionObservation
from services.vision_debug import build_transition_event
from services.vision_state_defs import SM, SMState
from services.vision_state_registry import vision_state_registry


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


class VisionStateConfig:
    """视觉状态机参数集合."""

    def __init__(
        self,
        target_center_x_px: float,
        target_bottom_px: float,
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

    def __init__(
        self,
        config: VisionStateConfig,
        initial_state=SM.IDLE,
        debug_sink=None,
    ):
        """初始化状态机运行时状态."""
        self.config = config
        coerced_state = vision_state_registry.coerce_state(initial_state)
        self.state = coerced_state if coerced_state is not None else SM.IDLE
        self._debug_sink = debug_sink
        self._stable_counter = 0
        self._push_start_x = 0.0
        self._push_start_y = 0.0
        self._done_since_ms = 0

    def _emit_debug_event(self, event) -> None:
        """输出结构化调试事件,失败时静默降级."""
        if self._debug_sink is None:
            return
        try:
            self._debug_sink(event)
        except Exception:
            pass

    def _build_debug_context(self, inputs, observation):
        """提取调试事件所需上下文."""
        observation_x = None
        observation_y = None
        heading_deg = None
        odom_x = None
        odom_y = None
        now_ms = None
        if observation is not None:
            observation_x = float(observation.center_x)
            observation_y = float(observation.bottom)
        if inputs is not None:
            heading_deg = float(inputs.heading_deg)
            odom_x = float(inputs.odom_x)
            odom_y = float(inputs.odom_y)
            now_ms = int(inputs.now_ms)
        return {
            "observation_x": observation_x,
            "observation_y": observation_y,
            "heading_deg": heading_deg,
            "odom_x": odom_x,
            "odom_y": odom_y,
            "now_ms": now_ms,
        }

    def _set_state(self, transition, inputs, observation) -> None:
        """切换状态并输出统一调试日志."""
        old_state = self.state
        self.state = transition.state
        if old_state == self.state:
            return
        self._emit_debug_event(
            build_transition_event(
                old_state=old_state,
                transition=transition,
                stable_counter=self._stable_counter,
                **self._build_debug_context(inputs, observation),
            )
        )

    def start_push(self, odom_x: float, odom_y: float) -> None:
        """记录推行阶段起点."""
        self._push_start_x = float(odom_x)
        self._push_start_y = float(odom_y)

    def reset(self) -> None:
        """重置状态机到空闲态."""
        self._set_state(SM.IDLE.RESET, None, None)
        self._stable_counter = 0
        self._push_start_x = 0.0
        self._push_start_y = 0.0
        self._done_since_ms = 0

    def _inactive_result(self) -> VisionStepResult:
        """生成空控制结果."""
        return VisionStepResult(
            int(self.state),
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
            int(self.state),
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

        # 对齐阶段依赖连续视觉观测,丢目标后立即退回空闲态
        if self.state in (SM.ALIGN_ANGLE, SM.ALIGN_DIST, SM.ALIGN_DX):
            if observation is None:
                self._set_state(SM.IDLE.OBSERVATION_LOST, inputs, observation)
                self._stable_counter = 0
                return self._inactive_result()

        # 空闲态只等待视觉目标出现,不主动输出控制量
        if self.state == SM.IDLE:
            self._stable_counter = 0
            if observation is None:
                return self._inactive_result()
            self._set_state(SM.ALIGN_ANGLE.OBSERVATION_ACQUIRED, inputs, observation)

        # 第一阶段先让目标落到图像中心附近,避免带着较大横向误差前进
        if self.state == SM.ALIGN_ANGLE:
            x_error = observation.center_x - self.config.target_center_x_px  # type: ignore[union-attr]
            if abs(x_error) <= self.config.angle_deadzone_px:
                # 只有连续多帧稳定进入死区才允许切到下一阶段,用于抑制视觉抖动
                self._stable_counter += 1
                if self._stable_counter >= self.config.stable_frames:
                    self._set_state(
                        SM.ALIGN_DIST.ANGLE_ALIGNED_STABLE, inputs, observation
                    )
                    self._stable_counter = 0
                return self._inactive_result()

            self._stable_counter = 0
            d_angle = _clamp(
                x_error * self.config.angle_kp,
                -self.config.max_d_angle_deg,
                self.config.max_d_angle_deg,
            )
            return self._active_result(0.0, 0.0, d_angle, False)

        # 第二阶段沿车体纵向微调距离,若横向误差重新变大则回到角度对齐
        if self.state == SM.ALIGN_DIST:
            x_error = observation.center_x - self.config.target_center_x_px  # type: ignore[union-attr]
            if abs(x_error) > self.config.angle_reentry_px:
                self._set_state(SM.ALIGN_ANGLE.ANGLE_ERROR_REENTRY, inputs, observation)
                self._stable_counter = 0
                return self._inactive_result()

            y_error = observation.bottom - self.config.target_bottom_px  # type: ignore[union-attr]
            if abs(y_error) <= self.config.dist_deadzone_px:
                # 距离稳定后再进入最终横移对齐,避免阶段切换过快
                self._stable_counter += 1
                if self._stable_counter >= self.config.stable_frames:
                    self._set_state(
                        SM.ALIGN_DX.DISTANCE_ALIGNED_STABLE, inputs, observation
                    )
                    self._stable_counter = 0
                return self._inactive_result()

            self._stable_counter = 0
            dy_body = _clamp(
                -y_error * self.config.dist_kp,
                -self.config.max_dy_m,
                self.config.max_dy_m,
            )
            return self._active_result(0.0, dy_body, 0.0, False)

        # 第三阶段处理最终横移误差,并决定是继续绕行还是进入推行
        if self.state == SM.ALIGN_DX:
            x_error = observation.center_x - self.config.target_center_x_px  # type: ignore[union-attr]
            if abs(x_error) <= self.config.dx_deadzone_px:
                self._stable_counter += 1
                if self._stable_counter >= self.config.stable_frames:
                    y_error = observation.bottom - self.config.target_bottom_px  # type: ignore[union-attr]
                    heading_error = normalize_angle(
                        self.config.push_angle_deg - inputs.heading_deg
                    )
                    self._stable_counter = 0
                    # 若距离再次偏离,说明前一阶段尚未真正完成,回退重新修正
                    if abs(y_error) > self.config.dist_deadzone_px:
                        self._set_state(
                            SM.ALIGN_DIST.DISTANCE_NOT_READY, inputs, observation
                        )
                    # 角度满足推行要求时直接进入推行态并记录里程计起点
                    elif abs(heading_error) <= self.config.heading_tolerance_deg:
                        self._set_state(SM.PUSHING.ENTER_PUSHING, inputs, observation)
                        self.start_push(inputs.odom_x, inputs.odom_y)
                    # 角度未满足要求时进入绕行态,仅通过转向继续修正
                    else:
                        self._set_state(
                            SM.ORBITING.HEADING_NOT_READY, inputs, observation
                        )
                return self._inactive_result()

            self._stable_counter = 0
            dx_body = _clamp(
                x_error * self.config.dx_kp,
                -self.config.max_dx_m,
                self.config.max_dx_m,
            )
            return self._active_result(dx_body, 0.0, 0.0, False)

        # 绕行态只关注推行朝向,朝向回正后交回横移阶段做最终确认
        if self.state == SM.ORBITING:
            heading_error = normalize_angle(
                self.config.push_angle_deg - inputs.heading_deg
            )
            if abs(heading_error) <= self.config.heading_tolerance_deg:
                self._set_state(SM.ALIGN_DX.HEADING_ALIGNED, inputs, observation)
                return self._inactive_result()

            d_angle = _clamp(
                heading_error,
                -self.config.max_d_angle_deg,
                self.config.max_d_angle_deg,
            )
            return self._active_result(0.0, 0.0, d_angle, True)

        # 推行态按照固定前进偏置推进,并在推进过程中保留少量横向纠偏
        if self.state == SM.PUSHING:
            distance = math.sqrt(
                (inputs.odom_x - self._push_start_x) ** 2
                + (inputs.odom_y - self._push_start_y) ** 2
            )
            # 推行距离达到阈值后切到返回态,后续不再继续前推
            if distance >= self.config.push_distance_m:
                self._set_state(SM.RETURNING.PUSH_DISTANCE_REACHED, inputs, observation)
                return self._inactive_result()

            dx_body = 0.0
            if observation is not None:
                # 推行时仍允许根据视觉横向误差做小幅修正,避免越推越偏
                x_error = observation.center_x - self.config.target_center_x_px
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

        # 返回态只负责把车头转到反向朝向,不再输出位移目标
        if self.state == SM.RETURNING:
            return_angle = normalize_angle(self.config.push_angle_deg + 180.0)
            heading_error = normalize_angle(return_angle - inputs.heading_deg)
            if abs(heading_error) <= self.config.heading_tolerance_deg:
                self._set_state(SM.DONE.RETURN_HEADING_REACHED, inputs, observation)
                self._done_since_ms = inputs.now_ms
                return self._inactive_result()

            d_angle = _clamp(
                heading_error,
                -self.config.max_d_angle_deg,
                self.config.max_d_angle_deg,
            )
            return self._active_result(0.0, 0.0, d_angle, False)

        # 完成态保持静止一小段时间,给外层留出状态观测窗口
        if self.state == SM.DONE:
            if inputs.now_ms - self._done_since_ms >= self.config.done_hold_ms:
                self._set_state(SM.IDLE.DONE_HOLD_ELAPSED, inputs, observation)
            return self._inactive_result()

        # 理论上不会走到这里,保底退回空闲态避免未知状态悬挂
        self._set_state(SM.IDLE.UNKNOWN_STATE_GUARD, inputs, observation)
        return self._inactive_result()
