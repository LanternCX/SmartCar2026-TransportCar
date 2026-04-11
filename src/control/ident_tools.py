"""系统辨识工具模块.

提供缓冲区创建、样本采集和一阶系统增益与时间常数的辨识.
"""
import math
from array import array
 


def create_ident_buffers(names, max_samples):
    """创建用于辨识的环形缓冲区.
    
    参数:
        names: 轮子名称列表.
        max_samples: 最大样本数.
    
    返回:
        字典,为每个轮子创建时间和速度数组及计数器.
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
    """向环形缓冲区添加采样点.
    
    参数:
        name: 轮子名称.
        t_ms: 时间戳(毫秒).
        val: 速度值.
        buf: 缓冲区字典.
        max_samples: 缓冲区大小(若为 None,则从 buf 推断).
    
    副作用:
        修改缓冲区内容和计数.
    """
    slot = buf[name]
    size = max_samples or len(slot["t"])
    idx = slot["count"] % size
    slot["t"][idx] = t_ms
    slot["v"][idx] = val
    slot["count"] += 1


def get_ident_samples(name, buf, max_samples=None):
    """从缓冲区读取所有采样点(有序).
    
    参数:
        name: 轮子名称.
        buf: 缓冲区字典.
        max_samples: 缓冲区大小.
    
    返回:
        列表 [(时间戳, 速度值), ...],按时间顺序排列.
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
    """从阶跃响应曲线辨识轮子的一阶系统参数.
    
    使用尾部稳态值计算增益,并通过时间常数定义(63%上升点或对数线性拟合)
    计算时间常数.
    
    参数:
        samples: 列表 [(时间_ms, 速度值), ...].
        step_duty: 阶跃输入的占空比值.
    
    返回:
        元组 (gain, tau);若计算失败,返回 (None, None).
    """
    if not samples or step_duty == 0:
        return None, None

    # 计算稳态值(使用最后 40 个样本的平均)
    tail = samples[-min(len(samples), 40) :]
    steady = sum(val for _, val in tail) / len(tail)
    gain = steady / step_duty if step_duty != 0 else 0.0
    if gain <= 0:
        return None, None

    # 时间常数:63% 稳态值上升时间
    target63 = steady * 0.632
    t0 = samples[0][0]
    tau = None

    for t_ms, val in samples:
        if val >= target63:
            tau = max((t_ms - t0) / 1000.0, 0.01)
            break

    # 若直接法失败,使用对数线性拟合
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
