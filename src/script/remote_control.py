"""搬运车远程控制主程序

@file src/script/remote_control.py
@brief 搬运车的核心控制入口, 初始化系统并启动 5ms 周期的控制循环

@details 根据车辆角色 (主车/辅车) 创建对应的运行时实例, 启动定时中断驱动的控制循环, 支持通过 UART3 接收上游指令, 按角色使用 UART8 / UART6 进行视觉数据通信
"""

from smartcar import ticker
from config import motion as motion_params
from utils.startup_log import startup_log
from vision import create_role_transport_car
from vision.vehicle_role import read_vehicle_role


TICK_MS = getattr(motion_params, "TICK_MS")


def _create_transport_car(role):
    """按当前角色创建当前运行链使用的车体实例

    @brief 根据拨码开关读取的角色标识, 创建对应的视觉运行时实例

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


def _build_capture_items(car):
    """构造需要交给 ticker 驱动采样的对象列表

    @brief 汇总所有需要在每个控制周期采样的硬件接口

    @param car TransportCar 实例

    @return 包含编码器和 IMU 对象的列表, ticker 每周期调用这些对象的采样方法
    """
    capture_items = [state["encoder"] for state in car.wheel_states]
    capture_items.append(car.imu)
    return capture_items


def _run_control_loop(car) -> None:
    """运行主控制循环

    @brief 驱动车体状态机的单步推进, 执行命令接收、运动学计算、PID 控制等

    @details 循环调用 car.step(), 若返回 False 则表示指令要求退出, 终止循环

    @param car TransportCar 实例
    """
    loop_logged = False
    while True:
        if not loop_logged:
            startup_log("remote_control", "main loop first iteration")
            loop_logged = True
        if not car.step():
            break


def _stop_runtime_after_fatal(car, pit1) -> None:
    """致命异常后停止板端运行资源."""

    if pit1 is not None:
        try:
            pit1.stop()
        except Exception as exc:
            startup_log("remote_control", "fatal ticker stop failed: %s" % exc)
    if car is not None:
        try:
            car.stop()
        except Exception as exc:
            startup_log("remote_control", "fatal car stop failed: %s" % exc)


def main():
    """按角色切换视觉运行入口并启动正式运行链

    @brief 启动序列入口, 读取拨码开关、创建车体实例、启动定时中断、运行主循环
    """

    car = None
    pit1 = None
    try:
        startup_log("remote_control", "module start")
        role = read_vehicle_role()
        startup_log("remote_control", "vehicle role=%s" % role)
        startup_log("remote_control", "vision runtime ready=%s" % role)

        startup_log("remote_control", "creating TransportCar")
        car = _create_transport_car(role)
        startup_log("remote_control", "TransportCar ready")

        startup_log("remote_control", "creating ticker")
        pit1 = _create_ticker()
        capture_items = _build_capture_items(car)
        startup_log("remote_control", "binding capture items=%d" % len(capture_items))
        pit1.capture_list(*capture_items)
        pit1.callback(car.mark_tick)
        car.set_ticker(pit1)

        startup_log("remote_control", "starting ticker=%dms" % TICK_MS)
        pit1.start(TICK_MS)
        startup_log("remote_control", "entering main loop")
        _run_control_loop(car)
        return role
    except Exception as exc:
        _stop_runtime_after_fatal(car, pit1)
        raise


if globals().get("__spec__") is None:
    main()
