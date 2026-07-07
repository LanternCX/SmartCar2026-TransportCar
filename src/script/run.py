"""搬运车远程控制主程序

@file src/script/run.py
@brief 搬运车的核心控制入口, 初始化系统并启动分层控制循环

@details 根据车辆角色 (主车/辅车) 创建对应的运行时实例, 由 ticker 触发底盘控制周期,
         主循环优先处理底盘控制, 空闲时推进通信和角色状态机
"""

import time

from smartcar import ticker
from config import motion as motion_params
from utils.startup_log import log, log_exception, log_memory
from role import create_role_transport_car
from role.vehicle_role import read_vehicle_role


TICK_MS = motion_params.TICK_MS
ROLE_STEP_MS = motion_params.ROLE_STEP_MS
MOTION_INPUT_STEP_MS = motion_params.MOTION_INPUT_STEP_MS
LOG_STAGE = "run"


def _create_transport_car(role):
    """按当前角色创建当前运行链使用的车体实例

    @brief 根据拨码开关读取的角色标识, 创建对应的角色运行时实例

    @param role 车辆角色标识符 (0 = 主车, 1 = 辅车)

    @return TransportCar 实例, 包含硬件接口、控制器等完整运行时状态
    """
    return create_role_transport_car(role)


def _create_ticker():
    """创建控制周期 ticker

    @brief 初始化 PIT 中断驱动, 使用定时中断触发周期任务

    @return ticker 对象, 用于驱动编码器和 IMU 的数据采样
    """
    return ticker(1)


def _now_ms():
    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


def _ticks_diff_ms(current_ms, previous_ms):
    ticks_diff = getattr(time, "ticks_diff", None)
    if ticks_diff is not None:
        return int(ticks_diff(current_ms, previous_ms))
    return int(current_ms - previous_ms)


def _idle_wait():
    sleep_ms = getattr(time, "sleep_ms", None)
    if sleep_ms is not None:
        sleep_ms(1)
        return
    time.sleep(0.001)


def _build_capture_items(car):
    """构造需要交给 ticker 驱动采样的对象列表

    @brief 汇总所有需要在每个控制周期采样的硬件接口

    @param car TransportCar 实例

    @return 包含编码器和 IMU 对象的列表, ticker 每周期调用这些对象的采样方法
    """
    capture_items = [state["encoder"] for state in car.wheel_states]
    capture_items.append(car.imu)
    return capture_items


def _has_pending_control_tick(car) -> bool:
    return bool(car.has_pending_tick())


def _step_control(car) -> bool:
    return bool(car.step_control())


def _step_role(car) -> bool:
    return bool(car.step_role())


def _step_motion_input(car) -> bool:
    return bool(car.step_motion_input())


def _collect_runtime_garbage(car) -> None:
    car.collect_garbage()


def _run_control_loop(car, now_ms=None) -> None:
    """运行主控制循环

    @brief 按优先级调度底盘控制、通信收发和角色状态机

    @details 有待处理底盘 tick 时优先执行底盘控制; 无底盘积压时推进通信收发;
             角色状态机按 ROLE_STEP_MS 低频运行, 若返回 False 则终止循环

    @param car TransportCar 实例
    """
    loop_logged = False
    last_role_step_ms = None
    last_motion_input_step_ms = None
    last_comm_step_ms = None
    now_ms = now_ms or _now_ms
    while True:
        if not loop_logged:
            log(LOG_STAGE, "main loop first iteration")
            loop_logged = True

        current_ms = int(now_ms())
        control_due = _has_pending_control_tick(car)
        role_due = last_role_step_ms is None or (
            _ticks_diff_ms(current_ms, last_role_step_ms) >= ROLE_STEP_MS
        )
        motion_input_due = last_motion_input_step_ms is None or (
            _ticks_diff_ms(current_ms, last_motion_input_step_ms) >= MOTION_INPUT_STEP_MS
        )
        comm_due = last_comm_step_ms is None or (
            _ticks_diff_ms(current_ms, last_comm_step_ms) >= TICK_MS
        )

        if not control_due and not role_due and not motion_input_due and not comm_due:
            _idle_wait()
            continue

        if control_due:
            if not _step_control(car):
                break

        _collect_runtime_garbage(car)
        if comm_due:
            car.poll_transport_rx()
            last_comm_step_ms = current_ms
        keep_running = True
        if role_due:
            keep_running = _step_role(car)
            last_role_step_ms = current_ms
        if keep_running and motion_input_due:
            keep_running = _step_motion_input(car)
            last_motion_input_step_ms = current_ms
        if comm_due:
            car.poll_transport_tx()
        if not keep_running:
            break


def _stop_runtime_after_fatal(car, pit1) -> None:
    """致命异常后停止板端运行资源."""

    if pit1 is not None:
        try:
            pit1.stop()
        except Exception as exc:
            log_exception(
                LOG_STAGE,
                "fatal ticker stop failed: %s" % exc,
                exc,
            )
    if car is not None:
        try:
            car.stop()
        except Exception as exc:
            log_exception(
                LOG_STAGE,
                "fatal car stop failed: %s" % exc,
                exc,
            )


def main():
    """按角色切换角色运行入口并启动正式运行链

    @brief 启动序列入口, 读取拨码开关、创建车体实例、启动定时中断、运行主循环
    """

    car = None
    pit1 = None
    try:
        log(LOG_STAGE, "module start")
        role = read_vehicle_role()
        log(LOG_STAGE, "vehicle role=%s" % role)
        log(LOG_STAGE, "vision runtime ready=%s" % role)

        log(LOG_STAGE, "creating TransportCar")
        log_memory("r0")
        car = _create_transport_car(role)
        log_memory("r1")
        log(LOG_STAGE, "TransportCar ready")

        log(LOG_STAGE, "creating ticker")
        pit1 = _create_ticker()
        capture_items = _build_capture_items(car)
        log(LOG_STAGE, "binding capture items=%d" % len(capture_items))
        pit1.capture_list(*capture_items)
        pit1.callback(car.mark_tick)
        car.set_ticker(pit1)

        log(LOG_STAGE, "starting ticker=%dms" % TICK_MS)
        pit1.start(TICK_MS)
        log(LOG_STAGE, "entering main loop")
        _run_control_loop(car)
        return role
    except Exception as exc:
        log_exception(LOG_STAGE, "fatal error: %s" % exc, exc)
        _stop_runtime_after_fatal(car, pit1)
        raise


if globals().get("__spec__") is None:
    main()
