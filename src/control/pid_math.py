"""@file pid_math.py
@brief PID 数学工具函数

提供硬度因子查询、数值限幅、系统辨识参数到 PI 增益转换,
以及控制器状态重置等工具函数
"""


def hardness_factor(name):
    """@brief 根据硬度级别返回相应的调谐时间常数因子

    用于根据期望的控制器响应硬度(快速响应 vs 平缓响应)调整时间常数,
    从而影响最终的 PI 增益

    @param name 硬度级别名称, 取值
               - "soft": 返回 4.0, 最缓和的响应
               - "hard": 返回 1.0, 标准响应
               - "hard2": 返回 0.5, 较快响应
               - "hard3": 返回 0.05, 最快响应
               - 其他: 返回 2.0, 中等响应
    @return 对应的调谐因子, 为正浮点数
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
    """@brief 将值限制在指定范围内

    确保值不超出给定的上下界, 常用于输出限幅或参数边界控制

    @param val 待限制的值
    @param lo 下界(含), 下限值
    @param hi 上界(含), 上限值
    @return 限制后的值, 范围为 [lo, hi]
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
    """@brief 从辨识的一阶系统参数计算 PI 增益

    使用系统辨识得到的模型参数(增益 K、时间常数 tau)和调谐硬度,
    通过参数化公式计算出合适的比例(kp)和积分(ki)增益

    @details
    模型假设: G(s) = K / (tau*s + 1), 在单位反馈控制下
    设 lambda = tau * hardness_factor(hardness_name), 则:
    - kp = (tau / (gain * lambda)) * gain_boost
    - ki = (1.0 / (gain * lambda)) * gain_boost

    增益会被限制在 [0, kp_max] 和 [0, ki_max] 范围内

    @param gain 系统增益, 单位为速度/占空比, 从系统辨识得出
    @param tau 系统时间常数, 单位秒, 从系统辨识得出
    @param hardness_name 调谐硬度级别名称, 传给 hardness_factor()
    @param kp_max 比例增益的上限, 用于防止过度调谐
    @param ki_max 积分增益的上限, 用于防止积分速度过快
    @param gain_boost 增益提升因子, 用于整体放大或缩小计算结果(通常为 1.0 或根据应用调整)
    @return 元组 (kp, ki), 分别为比例和积分增益, 单位与输入参数一致
    """
    lam = tau * hardness_factor(hardness_name)
    kp = (tau / (gain * lam)) * gain_boost
    ki = (1.0 / (gain * lam)) * gain_boost
    return clamp(kp, 0.0, kp_max), clamp(ki, 0.0, ki_max)


def reset_pi_state(states):
    """@brief 重置所有轮子的 PID 控制器和占空比

    在控制模式切换、重新初始化或故障恢复时调用, 清空每个轮子的
    控制器状态和输出指令

    @param states 轮子状态字典列表, 每个字典应包含 "controller" 字段(PID 对象)
                 和 "duty" 字段(浮点数, 占空比命令)
    """
    for state in states:
        controller = state.get("controller")
        if controller:
            controller.reset()
        state["duty"] = 0.0
