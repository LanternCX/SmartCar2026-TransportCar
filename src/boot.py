"""启动入口脚本.

上电后先识别车辆角色, 再根据按钮长按语义选择启动脚本。
"""

import builtins
import os
import time

from config.boot_role import clear_vehicle_role, set_vehicle_role
from machine import Pin


ROLE_MAIN = "main"
ROLE_AUX = "aux"

ROLE_PIN_D8 = "D8"
ROLE_PIN_D9 = "D9"
BUTTON1_PIN = "C8"
BUTTON2_PIN = "C9"
BUTTON3_PIN = "C14"
BUTTON4_PIN = "C15"

SCRIPT_PID_IDENTIFY = "script/pid_identify.py"
SCRIPT_CALIBRATE_GYRO = "script/calibrate_gyro.py"
SCRIPT_REMOTE_CONTROL = "script/remote_control.py"

BOOT_SETTLE_MS = 50
LONG_PRESS_SAMPLE_COUNT = 20
LONG_PRESS_SAMPLE_INTERVAL_MS = 10

VEHICLE_ROLE = None


def decode_vehicle_role(d8_value, d9_value):
    """根据 D8/D9 拨码值解码车辆角色.

    注意: D8/D9 板级输入带上拉电阻, 读到 `1` 表示开关断开,
    读到 `0` 表示开关闭合, 排障时不要把电平语义和开关状态混淆.
    """
    if d8_value == 1 and d9_value == 0:
        return ROLE_MAIN
    if d8_value == 0 and d9_value == 1:
        return ROLE_AUX
    raise ValueError(
        "Invalid vehicle role switch combination: D8=%d, D9=%d" % (d8_value, d9_value)
    )


def is_long_press(
    pin,
    sample_count=LONG_PRESS_SAMPLE_COUNT,
    sample_interval_ms=LONG_PRESS_SAMPLE_INTERVAL_MS,
    sleep_ms=time.sleep_ms,
):
    """判断按键在采样窗口内是否持续保持按下."""
    for _ in range(sample_count):
        if pin.value() != 0:
            return False
        sleep_ms(sample_interval_ms)
    return True


def select_boot_script(button1_long_press, button2_long_press):
    """根据按钮长按状态选择启动脚本."""
    if button1_long_press and button2_long_press:
        raise ValueError("Both boot buttons are long-pressed")
    if button1_long_press:
        return SCRIPT_PID_IDENTIFY
    if button2_long_press:
        return SCRIPT_CALIBRATE_GYRO
    return SCRIPT_REMOTE_CONTROL


def run_boot(
    pin_factory=Pin,
    sleep_ms=time.sleep_ms,
    chdir=os.chdir,
    execfile_func=None,
    print_func=print,
):
    """执行启动流程, 并在正常路径暴露车辆角色."""
    global VEHICLE_ROLE

    if execfile_func is None:
        execfile_func = getattr(builtins, "execfile", None)
    if execfile_func is None:
        raise RuntimeError("execfile is not available")

    sleep_ms(BOOT_SETTLE_MS)
    clear_vehicle_role()

    role_pin_d8 = pin_factory(ROLE_PIN_D8, Pin.IN, pull=Pin.PULL_UP_47K)
    role_pin_d9 = pin_factory(ROLE_PIN_D9, Pin.IN, pull=Pin.PULL_UP_47K)
    button1_pin = pin_factory(BUTTON1_PIN, Pin.IN, pull=Pin.PULL_UP_47K)
    button2_pin = pin_factory(BUTTON2_PIN, Pin.IN, pull=Pin.PULL_UP_47K)

    try:
        vehicle_role = decode_vehicle_role(role_pin_d8.value(), role_pin_d9.value())
        boot_script = select_boot_script(
            is_long_press(button1_pin, sleep_ms=sleep_ms),
            is_long_press(button2_pin, sleep_ms=sleep_ms),
        )
    except ValueError as exc:
        print_func(str(exc))
        return None

    VEHICLE_ROLE = vehicle_role
    set_vehicle_role(vehicle_role)

    try:
        chdir("/flash")
        execfile_func(boot_script)
    except OSError:
        clear_vehicle_role()
        print_func("File not found.")
        return None

    return {"vehicle_role": vehicle_role, "script": boot_script}


BOOT_RESULT = run_boot()
