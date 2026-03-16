"""Stage 3 设备观测临时探针脚本."""

import time

from smartcar import ticker

from config.boot_role import get_vehicle_role
from config.params import TICK_MS
from services.diagnostics import format_observe_line
from services.car import TransportCar


SAMPLE_EVERY_TICKS = 20
SETTLE_TICKS = 10
MAX_SAMPLE_COUNT = 3


def emit_snapshot(car, token, builder):
    """打印一条结构化观测快照."""
    print(format_observe_line(token, builder()))


def stop_transport(car):
    """停止 ticker 并清零电机输出."""
    if getattr(car, "ticker", None) is not None:
        car.ticker.stop()
    chassis_state = getattr(car, "chassis_state", None)
    for state in getattr(chassis_state, "wheel_states", ()):  # pragma: no branch
        motor = state.get("motor")
        if motor is not None:
            motor.duty(0)


def main():
    """运行一轮短时设备观测并输出结构化结果."""
    car = None
    sample_count = 0

    try:
        car = TransportCar(vehicle_role=get_vehicle_role())
        pit = ticker(1)
        chassis_state = car.chassis_state
        assert chassis_state is not None
        capture_items = [state["encoder"] for state in chassis_state.wheel_states]
        capture_items.append(car.imu)
        pit.capture_list(*capture_items)
        pit.callback(car.mark_tick)
        car.set_ticker(pit)
        pit.start(TICK_MS)
        facade = car.get_diagnostics_facade()

        next_emit_tick = SETTLE_TICKS
        max_tick = SETTLE_TICKS + SAMPLE_EVERY_TICKS * MAX_SAMPLE_COUNT

        while car.tick_count < max_tick:
            if not car.step():
                print("OBSERVE error stage=step reason=car_stopped")
                break

            if car.tick_count >= next_emit_tick:
                emit_snapshot(car, "health", facade.build_health_snapshot)
                emit_snapshot(car, "tick", facade.build_tick_snapshot)
                emit_snapshot(car, "imu", facade.build_imu_snapshot)
                emit_snapshot(car, "enc", facade.build_encoder_snapshot)
                emit_snapshot(car, "motor", facade.build_motor_snapshot)
                emit_snapshot(car, "vision", facade.build_vision_snapshot)
                sample_count += 1
                next_emit_tick += SAMPLE_EVERY_TICKS

            time.sleep_ms(1)

        print("OBSERVE done status=ok samples=%d" % sample_count)
    except Exception as exc:
        reason = str(exc).replace("\r", " ").replace("\n", " ").replace(",", ";")
        print("OBSERVE error stage=runtime reason=%s" % reason)
    finally:
        if car is not None:
            stop_transport(car)


if __name__ == "__main__":
    main()
