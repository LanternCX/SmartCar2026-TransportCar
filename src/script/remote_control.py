"""搬运车远程控制主程序.

初始化搬运车控制系统并启动 5ms 周期的控制循环.
支持通过 UART3 和 UART6 接收运动指令和查询请求.
"""

from config.boot_role import get_vehicle_role
from smartcar import ticker
from config.params import TICK_MS
from services.car import TransportCar


def _trace_mem(stage: str, uart=None) -> None:
    """@brief 输出启动阶段内存曲线埋点.

    @param stage 当前阶段名
    @param uart 可选串口对象
    """
    try:
        TransportCar.trace_runtime_mem(stage, uart=uart)
    except Exception as exc:
        try:
            TransportCar.trace_runtime_failure(stage, exc, uart=uart)
        except Exception:
            return


_trace_mem("after_import_transport_car")


VEHICLE_ROLE = get_vehicle_role()


_trace_mem("before_core_init")
try:
    car = TransportCar(vehicle_role=VEHICLE_ROLE)
except Exception as exc:
    TransportCar.trace_runtime_failure("core_init", exc)
    raise
flush_pending = getattr(TransportCar, "flush_pending_runtime_traces", None)
if callable(flush_pending):
    flush_pending(car.uart3)
_trace_mem("after_core_init", uart=car.uart3)

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
_trace_mem("before_first_step", uart=car.uart3)
first_step = True
while True:
    try:
        keep_running = car.step()
    except Exception as exc:
        TransportCar.trace_runtime_failure(
            "first_step" if first_step else "step", exc, uart=car.uart3
        )
        raise
    if first_step:
        _trace_mem("after_first_step", uart=car.uart3)
        first_step = False
    if not keep_running:
        break
