"""主车参数辨识脚本.

@file src/master/script/pid_identify.py
"""

from array import array
import gc
import math

TARGET_WHEELS = ("m", "l", "r")
IDENT_TICK_MS = 5
MAX_DUTY = 10000
IDENT_STEP_DUTY = 5000
IDENT_DURATION_MS = 4000
IDENT_MAX_SAMPLES = 600
IDENT_RESULTS_FILE = "/flash/ident_params.txt"
LEGACY_ENCODER_PINS = {
    "m": ("D15", "D16", True),
    "l": ("C2", "C3", True),
    "r": ("C0", "C1", True),
}
LEGACY_MOTOR_PORTS = {
    "m": ("PWM_C30_DIR_C31", False),
    "l": ("PWM_D6_DIR_D7", True),
    "r": ("PWM_D4_DIR_D5", False),
}


class LowPassFilter:
    def __init__(self, alpha=0.3, initial=None):
        self.alpha = float(alpha)
        self.state = initial

    def update(self, new_val):
        value = float(new_val)
        if self.state is None:
            self.state = value
        else:
            self.state = ((1.0 - self.alpha) * float(self.state)) + (self.alpha * value)
        return float(self.state)


class DualWindowRegressionFilter:
    def __init__(self, tick_ms=10, long_window=30, short_window=8, combine_w=0.65):
        self.tick_ms = int(tick_ms)
        self.long_window = int(long_window)
        self.short_window = int(short_window)
        self.combine_w = float(combine_w)
        self.sample_idx = 0
        self.vals = [0.0] * self.long_window
        self.stamps = [0.0] * self.long_window
        self.idx = 0
        self.count = 0
        self.sum_t = 0.0
        self.sum_t2 = 0.0
        self.sum_y = 0.0
        self.sum_ty = 0.0
        self.s_vals = [0.0] * self.short_window
        self.s_stamps = [0.0] * self.short_window
        self.s_idx = 0
        self.s_count = 0
        self.s_sum_t = 0.0
        self.s_sum_t2 = 0.0
        self.s_sum_y = 0.0
        self.s_sum_ty = 0.0

    def _update_window(
        self,
        value,
        t_ms,
        buf,
        tbuf,
        idx,
        count,
        sum_t,
        sum_t2,
        sum_y,
        sum_ty,
        max_len,
    ):
        if count < max_len:
            buf[count] = value
            tbuf[count] = t_ms
            sum_t += t_ms
            sum_t2 += t_ms * t_ms
            sum_y += value
            sum_ty += value * t_ms
            count += 1
        else:
            old = buf[idx]
            old_t = tbuf[idx]
            sum_t -= old_t
            sum_t2 -= old_t * old_t
            sum_y -= old
            sum_ty -= old * old_t
            buf[idx] = value
            tbuf[idx] = t_ms
            sum_t += t_ms
            sum_t2 += t_ms * t_ms
            sum_y += value
            sum_ty += value * t_ms
            idx = (idx + 1) % max_len
        return idx, count, sum_t, sum_t2, sum_y, sum_ty

    @staticmethod
    def _regression(count, sum_t, sum_t2, sum_y, sum_ty):
        denom = count * sum_t2 - sum_t * sum_t
        if denom != 0:
            slope = (count * sum_ty - sum_t * sum_y) / denom
            intercept = (sum_y - slope * sum_t) / count
        else:
            slope = 0.0
            intercept = 0.0
        return slope, intercept

    def update(self, raw_value):
        value = float(raw_value)
        t_ms = self.sample_idx * self.tick_ms
        self.sample_idx += 1
        self.idx, self.count, self.sum_t, self.sum_t2, self.sum_y, self.sum_ty = (
            self._update_window(
                value,
                t_ms,
                self.vals,
                self.stamps,
                self.idx,
                self.count,
                self.sum_t,
                self.sum_t2,
                self.sum_y,
                self.sum_ty,
                self.long_window,
            )
        )
        (
            self.s_idx,
            self.s_count,
            self.s_sum_t,
            self.s_sum_t2,
            self.s_sum_y,
            self.s_sum_ty,
        ) = self._update_window(
            value,
            t_ms,
            self.s_vals,
            self.s_stamps,
            self.s_idx,
            self.s_count,
            self.s_sum_t,
            self.s_sum_t2,
            self.s_sum_y,
            self.s_sum_ty,
            self.short_window,
        )
        slope_long, intercept_long = self._regression(
            self.count, self.sum_t, self.sum_t2, self.sum_y, self.sum_ty
        )
        slope_short, intercept_short = self._regression(
            self.s_count,
            self.s_sum_t,
            self.s_sum_t2,
            self.s_sum_y,
            self.s_sum_ty,
        )
        if self.s_count < 2:
            slope_short, intercept_short = slope_long, intercept_long
        next_t = (self.sample_idx + 1) * self.tick_ms
        pred_long = slope_long * next_t + intercept_long
        pred_short = slope_short * next_t + intercept_short
        fused_speed = pred_short * self.combine_w + pred_long * (1.0 - self.combine_w)
        fused_slope = slope_short * self.combine_w + slope_long * (1.0 - self.combine_w)
        accel = fused_slope * 1000.0
        return fused_speed, accel, fused_slope


