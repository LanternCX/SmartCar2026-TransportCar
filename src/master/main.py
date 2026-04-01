"""主车启动入口

@file src/master/main.py
"""

import os.path
import sys
import types

if __package__ in ("", None):
    _PACKAGE_NAME = "master"
    _PACKAGE_PATH = os.path.dirname(__file__)
    _package = sys.modules.get(_PACKAGE_NAME)
    if _package is None:
        _package = types.ModuleType(_PACKAGE_NAME)
        _package.__path__ = [_PACKAGE_PATH]
        sys.modules[_PACKAGE_NAME] = _package
    __package__ = _PACKAGE_NAME


def build_hw_bundle():
    from .app import build_hw_bundle as _build_hw_bundle

    return _build_hw_bundle()


def __getattr__(name):
    if name == "MasterRuntimeLoop":
        from .app import MasterRuntimeLoop

        return MasterRuntimeLoop
    raise AttributeError(name)


def _build_runtime_loop_impl():
    runtime_loop_class = getattr(sys.modules[__name__], "MasterRuntimeLoop")
    return runtime_loop_class(build_hw_bundle())


def run_calibrate_gyro():
    from .script.calibrate_gyro import main

    return main()


def run_pid_identify():
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


def _build_runtime_loop():
    return _build_runtime_loop_impl()


def _start_runtime():
    runtime_loop = _build_runtime_loop()
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


if __name__ == "__main__" and __spec__ is None:
    main()
