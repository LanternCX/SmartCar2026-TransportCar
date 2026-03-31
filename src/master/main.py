"""主车启动入口

@file src/master/main.py
"""

try:
    from master.app import MasterRuntimeLoop, build_hw_bundle
    from master.script.calibrate_gyro import main as run_calibrate_gyro
    from master.script.pid_identify import main as run_pid_identify
except ImportError:
    from app import MasterRuntimeLoop, build_hw_bundle
    from script.calibrate_gyro import main as run_calibrate_gyro
    from script.pid_identify import main as run_pid_identify


def _read_button_state(pin_name, button_reader):
    if button_reader is not None:
        return bool(button_reader(pin_name))
    try:
        from machine import Pin

        return Pin(pin_name, Pin.IN, Pin.PULL_UP).value() == 0
    except ImportError:
        return False


def main(button_reader=None):
    """创建主车运行循环入口对象

    @brief 为启动脚本提供主车主线运行循环
    @return MasterRuntimeLoop
    """

    if _read_button_state("C8", button_reader):
        run_pid_identify()
        return "pid_identify"
    if _read_button_state("C9", button_reader):
        run_calibrate_gyro()
        return "calibrate_gyro"

    return MasterRuntimeLoop(build_hw_bundle()["uart"])
