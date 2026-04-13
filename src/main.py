"""当前仓库正式单入口.

@file src/main.py
"""

from utils.startup_log import startup_log

STARTUP_SETTLE_MS = 100
KEY_SCAN_PERIOD_MS = 10
KEY_SCAN_TIMEOUT_MS = 300
LONG_PRESS_VALUE = 2

SCRIPT_PID_IDENTIFY = "script/pid_identify.py"
SCRIPT_CALIBRATE_GYRO = "script/calibrate_gyro.py"
SCRIPT_REMOTE_CONTROL = "script/remote_control.py"


def resolve_startup_script(key_states):
    """根据按键状态决定启动脚本."""

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
    if index >= len(key_states):
        return 0
    return int(key_states[index])


def _copy_key_states(key_states):
    return [int(value) for value in key_states]


def _sleep_ms(delay_ms):
    import time

    sleep_ms = getattr(time, "sleep_ms", None)
    if sleep_ms is not None:
        sleep_ms(int(delay_ms))
        return
    time.sleep(float(delay_ms) / 1000.0)


def _noop_ticker_callback(_ticker_obj):
    return None


def _scan_startup_key_states():
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


def _run_script(script_path):
    import os

    os.chdir("/flash")
    execfile(script_path)


def main():
    """入口阶段只负责按钮判定和脚本分发."""

    startup_log("main", "entry start")
    _sleep_ms(STARTUP_SETTLE_MS)
    key_states = _scan_startup_key_states()
    startup_log("main", "startup keys=%s" % key_states)
    try:
        script_path = resolve_startup_script(key_states)
    except ValueError as exc:
        print(str(exc))
        return None
    startup_log("main", "selected script=%s" % script_path)
    startup_log("main", "launching script=%s" % script_path)
    _run_script(script_path)
    return script_path


if __name__ == "__main__" and globals().get("__spec__") is None:
    main()
