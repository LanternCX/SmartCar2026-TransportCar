"""搬运车远程控制主程序.

初始化搬运车控制系统并启动 5ms 周期的控制循环.
支持通过 UART3 和 UART6 接收运动指令和查询请求.
"""

from smartcar import ticker
from config.params import TICK_MS
from services.transport_car import TransportCar
from utils.startup_log import startup_log


startup_log("remote_control", "module start")
startup_log("remote_control", "creating TransportCar")
car = TransportCar()
startup_log("remote_control", "TransportCar ready")

startup_log("remote_control", "creating ticker")
pit1 = ticker(1)

# 注册编码器和 IMU 到 ticker 的采集列表,驱动周期更新
capture_items = [state["encoder"] for state in car.wheel_states]
capture_items.append(car.imu)
startup_log("remote_control", "binding capture items=%d" % len(capture_items))
pit1.capture_list(*capture_items)
pit1.callback(car.mark_tick)
car.set_ticker(pit1)

startup_log("remote_control", "starting ticker=%dms" % TICK_MS)
pit1.start(TICK_MS)
startup_log("remote_control", "entering main loop")

# 主控制循环
loop_logged = False
while True:
    if not loop_logged:
        startup_log("remote_control", "main loop first iteration")
        loop_logged = True
    if not car.step():
        break
