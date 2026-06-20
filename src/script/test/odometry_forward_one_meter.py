"""里程计纵向距离标定脚本.

@file src/script/test/odometry_forward_one_meter.py
@brief 让车辆按当前里程计执行一次车体系 x+ 位移动作, 用于现场测量纵向真实距离
"""

import time


# 标定目标距离, 单位米
TARGET_DISTANCE_M = 1
# 标定运动速度上限, 沿用当前直行动作速度
TARGET_MAX_SPEED_CMD = 3.0
# 标定动作超时时间, 单位毫秒
RUN_TIMEOUT_MS = 60000
# 主循环空转等待时间, 单位毫秒
LOOP_SLEEP_MS = 1


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


def _build_capture_items(car):
    """构造控制周期采样对象列表."""

    capture_items = [state["encoder"] for state in car.wheel_states]
    capture_items.append(car.imu)
    return capture_items


def _log_final_state(car, result, log_fn):
    """打印标定结束时的里程计状态."""

    odometry = getattr(car, "odometry")
    final_x = float(getattr(odometry, "x"))
    final_y = float(getattr(odometry, "y"))
    target_x = float(TARGET_DISTANCE_M)
    target_y = 0.0
    err_x = target_x - final_x
    err_y = target_y - final_y
    detail = (
        "result=%s target_x=%.3f x=%.3f y=%.3f err_x=%.3f err_y=%.3f"
        % (result, target_x, final_x, final_y, err_x, err_y)
    )
    if log_fn is not None:
        log_fn("odometry_forward_one_meter", detail)
        return
    print("odometry_forward_one_meter: %s" % detail)


def run_forward_one_meter_calibration(
    car,
    sleep_ms=_sleep_ms,
    now_ms=_ticks_ms,
    ticks_diff=_ticks_diff,
    log_fn=None,
):
    """运行一次纵向一米标定动作."""

    car.reset_control_state()
    car.set_relative_translation_target(
        TARGET_DISTANCE_M,
        0.0,
        hold_heading_deg=0.0,
        max_speed_cmd=TARGET_MAX_SPEED_CMD,
    )

    start_ms = now_ms()
    result = "done"
    while bool(getattr(car, "command_lock", False)):
        current_ms = now_ms()
        if ticks_diff(current_ms, start_ms) >= RUN_TIMEOUT_MS:
            result = "timeout"
            break
        if not car.step():
            result = "stopped"
            break
        sleep_ms(LOOP_SLEEP_MS)

    _log_final_state(car, result, log_fn)
    car.stop()
    return result


def _create_transport_car():
    """创建基础底盘运行时."""

    from core.runtime import TransportCar
    from vision.vehicle_role import read_vehicle_role

    return TransportCar(vehicle_role=read_vehicle_role())


def main():
    """板端测试入口."""

    from smartcar import ticker
    from config import motion as motion_params
    from utils.startup_log import log, log_exception

    car = None
    pit1 = None
    try:
        car = _create_transport_car()
        pit1 = ticker(1)
        pit1.capture_list(*_build_capture_items(car))
        pit1.callback(car.mark_tick)
        car.set_ticker(pit1)
        pit1.start(getattr(motion_params, "TICK_MS"))
        return run_forward_one_meter_calibration(car, log_fn=log)
    except Exception as exc:
        log_exception("odometry_forward_one_meter", "fatal error: %s" % exc, exc)
        if pit1 is not None:
            pit1.stop()
        if car is not None:
            car.stop()
        raise


if __name__ == "__main__" and globals().get("__spec__") is None:
    main()
