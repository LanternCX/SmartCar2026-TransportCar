"""
@file cmd_reset.py
@brief reset 系统复位指令处理器, 全量硬重置, 不受 command_lock 影响
"""

from command.router import router
from control.pid_math import reset_pi_state


@router.command("reset")
def handle(ctx, value):
    """
    @brief 执行全量系统复位, 清零所有运动状态、估计器、控制器与暂存数据

    @details
    该命令不受 command_lock 限制, 可在任何运动状态下强制执行, 用于应急停机或
    初始化重启场景.清零顺序确保物理状态与逻辑状态的一致性:
    1. 里程计复位: 清零位置与速度积分状态
    2. 姿态估计复位: 角度、四元数、角速度LPF
    3. PID 控制器复位: 清零积分项与历史状态
    4. 速度指令复位: 初始化为零速度
    5. 锁定与模式复位: 退出锁定, 清除暂存模式切换标志

    @param ctx   TransportCar 实例
    @param value 忽略(兼容路由器接口签名, reset 无需参数值)

    @variables_reset
    - ctx.odometry: 位置与速度积分状态
    - ctx.heading_est, ctx.heading_target, ctx.yaw_integral: 姿态与目标
    - ctx.q_est: 四元数估计
    - ctx.wheel_states: 电机积分状态
    - ctx.last_cmd: 最后一条速度命令
    - ctx.command_lock, ctx.command_mode: 运动锁定与模式状态
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
