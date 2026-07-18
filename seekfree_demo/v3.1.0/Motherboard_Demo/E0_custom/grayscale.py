import gc, time

from machine import *
from seekfree import *
from smartcar import *

time.sleep_ms(100)

print("REAL TYPE : " + BOARD_TYPE)
print("BOARD VERSION : " + BOARD_VERSION)

LED_PIN = 'C4'
GRAY_PIN = 'D19'

led = Pin(LED_PIN, Pin.OUT, value = True)
gray = Pin(GRAY_PIN, Pin.IN)

print("LED_PIN: " + LED_PIN)
print("GRAY_PIN: " + GRAY_PIN)

pit1 = ticker(1)

ticker_flag = False

def time_pit_handler (ticker_obj):
    global ticker_flag
    ticker_flag = True

pit1.callback(time_pit_handler)
pit1.start(5)

state = False

while True:
    if ticker_flag:
        ticker_flag = False

        if gray.value() != state:
            if gray.value():
                led.on()
                print("Gray is off")
            else:
                led.off()
                print("Gray is on")
            state = gray.value()