def _read_board_drivers():
    from machine import Pin
    from seekfree import MOTOR_CONTROLLER
    from smartcar import encoder, ticker

    return {
        "Pin": Pin,
        "MOTOR_CONTROLLER": MOTOR_CONTROLLER,
        "encoder": encoder,
        "ticker": ticker,
    }


def build_ident_encoder_bundle(drivers):
    encoder_factory = drivers["encoder"]
    bundle = {}
    for name in TARGET_WHEELS:
        phase_a_pin, phase_b_pin, invert = LEGACY_ENCODER_PINS[name]
        bundle[name] = encoder_factory(phase_a_pin, phase_b_pin, invert)
    return bundle


def build_ident_motor_bundle(drivers):
    motor_controller = drivers["MOTOR_CONTROLLER"]
    bundle = {}
    for name in TARGET_WHEELS:
        port_name, invert = LEGACY_MOTOR_PORTS[name]
        bundle[name] = motor_controller(
            getattr(motor_controller, port_name),
            13000,
            duty=0,
            invert=invert,
        )
    return bundle


def build_ident_status_led(drivers):
    pin = drivers["Pin"]
    return pin("C4", pin.OUT, value=True)


def build_ident_stop_switch(drivers):
    pin = drivers["Pin"]
    return pin("D9", pin.IN, pull=pin.PULL_UP_47K)


def build_ident_filter_bank(tick_ms, wheel_names=TARGET_WHEELS):
    bank = {}
    for name in tuple(wheel_names):
        bank[str(name)] = {
            "input_lpf": LowPassFilter(alpha=0.5),
            "dual_filter": DualWindowRegressionFilter(
                tick_ms=int(tick_ms),
                long_window=30,
                short_window=8,
                combine_w=0.65,
            ),
            "output_lpf": LowPassFilter(alpha=0.9),
        }
    return bank


def filter_ident_speed(filter_state, raw_ticks):
    smooth_raw = filter_state["input_lpf"].update(float(raw_ticks))
    fused_speed, _, _ = filter_state["dual_filter"].update(smooth_raw)
    filtered_speed = filter_state["output_lpf"].update(float(fused_speed))
    return float(filtered_speed) / 3.0


def create_ident_buffers(names, max_samples):
    return {
        str(name): {
            "t": array("f", [0.0] * int(max_samples)),
            "v": array("f", [0.0] * int(max_samples)),
            "count": 0,
        }
        for name in tuple(names)
    }


def push_ident_sample(name, t_ms, value, buffers, max_samples=None):
    slot = buffers[str(name)]
    size = int(max_samples or len(slot["t"]))
    index = int(slot["count"]) % size
    slot["t"][index] = float(t_ms)
    slot["v"][index] = float(value)
    slot["count"] += 1


