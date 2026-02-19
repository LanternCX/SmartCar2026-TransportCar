"""系统启动引导脚本.

通过拨码开关控制是否启动用户主程序(user_main.py).
当启动时,UART3 波特率为 115200,可用于调试输出.
"""

# 从 machine 库导入所有内容
from machine import *

# 导入垃圾回收和时间库
import gc
import time

# 上电启动时的初始化延迟
time.sleep_ms(50)

# 选择学习板上的一号拨码开关作为启动选择开关
boot_select = Pin("D8", Pin.IN, pull=Pin.PULL_UP_47K)

# 若拨码开关打开(引脚拉低),则启动用户文件
if boot_select.value() == 0:
    try:
        os.chdir("/flash")
        execfile("user_main.py")
    except Exception:
        print("File not found.")
