"""@file ident_tools.py
@brief 系统辨识工具模块

提供环形缓冲区管理、阶跃响应采样和一阶系统参数(增益与时间常数)辨识
"""
import math
from array import array


def create_ident_buffers(names, max_samples):
    """@brief 创建用于辨识的环形缓冲区

    为每个轮子预分配固定大小的时间和速度数组, 支持环形覆盖写入

    @param names 轮子名称列表, 如 ['m', 'l', 'r']
    @param max_samples 单个缓冲区的最大样本数, 超过此数后将覆盖旧数据
    @return 字典, 格式 {轮子名: {"t": 时间数组, "v": 速度数组, "count": 总写入数}}
    """
    return {
        name: {
            "t": array("f", [0.0] * max_samples),
            "v": array("f", [0.0] * max_samples),
            "count": 0,
        }
        for name in names
    }


def push_ident_sample(name, t_ms, val, buf, max_samples=None):
    """@brief 向环形缓冲区添加一个采样点

    采用模运算实现环形覆盖, count 计数器可超过 max_samples,
    用于判断缓冲区是否已满且计算起始位置

    @param name 轮子名称
    @param t_ms 时间戳, 单位毫秒
    @param val 该时刻的速度值或其他观测量
    @param buf 缓冲区字典, 由 create_ident_buffers() 创建
    @param max_samples 缓冲区大小, 若为 None 则从 buf 推断
    """
    slot = buf[name]
    size = max_samples or len(slot["t"])
    idx = slot["count"] % size
    slot["t"][idx] = t_ms
    slot["v"][idx] = val
    slot["count"] += 1


def get_ident_samples(name, buf, max_samples=None):
    """@brief 从缓冲区读取所有有效采样点, 按时间顺序排列

    处理环形缓冲区的起始位置计算, 确保返回的样本按采集时间顺序排列

    @param name 轮子名称
    @param buf 缓冲区字典
    @param max_samples 缓冲区大小
    @return 列表, 格式 [(时间戳_ms, 速度值), ...], 若缓冲区为空返回空列表
    """
    slot = buf[name]
    size = max_samples or len(slot["t"])
    n = min(slot["count"], size)
    if n == 0:
        return []
    start = (slot["count"] - n) % max_samples
    samples = []
    for i in range(n):
        idx = (start + i) % max_samples
        samples.append((slot["t"][idx], slot["v"][idx]))
    return samples


def identify_wheel(samples, step_duty):
    """@brief 从阶跃响应曲线辨识轮子的一阶系统参数

    使用稳态值计算增益, 通过 63% 幅度时间或对数线性拟合计算时间常数
    设系统响应为 y(t) = K*(1 - exp(-t/tau)), 其中 K 为增益, tau 为时间常数

    @details
    增益计算: 取尾部 40 个样本平均作为稳态值, gain = steady / step_duty
    时间常数计算:
    - 一级策略: 直接查找到达 63.2% 稳态值的时间
    - 备选策略: 对 ln(1 - y/steady) 与时间进行线性回归
    - 返回最小值为 0.001s 或 0.01s 的结果, 避免过小值

    @param samples 采样列表, 格式 [(时间_ms, 速度值), ...], 应为阶跃输入后的响应
    @param step_duty 阶跃输入的占空比值, 用于计算增益; 若为 0 则返回 (None, None)
    @return 元组 (gain, tau), 单位为增益(速度/占空比)和秒; 若辨识失败返回 (None, None)
    """
    if not samples or step_duty == 0:
        return None, None

    # 稳态值采用尾部 40 个样本平均, 使得结果对最后阶段的波动更敏感
    tail = samples[-min(len(samples), 40) : ]
    steady = sum(val for _, val in tail) / len(tail)
    gain = steady / step_duty if step_duty != 0 else 0.0
    if gain <= 0:
        return None, None

    # 寻找 63.2% 幅度点以直接计算时间常数
    target63 = steady * 0.632
    t0 = samples[0][0]
    tau = None

    for t_ms, val in samples:
        if val >= target63:
            tau = max((t_ms - t0) / 1000.0, 0.01)
            break

    # 若直接法无法找到 63% 点, 使用对数线性拟合
    if tau is None:
        xs = []
        zs = []
        for t_ms, val in samples:
            if val < steady and steady > 1e-6:
                x = (t_ms - t0) / 1000.0
                r = 1.0 - val / steady
                if r > 0.0:
                    xs.append(x)
                    zs.append(math.log(r))
        if xs:
            num = sum(x * z for x, z in zip(xs, zs))
            den = sum(x * x for x in xs)
            if den > 0 and num < 0:
                tau_est = -den / num
                tau = max(tau_est, 0.001)

    if tau is None:
        return None, None
    return gain, tau