def identify_wheel_from_buffer(name, buffers, step_duty, max_samples=None):
    if float(step_duty) == 0.0:
        return (None, None)
    slot = buffers[str(name)]
    size = int(max_samples or len(slot["t"]))
    count = min(int(slot["count"]), size)
    if count <= 0:
        return (None, None)
    start = (int(slot["count"]) - count) % size
    tail_count = min(count, 40)
    steady_total = 0.0
    for offset in range(count - tail_count, count):
        index = (start + offset) % size
        steady_total += float(slot["v"][index])
    steady = steady_total / float(tail_count)
    gain = steady / float(step_duty)
    if gain <= 0.0:
        return (None, None)
    start_t_ms = float(slot["t"][start])
    target63 = steady * 0.632
    tau = None
    for offset in range(count):
        index = (start + offset) % size
        t_ms = float(slot["t"][index])
        value = float(slot["v"][index])
        if value >= target63:
            tau = max((t_ms - start_t_ms) / 1000.0, 0.01)
            break
    if tau is None:
        numerator = 0.0
        denominator = 0.0
        for offset in range(count):
            index = (start + offset) % size
            t_ms = float(slot["t"][index])
            value = float(slot["v"][index])
            if value >= steady or steady <= 1e-6:
                continue
            x = (t_ms - start_t_ms) / 1000.0
            ratio = 1.0 - (value / steady)
            if ratio <= 0.0:
                continue
            numerator += x * math.log(ratio)
            denominator += x * x
        if denominator > 0.0 and numerator < 0.0:
            tau = max(-denominator / numerator, 0.001)
    if tau is None:
        return (None, None)
    return (float(gain), float(tau))


def summarize_ident_buffer(name, buffers, max_samples=None, preview_count=5):
    slot = buffers[str(name)]
    size = int(max_samples or len(slot["t"]))
    count = min(int(slot["count"]), size)
    if count <= 0:
        return {
            "count": 0,
            "first": (),
            "last": (),
            "min": None,
            "max": None,
            "tail_avg": None,
        }
    start = (int(slot["count"]) - count) % size
    preview = max(1, int(preview_count))
    first = []
    last = []
    min_value = None
    max_value = None
    tail_count = min(count, 40)
    tail_values = [0.0] * tail_count
    tail_sum = 0.0
    for offset in range(count):
        index = (start + offset) % size
        sample = (float(slot["t"][index]), float(slot["v"][index]))
        value = sample[1]
        if min_value is None or value < min_value:
            min_value = value
        if max_value is None or value > max_value:
            max_value = value
        if offset < preview:
            first.append(sample)
        if offset >= (count - preview):
            last.append(sample)
        if tail_count > 0:
            tail_index = offset % tail_count
            if offset >= tail_count:
                tail_sum -= tail_values[tail_index]
            tail_values[tail_index] = value
            tail_sum += value
    tail_avg = tail_sum / float(tail_count)
    return {
        "count": int(count),
        "first": tuple(first),
        "last": tuple(last),
        "min": min_value,
        "max": max_value,
        "tail_avg": float(tail_avg),
    }


def _format_sample_preview(samples):
    if not samples:
        return "[]"
    return (
        "["
        + ", ".join("(%.1f,%.3f)" % (sample[0], sample[1]) for sample in samples)
        + "]"
    )


def print_ident_failure_debug(name, buffers, max_samples=None):
    summary = summarize_ident_buffer(
        name, buffers, max_samples=max_samples, preview_count=5
    )
    print(
        "%s debug count=%d min=%s max=%s tail_avg=%s"
        % (
            str(name),
            int(summary["count"]),
            str(summary["min"]),
            str(summary["max"]),
            str(summary["tail_avg"]),
        )
    )
    print("%s first=%s" % (str(name), _format_sample_preview(summary["first"])))
    print("%s last=%s" % (str(name), _format_sample_preview(summary["last"])))


def format_ident_text(results):
    lines = []
    for name in TARGET_WHEELS:
        gain_tau = dict(results).get(name)
        if gain_tau is None:
            continue
        gain, tau = gain_tau
        if gain is None or tau is None:
            continue
        lines.append("%s %.6f %.6f" % (name, float(gain), float(tau)))
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _save_ident_text(results, file_path):
    text = format_ident_text(results)
    if not text:
        raise RuntimeError("参数辨识失败，未生成有效结果")
    with open(file_path, "w") as handle:
        handle.write(text)
    return text


