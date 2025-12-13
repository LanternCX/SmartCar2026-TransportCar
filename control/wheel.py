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
        "kp": 0.0,
        "ki": 0.0,
        "id_gain": None,
        "id_tau": None,
    }
