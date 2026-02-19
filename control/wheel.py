"""车轮状态构造工厂函数."""
from filters.dual_window_regression_filter import DualWindowRegressionFilter
from filters.lowpass_filter import LowPassFilter
from control.pid_controller import IncrementalPIDController
from typing import Dict, Any, Optional


def build_wheel_state(
    name: str,
    encoder_obj: Any,
    motor_obj: Any,
    tick_ms: int,
    long_window: int,
    short_window: int,
    pid_controller: Optional[Any] = None,
) -> Dict[str, Any]:
    """构造单个轮子的状态字典.
    
    集合编码器、电机、滤波器、PID 控制器等组件到一个统一状态对象,
    便于统一管理和更新.
    
    参数:
        name: 轮子名称("m"、"l" 或 "r").
        encoder_obj: 编码器对象,支持 .get() 方法获取当前脉冲数.
        motor_obj: 电机对象,支持 .duty(pwm) 方法设置占空比.
        tick_ms: 采样周期(毫秒).
        long_window: 长窗口大小(样本数).
        short_window: 短窗口大小(样本数).
        pid_controller: PID 控制器对象(可选;默认为增量式 PID).
    
    返回:
        字典,包含轮子名称、硬件接口、滤波器、PID 控制器及各类状态变量.
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
