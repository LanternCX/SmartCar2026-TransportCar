"""reset 系统复位指令处理器:不受 command_lock 影响."""

from services.command_router import router
from control.pid_math import reset_pi_state


@router.command("reset")
def handle(ctx, value):
    """
    全量系统复位:里程计、姿态、滤波器、PID 积分、锁定状态、暂存位移.

    本命令不受 command_lock 限制,可随时执行.

    参数:
        ctx:   TransportCar 实例.
        value: 忽略(兼容路由器接口,reset 无需数值).
    """
    ctx.odometry.reset()
    ctx.heading_est = 0.0
    ctx.heading_target = 0.0
    ctx.yaw_pid.reset()
    ctx.yaw_integral = 0.0
    ctx.q_est.w, ctx.q_est.x, ctx.q_est.y, ctx.q_est.z = 1.0, 0.0, 0.0, 0.0
    ctx.last_yaw_rad = 0.0
    ctx.gyro_lpf.reset(0.0)
    reset_pi_state(ctx.wheel_states)
    ctx.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    ctx.command_lock = False
    ctx.command_mode = "none"
    ctx._pending_lock = None
    ctx._pending_dx = None
    ctx._pending_dy = None
    ctx._pending_d_angle = None
    if hasattr(ctx, "vision_protocol"):
        ctx.vision_protocol.clear()
    if hasattr(ctx, "vision_state_machine"):
        ctx.vision_state_machine.reset()
    if hasattr(ctx, "_vision_step_result"):
        ctx._vision_step_result = None
    if hasattr(ctx, "_vision_resolved_target"):
        ctx._vision_resolved_target = None
