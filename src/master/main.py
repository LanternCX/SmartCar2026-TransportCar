"""主车启动入口

@file src/master/main.py
"""

_USE_DIRECT_IMPORTS = globals().get("__package__") in ("", None)


def run_calibrate_gyro():
    if _USE_DIRECT_IMPORTS:
        from script.calibrate_gyro import main
    else:
        from .script.calibrate_gyro import main

    return main()


def run_pid_identify():
    if _USE_DIRECT_IMPORTS:
        from script.pid_identify import main
    else:
        from .script.pid_identify import main

    return main()


def _read_button_state(pin_name):
    from machine import Pin

    return Pin(pin_name, Pin.IN, Pin.PULL_UP).value() == 0


def _read_now_ms():
    """读取当前毫秒时钟

    @brief 板端优先使用毫秒时钟, 主机侧回退到系统时间。
    """

    import time

    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


def _sleep_ms(delay_ms):
    import time

    sleep_ms = getattr(time, "sleep_ms", None)
    if sleep_ms is not None:
        sleep_ms(int(delay_ms))
        return
    time.sleep(float(delay_ms) / 1000.0)


def _control_tick_ms():
    if _USE_DIRECT_IMPORTS:
        import runtime_params
    else:
        from . import runtime_params

    return int(runtime_params.CONTROL_TICK_MS)


def _drive_loop(loop):
    """驱动运行循环

    @brief 正常运行分支持续推进主循环。
    """

    tick_ms = _control_tick_ms()
    next_tick_ms = None
    while True:
        now_ms = _read_now_ms()
        if next_tick_ms is not None:
            remaining_ms = int(next_tick_ms) - int(now_ms)
            if remaining_ms > 0:
                _sleep_ms(remaining_ms)
                continue
        loop.step(now_ms)
        next_tick_ms = int(now_ms) + tick_ms


def _start_runtime():
    if _USE_DIRECT_IMPORTS:
        from app import MasterRuntimeLoop, build_hw_bundle
    else:
        from .app import MasterRuntimeLoop, build_hw_bundle

    runtime_loop = MasterRuntimeLoop(build_hw_bundle())
    _drive_loop(runtime_loop)


def main():
    """创建并驱动主车运行循环

    @brief 正常启动后直接进入主循环。
    """

    if _read_button_state("C8"):
        run_pid_identify()
        return
    if _read_button_state("C9"):
        run_calibrate_gyro()
        return

    _start_runtime()


if __name__ == "__main__" and globals().get("__spec__") is None:
    main()
