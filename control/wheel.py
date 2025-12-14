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
    """
    构造轮子状态

    :param name: 轮子名称
    :param encoder_obj: 编码器对象
    :param motor_obj: 电机对象
    :param tick_ms: 采样周期（毫秒）
    :param long_window: 长窗口大小
    :param short_window: 短窗口大小
    :param pid_controller: PID 控制器对象（可选）
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
