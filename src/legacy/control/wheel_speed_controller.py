"""轮速滤波与速度环控制."""

from config.params import ACTIVE_WHEELS, TARGET_SPEED_MAX
from control.pid_math import clamp


class WheelSpeedController:
    """封装轮速滤波、逆运动学和电机占空比分配."""

    def __init__(self, kinematics):
        self.kinematics = kinematics

    def update_wheel_speeds(self, wheel_states):
        """读取编码器并执行既有多级滤波链."""
        for state in wheel_states:
            raw = float(state["encoder"].get())
            state["raw_speed"] = raw
            smooth_raw = state["input_lpf"].update(raw)
            smooth_raw = state["diff_filter"].update(smooth_raw)
            fused_speed, _, _ = state["dual_filter"].update(smooth_raw)
            state["filtered_speed"] = state["output_lpf"].update(fused_speed)

    def inverse_kinematics(self, vx, vy, omega):
        """保持旧版三轮逆解与限速语义."""
        vm, vl, vr = self.kinematics.inverse_kinematics(vx, vy, omega)
        max_speed = max(abs(vm), abs(vl), abs(vr))
        if max_speed > TARGET_SPEED_MAX and max_speed > 0.0:
            scale = TARGET_SPEED_MAX / max_speed
            vm *= scale
            vl *= scale
            vr *= scale
        return vm, vl, vr

    def apply_target_speeds(
        self,
        wheel_states,
        target_speeds,
        target_vx_cmd,
        target_vy_cmd,
        omega_cmd,
        dt_s,
        rear_only_mode,
    ):
        """执行逆解、rear only 分配和速度环输出."""
        vm, vl, vr = self.inverse_kinematics(
            target_vx_cmd,
            target_vy_cmd,
            float(omega_cmd),
        )

        if rear_only_mode:
            target_speeds["m"] = clamp(vm, -TARGET_SPEED_MAX, TARGET_SPEED_MAX) / 3.0
            target_speeds["l"] = 0.0
            target_speeds["r"] = 0.0
        else:
            target_speeds["m"] = clamp(vm, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)
            target_speeds["l"] = clamp(vl, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)
            target_speeds["r"] = clamp(vr, -TARGET_SPEED_MAX, TARGET_SPEED_MAX)

        for state in wheel_states:
            if state["name"] in ACTIVE_WHEELS:
                target = clamp(
                    target_speeds.get(state["name"], 0.0),
                    -TARGET_SPEED_MAX,
                    TARGET_SPEED_MAX,
                )
                duty_cmd = state["controller"].update(
                    target, state["filtered_speed"], dt_s
                )
                state["duty"] = duty_cmd
                state["motor"].duty(int(duty_cmd))
            else:
                state["controller"].reset()
                state["duty"] = 0.0
                state["motor"].duty(0)
