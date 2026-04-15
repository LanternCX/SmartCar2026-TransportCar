"""搬运车远程控制主程序.

初始化搬运车控制系统并启动 5ms 周期的控制循环.
支持通过 UART3 和 UART6 接收运动指令和查询请求.
"""

from smartcar import ticker
from config import params as _params
from utils.startup_log import startup_log
from vision import create_role_transport_car
from vision.vehicle_role import read_vehicle_role


TICK_MS = getattr(_params, "TICK_MS")


def _create_transport_car(role):
    """按当前角色创建当前运行链使用的车体实例."""

    return create_role_transport_car(role)


def _create_ticker():
    """创建控制周期 ticker."""

    return ticker(1)


def _build_capture_items(car):
    """构造需要交给 ticker 驱动采样的对象列表."""

    capture_items = [state["encoder"] for state in car.wheel_states]
    capture_items.append(car.imu)
    return capture_items


def _run_control_loop(car) -> None:
    """运行主控制循环."""

    loop_logged = False
    while True:
        if not loop_logged:
            startup_log("remote_control", "main loop first iteration")
            loop_logged = True
        if not car.step():
            break


def main():
    """按角色切换视觉运行入口并启动正式运行链."""

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


if globals().get("__spec__") is None:
    main()
