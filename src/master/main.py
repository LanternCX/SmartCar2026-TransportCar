"""主车启动入口

@file src/master/main.py
"""

from master.app import MasterRuntimeLoop, build_hw_bundle
from master.script.calibrate_gyro import main as run_calibrate_gyro
from master.script.pid_identify import main as run_pid_identify


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


def _drive_loop(loop):
    """驱动运行循环

    @brief 正常运行分支持续推进主循环。
    """

    while True:
        loop.step(_read_now_ms())


def _build_runtime_loop():
    return MasterRuntimeLoop(build_hw_bundle()["uart"])


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


if __name__ == "__main__":
    main()
