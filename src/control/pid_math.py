"""PID 数学工具函数."""
 


def hardness_factor(name):
    """根据硬度级别返回相应的调谐因子.
    
    参数:
        name: 硬度级别名称("soft", "hard", "hard2", "hard3" 或其他).
    
    返回:
        对应的因子值("soft" -> 4.0, "hard" -> 1.0, 等).
    """
    if name == "soft":
        return 4.0
    if name == "hard":
        return 1.0
    if name == "hard2":
        return 0.5
    if name == "hard3":
        return 0.05
    return 2.0


def clamp(val, lo, hi):
    """将值限制在指定范围内.
    
    参数:
        val: 待限制的值.
        lo: 下界(含).
        hi: 上界(含).
    
    返回:
        限制后的值.
    """
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val


def compute_pi_from_id(
    gain,
    tau,
    hardness_name,
    kp_max,
    ki_max,
    gain_boost,
):
    """从辨识的一阶系统参数计算 PI 增益.
    
    使用模型参数(增益、时间常数)通过硬度因子计算出合适的比例和积分增益.
    
    参数:
        gain: 系统增益(速度/占空比).
        tau: 系统时间常数(秒).
        hardness_name: 调谐硬度级别.
        kp_max: 比例增益的上限.
        ki_max: 积分增益的上限.
        gain_boost: 增益提升因子.
    
    返回:
        元组 (kp, ki).
    """
    lam = tau * hardness_factor(hardness_name)
    kp = (tau / (gain * lam)) * gain_boost
    ki = (1.0 / (gain * lam)) * gain_boost
    return clamp(kp, 0.0, kp_max), clamp(ki, 0.0, ki_max)


def reset_pi_state(states):
    """重置所有轮子的 PID 控制器和占空比.
    
    参数:
        states: 轮子状态字典列表.
    
    副作用:
        修改每个 state 的 controller 内部状态和 duty 值.
    """
    for state in states:
        controller = state.get("controller")
        if controller:
            controller.reset()
        state["duty"] = 0.0
