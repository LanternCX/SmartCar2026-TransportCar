"""辅车启动入口

@file src/assistant/main.py
"""

_USE_DIRECT_IMPORTS = globals().get("__package__") in ("", None)
# 运行中周期翻转心跳灯, 方便现场确认主循环仍在推进
RUNTIME_HEARTBEAT_MS = 500


def _debug_print(stage, **payload):
    if not payload:
        print("[assistant.main] %s" % str(stage))
        return
    parts = []
    for key in sorted(payload):
        parts.append("%s=%s" % (str(key), str(payload[key])))
    print("[assistant.main] %s | %s" % (str(stage), ", ".join(parts)))


def run_calibrate_gyro():
    """切到零漂标定脚本

    @brief 按键触发后复用独立脚本完成陀螺仪零漂采集。
    @return object
    """

    if _USE_DIRECT_IMPORTS:
        from script.calibrate_gyro import main
    else:
        from .script.calibrate_gyro import main

    return main()


def run_pid_identify():
    """切到电机辨识脚本

    @brief 按键触发后复用独立脚本完成底座辨识流程。
    @return object
    """

    if _USE_DIRECT_IMPORTS:
        from script.pid_identify import main
    else:
        from .script.pid_identify import main

    return main()


def _read_button_state(pin_name):
    from machine import Pin

    pressed = Pin(pin_name, Pin.IN, Pin.PULL_UP).value() == 0
    _debug_print("button_state", pin=pin_name, pressed=int(pressed))
    return pressed


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


def _noop_ticker_callback(_ticker_obj):
    return None


def _build_runtime_heartbeat_led():
    from machine import Pin

    return Pin("C4", Pin.OUT, value=True)


def _ticks_diff_ms(current_ms, previous_ms):
    import time

    ticks_diff = getattr(time, "ticks_diff", None)
    if ticks_diff is not None:
        return int(ticks_diff(int(current_ms), int(previous_ms)))
    return int(current_ms) - int(previous_ms)


def _build_capture_ticker(hw_bundle):
    from smartcar import ticker

    capture_ticker = ticker(1)
    capture_items = []
    for name in ("m", "l", "r"):
        capture_items.append(hw_bundle["encoders"][name].ensure_device())
    imu_device = hw_bundle["imu"].ensure_device()
    getter = getattr(imu_device, "get", None)
    if getter is not None:
        getter()
    capture_items.append(imu_device)
    capture_ticker.capture_list(*capture_items)
    capture_ticker.callback(_noop_ticker_callback)
    capture_ticker.start(_control_tick_ms())
    _debug_print("capture_ticker_ready", count=len(capture_items))
    return capture_ticker


def _drive_loop(loop):
    """驱动运行循环

    @brief 正常运行分支持续推进主循环。
    """

    _debug_print("drive_loop_enter")
    tick_ms = _control_tick_ms()
    next_tick_ms = None
    heartbeat_led = getattr(loop, "heartbeat_led", None)
    last_heartbeat_ms = None
    while True:
        now_ms = _read_now_ms()

        # 先对齐控制周期, 避免主循环因为空转打乱底座采样节奏
        if next_tick_ms is not None:
            remaining_ms = int(next_tick_ms) - int(now_ms)
            if remaining_ms > 0:
                _sleep_ms(remaining_ms)
                continue

        # 再在固定节拍里翻转心跳灯并推进单步运行时
        if heartbeat_led is not None and (
            last_heartbeat_ms is None
            or _ticks_diff_ms(now_ms, last_heartbeat_ms) >= RUNTIME_HEARTBEAT_MS
        ):
            heartbeat_led.toggle()
            last_heartbeat_ms = int(now_ms)
        loop.step(now_ms)
        next_tick_ms = int(now_ms) + tick_ms


def _start_runtime():
    """装配并启动辅车运行时

    @brief 统一收口硬件装配、运行循环实例和板端采样定时器。
    """

    _debug_print("start_runtime_enter")
    if _USE_DIRECT_IMPORTS:
        from app import AssistantRuntimeLoop, build_hw_bundle
    else:
        from .app import AssistantRuntimeLoop, build_hw_bundle

    # 先完成硬件装配, 保证运行循环与采样链路共用同一套对象
    hw_bundle = build_hw_bundle()
    _debug_print("start_runtime_hw_ready", keys=tuple(sorted(hw_bundle.keys())))
    runtime_loop = AssistantRuntimeLoop(hw_bundle)

    # 再补上周期采样与心跳灯, 让主循环只专注于命令推进
    setattr(runtime_loop, "capture_ticker", _build_capture_ticker(hw_bundle))
    setattr(runtime_loop, "heartbeat_led", _build_runtime_heartbeat_led())
    _debug_print("start_runtime_loop_ready")
    _drive_loop(runtime_loop)


def main():
    """创建并驱动辅车运行循环

    @brief 正常启动后直接进入主循环。
    """

    _debug_print("main_enter")
    # 优先检查维护按键, 现场按键时直接切到对应脚本
    if _read_button_state("C8"):
        _debug_print("main_branch_pid_identify")
        run_pid_identify()
        return
    if _read_button_state("C9"):
        _debug_print("main_branch_calibrate_gyro")
        run_calibrate_gyro()
        return

    # 未触发维护分支时进入正常辅车运行链路
    _debug_print("main_branch_runtime")
    _start_runtime()


if __name__ == "__main__" and globals().get("__spec__") is None:
    main()
