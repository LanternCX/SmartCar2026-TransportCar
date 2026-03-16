"""搬运车远程控制主程序.

初始化搬运车控制系统并启动 5ms 周期的控制循环.
支持通过 UART3 和 UART6 接收运动指令和查询请求.
"""

from config.boot_role import get_vehicle_role
from smartcar import ticker
from config.params import TICK_MS
from services.car import TransportCar


VEHICLE_ROLE = get_vehicle_role()


car = TransportCar(vehicle_role=VEHICLE_ROLE)

car.uart3.write("Creating ticker...\r\n")
pit1 = ticker(1)

# 注册编码器和 IMU 到 ticker 的采集列表,驱动周期更新
chassis_state = car.chassis_state
assert chassis_state is not None
capture_items = [state["encoder"] for state in chassis_state.wheel_states]
capture_items.append(car.imu)
pit1.capture_list(*capture_items)
pit1.callback(car.mark_tick)
car.set_ticker(pit1)

car.uart3.write("Starting ticker (%d ms)...\r\n" % TICK_MS)
pit1.start(TICK_MS)
car.uart3.write("Initialization complete. Control loop started.\r\n")

# 主控制循环
while True:
    if not car.step():
        break
