"""当前仓库正式单入口

@file src/main.py
"""


def _allocate_emergency_exception_buffer() -> bool:
    """申请中断异常缓冲区, 保障板端异常可捕获。"""

    try:
        import micropython  # pyright: ignore[reportMissingImports]
    except ImportError:
        return False
    alloc_buffer = getattr(micropython, "alloc_emergency_exception_buf", None)
    if alloc_buffer is None:
        return False
    try:
        alloc_buffer(100)
    except Exception:
        return False
    return True


_allocate_emergency_exception_buffer()

from config import params
from utils.startup_log import startup_log

# 启动后等待时间, 等待外设稳定
STARTUP_SETTLE_MS = 100
# 按键扫描周期
KEY_SCAN_PERIOD_MS = 10
# 按键扫描超时时间
KEY_SCAN_TIMEOUT_MS = 300
# 长按判定值
LONG_PRESS_VALUE = 2

# PID 辨识脚本路径
SCRIPT_PID_IDENTIFY = "script/pid_identify.py"
# 陀螺仪校准脚本路径
SCRIPT_CALIBRATE_GYRO = "script/calibrate_gyro.py"
# 遥控主脚本路径
SCRIPT_REMOTE_CONTROL = "script/remote_control.py"


def _path_exists(path):
    import os

    try:
        os.stat(path)
        return True
    except OSError:
        return False


def resolve_existing_startup_script(script_path):
    """根据板端实际文件选择启动脚本路径."""

    if script_path.endswith(".py"):
        compiled_path = script_path[:-3] + ".mpy"
        if _path_exists(compiled_path):
            return compiled_path
    return script_path


def resolve_startup_script(key_states):
    """根据按键状态决定启动脚本

    @param key_states 按键状态列表
    @return 启动脚本路径
    @throws ValueError C8 与 C9 同时长按时抛出
    """
    key1_held = _read_key_state(key_states, 0) == LONG_PRESS_VALUE
    key2_held = _read_key_state(key_states, 1) == LONG_PRESS_VALUE
    if key1_held and key2_held:
        raise ValueError("C8 与 C9 同时长按，拒绝进入正常脚本")
    if key1_held:
        return SCRIPT_PID_IDENTIFY
    if key2_held:
        return SCRIPT_CALIBRATE_GYRO
    return SCRIPT_REMOTE_CONTROL


def _read_key_state(key_states, index):
    """读取指定索引的按键状态

    @param key_states 按键状态列表
    @param index 索引
    @return 按键状态值, 越界时返回 0
    """
    if index >= len(key_states):
        return 0
    return int(key_states[index])


def _copy_key_states(key_states):
    """复制按键状态列表

    @param key_states 按键状态列表
    @return 新的按键状态列表
    """
    return [int(value) for value in key_states]


def _sleep_ms(delay_ms):
    """毫秒级延时, 兼容 MicroPython 和 CPython

    @param delay_ms 延时毫秒数
    """
    import time

    sleep_ms = getattr(time, "sleep_ms", None)
    if sleep_ms is not None:
        sleep_ms(int(delay_ms))
        return
    time.sleep(float(delay_ms) / 1000.0)


def _convert_power_adc_to_voltage(adc_value):
    """将 B27 ADC 原始值换算为电池电压."""

    return (
        int(adc_value)
        / 65535
        * 3.3
        * 11.0
    )


def _read_startup_voltage():
    """读取上电阶段电池电压."""

    from machine import ADC

    power_adc = ADC("B27")
    return _convert_power_adc_to_voltage(power_adc.read_u16())


def _run_low_voltage_alarm(voltage):
    """低电压时循环蜂鸣告警."""

    from machine import Pin

    on_ms = 100
    beep = Pin("D24", Pin.OUT, value=False)
    off_ms = 1000 - on_ms
    if off_ms < 0:
        off_ms = 0

    while True:
        beep.high()
        _sleep_ms(on_ms)
        beep.low()
        _sleep_ms(off_ms)


def _should_block_startup_for_voltage(voltage):
    """判断上电电压是否低于保护阈值."""

    return float(voltage) < float(params.POWER_MIN_VOLTAGE_V)


def _noop_ticker_callback(_ticker_obj):
    """空 ticker 回调函数, 用于初始化阶段占位"""
    return None


def _scan_startup_key_states():
    """扫描启动按键状态

    在超时时间内轮询按键, 检测是否有长按事件

    @return 按键状态快照列表
    """
    from smartcar import ticker
    from seekfree import KEY_HANDLER

    key = KEY_HANDLER(KEY_SCAN_PERIOD_MS)
    key_states = key.get()
    key_ticker = ticker(1)
    key_ticker.capture_list(key)
    key_ticker.callback(_noop_ticker_callback)
    key_ticker.start(KEY_SCAN_PERIOD_MS)

    try:
        scan_rounds = max(1, KEY_SCAN_TIMEOUT_MS // KEY_SCAN_PERIOD_MS)
        for _ in range(scan_rounds):
            snapshot = _copy_key_states(key_states)
            if snapshot[0] == LONG_PRESS_VALUE or snapshot[1] == LONG_PRESS_VALUE:
                return snapshot
            _sleep_ms(KEY_SCAN_PERIOD_MS)
        return _copy_key_states(key_states)
    finally:
        key_ticker.stop()


def _chdir_flash():
    """切换到板端 Flash 根目录"""
    import os

    os.chdir("/flash")


def _import_module(module_name):
    """导入指定模块

    @param module_name 模块全名
    @return 导入后的模块对象
    """
    return __import__(module_name, None, None, ["*"])


def _script_path_to_module_name(script_path):
    """将脚本路径转换为模块名

    @param script_path 脚本路径
    @return 模块名
    """
    if script_path.endswith(".mpy"):
        script_path = script_path[:-4]
    elif script_path.endswith(".py"):
        script_path = script_path[:-3]
    return script_path.replace("/", ".")


def _run_script(script_path):
    """执行指定脚本

    @param script_path 脚本路径
    @return 脚本执行结果
    """
    _chdir_flash()
    if script_path.endswith(".mpy"):
        module = _import_module(_script_path_to_module_name(script_path))
        return module.main()
    return execfile(script_path)  # pyright: ignore[reportUndefinedVariable]


def main():
    """入口阶段只负责按钮判定和脚本分发"""

    startup_log("main", "entry start")
    _sleep_ms(STARTUP_SETTLE_MS)
    voltage = _read_startup_voltage()
    startup_log("main", "power voltage=%.2fV" % voltage)
    if _should_block_startup_for_voltage(voltage):
        startup_log("main", "low voltage=%.2fV" % voltage)
        return _run_low_voltage_alarm(voltage)
    key_states = _scan_startup_key_states()
    startup_log("main", "startup keys=%s" % key_states)
    try:
        script_path = resolve_existing_startup_script(resolve_startup_script(key_states))
    except ValueError as exc:
        print(str(exc))
        return None
    startup_log("main", "selected script=%s" % script_path)
    startup_log("main", "launching script=%s" % script_path)
    _run_script(script_path)
    return script_path


if __name__ == "__main__" and globals().get("__spec__") is None:
    main()
