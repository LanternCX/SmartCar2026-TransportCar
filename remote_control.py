from smartcar import ticker
from config.params import TICK_MS
from services.transport_car import TransportCar


car = TransportCar()

car.uart3.write("Creating ticker...\r\n")
pit1 = ticker(1)

capture_items = [state["encoder"] for state in car.wheel_states]
capture_items.append(car.imu)
pit1.capture_list(*capture_items)
pit1.callback(car.mark_tick)
car.set_ticker(pit1)

car.uart3.write("Starting ticker (%d ms)...\r\n" % TICK_MS)
pit1.start(TICK_MS)
car.uart3.write("Initialization complete. Control loop started.\r\n")

while True:
    if not car.step():
        break