def _set_motor_duty(motors, duty):
    duty_value = max(-MAX_DUTY, min(MAX_DUTY, int(duty)))
    for name in TARGET_WHEELS:
        motors[name].duty(duty_value)


def _stop_motors(motors):
    for name in TARGET_WHEELS:
        motors[name].duty(0)


def _progress_step(sample_count):
    return max(1, int(sample_count) // 10)


def resolve_ident_plan(duration_ms, tick_ms):
    sample_count = max(1, (int(duration_ms) + int(tick_ms) - 1) // int(tick_ms))
    return {
        "duration_ms": int(duration_ms),
        "sample_count": int(sample_count),
        "buffer_samples": int(min(int(sample_count) + 10, IDENT_MAX_SAMPLES)),
    }


def main(
    duration_ms=IDENT_DURATION_MS,
    step_duty=IDENT_STEP_DUTY,
    tick_ms=IDENT_TICK_MS,
    file_path=IDENT_RESULTS_FILE,
):
    drivers = _read_board_drivers()
    ident_plan = resolve_ident_plan(duration_ms=duration_ms, tick_ms=tick_ms)
    sample_count = int(ident_plan["sample_count"])
    max_samples = int(ident_plan["buffer_samples"])
    encoders = build_ident_encoder_bundle(drivers)
    motors = build_ident_motor_bundle(drivers)
    led = build_ident_status_led(drivers)
    stop_switch = build_ident_stop_switch(drivers)
    stop_switch_state = stop_switch.value()
    ident_filter_bank = build_ident_filter_bank(
        tick_ms=tick_ms, wheel_names=TARGET_WHEELS
    )
    ident_buffers = create_ident_buffers(TARGET_WHEELS, max_samples)
    capture_ready = {"flag": False}
    pit = drivers["ticker"](1)
    pit.capture_list(*tuple(encoders[name] for name in TARGET_WHEELS))
    pit.callback(lambda _ticker_obj: capture_ready.__setitem__("flag", True))

    print("开始主车电机参数辨识，请保持车辆悬空且避免接触障碍物")
    print(
        "tick_ms=%d duration_ms=%d step_duty=%d sample_count=%d buffer_samples=%d"
        % (
            int(tick_ms),
            int(ident_plan["duration_ms"]),
            int(step_duty),
            int(sample_count),
            int(max_samples),
        )
    )

    pit.start(int(tick_ms))
    tick_count = 0
    try:
        while True:
            if capture_ready["flag"]:
                capture_ready["flag"] = False
                tick_count += 1
                led.toggle()
                _set_motor_duty(motors, step_duty)
                t_ms = int(tick_count) * int(tick_ms)
                for name in TARGET_WHEELS:
                    filtered_speed = filter_ident_speed(
                        ident_filter_bank[name], encoders[name].get()
                    )
                    push_ident_sample(
                        name,
                        t_ms,
                        filtered_speed,
                        ident_buffers,
                        max_samples=max_samples,
                    )
                if tick_count == 1 or (tick_count % _progress_step(sample_count) == 0):
                    print("progress=%d/%d" % (int(tick_count), int(sample_count)))
                if tick_count >= sample_count:
                    break
            if stop_switch.value() != stop_switch_state:
                print("stop")
                return "stop"
            gc.collect()
    finally:
        pit.stop()
        _stop_motors(motors)

    results = {}
    for name in TARGET_WHEELS:
        results[name] = identify_wheel_from_buffer(
            name,
            ident_buffers,
            step_duty,
            max_samples=max_samples,
        )
        gain, tau = results[name]
        print("%s gain=%s tau=%s" % (name, str(gain), str(tau)))
        if gain is None or tau is None:
            print_ident_failure_debug(name, ident_buffers, max_samples=max_samples)

    text = _save_ident_text(results, file_path=file_path)
    print("saved=%s" % str(file_path))
    print(text, end="")
    return text


if __name__ == "__main__":
    main()
