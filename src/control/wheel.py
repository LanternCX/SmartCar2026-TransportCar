"""@file wheel.py
@brief 车轮状态构造工厂函数

提供构建单个轮子完整状态字典的工厂函数, 集成编码器、电机、滤波器和 PID 控制器
"""
from filters.dual_window_regression_filter import DualWindowRegressionFilter
from filters.lowpass_filter import LowPassFilter
from control.pid_controller import IncrementalPIDController


def build_wheel_state(
    name,
    encoder_obj,
    motor_obj,
    tick_ms,
    long_window,
    short_window,
    pid_controller=None,
):
    """@brief 构造单个轮子的状态字典

    集合编码器、电机、滤波器、PID 控制器等组件到一个统一状态对象,
    便于在控制主循环中统一管理和更新

    @param name 轮子名称, 取值为 "m"(中间)、"l"(左)或 "r"(右)
    @param encoder_obj 编码器对象, 支持 .get() 方法获取当前累计脉冲数
    @param motor_obj 电机对象, 支持 .duty(pwm) 方法设置占空比输出(范围 -1.0 ~ 1.0)
    @param tick_ms 采样周期, 单位毫秒, 用于滤波器和速度计算的时基
    @param long_window 长窗口大小, 单位采样次数, 用于低频速度估计
    @param short_window 短窗口大小, 单位采样次数, 用于高频速度估计
    @param pid_controller PID 控制器对象(可选); 若为 None 则默认创建增量式 PID
    @return 字典, 包含以下字段
            - name: 轮子名称
            - encoder: 编码器对象, 提供脉冲数读取
            - motor: 电机对象, 用于占空比控制
            - dual_filter: 双窗口回归滤波器, 支持快速/慢速速度切换
            - input_lpf: 输入低通滤波(目标速度), alpha=0.5
            - output_lpf: 输出低通滤波(实际速度), alpha=0.9
            - raw_speed: 原始速度估计(脉冲/采样周期)
            - filtered_speed: 滤波后的速度
            - duty: 当前占空比命令(范围 -1.0 ~ 1.0)
            - controller: PID 控制器对象
            - id_gain: 辨识参数: 系统增益(速度/占空比), 初值 None
            - id_tau: 辨识参数: 系统时间常数(秒), 初值 None
    """
    controller = pid_controller or IncrementalPIDController()
    return {
        "name": name,
        "encoder": encoder_obj,
        "motor": motor_obj,
        "dual_filter": DualWindowRegressionFilter(
            tick_ms=tick_ms,
            long_window=long_window,
            short_window=short_window,
            combine_w=0.65,
        ),
        "input_lpf": LowPassFilter(alpha=0.5),
        "output_lpf": LowPassFilter(alpha=0.9),
        "raw_speed": 0.0,
        "filtered_speed": 0.0,
        "duty": 0.0,
        "controller": controller,
        "id_gain": None,
        "id_tau": None,
    }
