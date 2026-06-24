"""编码器计数探针脚本.

@file src/script/test/encoder_count_probe.py
@brief 手动旋转车轮时输出三路编码器增量与累计值
"""

import gc
import time


# 探针输出间隔, 单位毫秒
REPORT_INTERVAL_MS = 200
# 主循环空转等待时间, 单位毫秒
LOOP_SLEEP_MS = 1
# 编码器读取顺序
WHEEL_NAMES = ("m", "l", "r")


_tick_ready = False


def _mark_tick(_tick=None):  # noqa: F841
    """ticker 回调中只置位采样标志."""

    global _tick_ready
    _tick_ready = True


def _is_tick_ready():
    """读取采样标志."""

    return bool(_tick_ready)


def _clear_tick():
    """清除采样标志."""

    global _tick_ready
    _tick_ready = False


def _sleep_ms(delay_ms):
    """按毫秒延时."""

    sleep_ms = getattr(time, "sleep_ms", None)
    if sleep_ms is not None:
        sleep_ms(int(delay_ms))
        return
    time.sleep(float(delay_ms) / 1000.0)


def _ticks_ms():
    """读取毫秒计数."""

    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return ticks_ms()
    return int(time.time() * 1000)


def _ticks_diff(current, previous):
    """计算毫秒计数差值."""

    ticks_diff = getattr(time, "ticks_diff", None)
    if ticks_diff is not None:
        return ticks_diff(current, previous)
    return current - previous


def _collect():
    """触发一次垃圾回收."""

    gc.collect()


def _create_encoders():
    """按当前车号创建三路编码器."""

    from hardware.encoders import create_encoders
    from role.vehicle_role import read_vehicle_role

    return create_encoders(read_vehicle_role())


def _read_encoder_counts(encoders):
    """读取三路编码器当前增量."""

    return {
        name: int(encoders[name].get())
        for name in WHEEL_NAMES
    }


def _format_report(last_counts, totals):
    """格式化探针输出."""

    return (
        "enc m=%d l=%d r=%d total_m=%d total_l=%d total_r=%d"
        % (
            last_counts["m"],
            last_counts["l"],
            last_counts["r"],
            totals["m"],
            totals["l"],
            totals["r"],
        )
    )


def run_encoder_count_probe(
    encoders,
    tick_ready=_is_tick_ready,
    clear_tick=_clear_tick,
    now_ms=_ticks_ms,
    ticks_diff=_ticks_diff,
    sleep_ms=_sleep_ms,
    collect=_collect,
    print_fn=print,
    max_reports=None,
):
    """累计并输出三路编码器计数.

    @param encoders 三路编码器对象映射
    @param tick_ready 采样标志读取函数
    @param clear_tick 采样标志清除函数
    @param now_ms 当前毫秒计数读取函数
    @param ticks_diff 毫秒计数差值函数
    @param sleep_ms 毫秒延时函数
    @param collect 垃圾回收函数
    @param print_fn 输出函数
    @param max_reports 最大输出次数, None 表示持续运行
    """

    totals = {"m": 0, "l": 0, "r": 0}
    last_counts = {"m": 0, "l": 0, "r": 0}
    reports = 0
    last_report_ms = now_ms()

    while max_reports is None or reports < max_reports:
        if tick_ready():
            last_counts = _read_encoder_counts(encoders)
            for name in WHEEL_NAMES:
                totals[name] += last_counts[name]
            clear_tick()

        current_ms = now_ms()
        if ticks_diff(current_ms, last_report_ms) >= REPORT_INTERVAL_MS:
            print_fn(_format_report(last_counts, totals))
            last_report_ms = current_ms
            reports += 1

        collect()
        sleep_ms(LOOP_SLEEP_MS)


def main():
    """板端手动探针入口."""

    from smartcar import ticker
    from config import motion as motion_params

    encoders = _create_encoders()
    pit1 = ticker(1)
    pit1.capture_list(*[encoders[name] for name in WHEEL_NAMES])
    pit1.callback(_mark_tick)
    pit1.start(getattr(motion_params, "TICK_MS"))
    try:
        run_encoder_count_probe(encoders)
    finally:
        pit1.stop()


if __name__ == "__main__" and globals().get("__spec__") is None:
    main()
