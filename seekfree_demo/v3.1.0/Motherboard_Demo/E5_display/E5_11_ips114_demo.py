
# 本示例程序演示如何使用 display 库
# 使用 RT1021-MicroPython 核心板搭配对应拓展学习板的屏幕接口测试

# 示例程序运行效果为循环在 IPS114 上刷新全屏颜色 然后显示数字 画线
# 当 SWITCH2 引脚电平出现变化时退出测试程序

# 包含 gc 与 time 类
import gc, time
# 从 machine 库包含所有内容
from machine import *
# 从 smartcar 库包含所有内容
from smartcar import *
# 从 seekfree 库包含所有内容
from seekfree import *
# 从 display 库包含所有内容
from display import *
# 从 array 库包含所有内容
from array import *

# 延迟上电 避免 CR 时序控制导致屏幕还未成功启动
time.sleep_ms(100)

print("REAL TYPE : " + BOARD_TYPE)
print("BOARD VERSION : " + BOARD_VERSION)

LED_PIN = 'C4'
SWITCH2_PIN = None
LCD_CS_PIN = None
LCD_RST_PIN = None
LCD_DC_PIN = None
LCD_BLK_PIN = None
LCD_SPI_SELECT = None
if BOARD_TYPE == 'RT1021_144P_BTB':
    # RT1021-144P-BTB 核心板上 C4  是 LED
    # RT1021-144P-BTB 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
    # RT1021-144P-BTB 学习板上 B29 对应屏幕接口的 CS
    # RT1021-144P-BTB 学习板上 B31 对应屏幕接口的 RST
    # RT1021-144P-BTB 学习板上 B5  对应屏幕接口的 DC
    # RT1021-144P-BTB 学习板上 C21 对应屏幕接口的 BLK
    LCD_CS_PIN  = 'B29'
    LCD_RST_PIN = 'B31'
    LCD_DC_PIN  = 'B5'
    LCD_BLK_PIN = 'C21'
    LCD_SPI_SELECT = 2
elif BOARD_TYPE == 'RT1021_144P_2P54':
    # RT1021-144P-2.54 核心板上 C4  是 LED
    # RT1021-144P-2.54 学习板上 D9  对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'D9'
    # RT1021-144P-BTB 学习板上 B29 对应屏幕接口的 CS
    # RT1021-144P-BTB 学习板上 B31 对应屏幕接口的 RST
    # RT1021-144P-BTB 学习板上 B5  对应屏幕接口的 DC
    # RT1021-144P-BTB 学习板上 C21 对应屏幕接口的 BLK
    LCD_CS_PIN  = 'B29'
    LCD_RST_PIN = 'B31'
    LCD_DC_PIN  = 'B5'
    LCD_BLK_PIN = 'C21'
    LCD_SPI_SELECT = 2
elif BOARD_TYPE == 'RT1021_100P_2P54':
    # RT1021-100P-2.54 核心板上 C4  是 LED
    # RT1021-100P-2.54 学习板上 C19 对应二号拨码开关
    LED_PIN = 'C4'
    SWITCH2_PIN = 'C19'
    # RT1021-144P-BTB 学习板上 C5  对应屏幕接口的 CS
    # RT1021-144P-BTB 学习板上 B9  对应屏幕接口的 RST
    # RT1021-144P-BTB 学习板上 B8  对应屏幕接口的 DC
    # RT1021-144P-BTB 学习板上 C4  对应屏幕接口的 BLK
    LCD_CS_PIN  = 'C5'
    LCD_RST_PIN = 'B9'
    LCD_DC_PIN  = 'B8'
    LCD_BLK_PIN = 'C4'
    LCD_SPI_SELECT = 1

print("LED_PIN     : " + LED_PIN)
print("SWITCH2_PIN : " + SWITCH2_PIN)
print("LCD_CS_PIN  : " + LCD_CS_PIN)
print("LCD_RST_PIN : " + LCD_RST_PIN)
print("LCD_DC_PIN  : " + LCD_DC_PIN)
print("LCD_BLK_PIN : " + LCD_BLK_PIN)
print("LCD_SPI_SELECT : " + str(LCD_SPI_SELECT))

led     = Pin(LED_PIN, Pin.OUT, value = True)
switch2 = Pin(SWITCH2_PIN, Pin.IN , pull = Pin.PULL_UP_47K)
state2  = switch2.value()

# 定义片选引脚 拉高拉低一次 CS 片选确保屏幕通信时序正常
cs = Pin(LCD_CS_PIN, Pin.OUT, value=True)
cs.high()
cs.low()

# 定义控制引脚
rst = Pin(LCD_RST_PIN, Pin.OUT, value=True)
dc  = Pin(LCD_DC_PIN, Pin.OUT, value=True)
blk = Pin(LCD_BLK_PIN, Pin.OUT, value=True)

# ------------------------------------------------------------------------------
#   构造接口 用于构建一个 LCD_Drv 对象
#   LCD_Drv(SPI_INDEX, BAUDRATE, DC_PIN, RST_PIN, LCD_TYPE)
#       SPI_INDEX       接口索引    |   必要参数 关键字输入 选择屏幕所用的 SPI 接口索引
#       BAUDRATE        通信速率    |   必要参数 关键字输入 SPI 的通信速率 最高 60MHz
#       DC_PIN          命令引脚    |   必要参数 关键字输入 一个 Pin 实例
#       RST_PIN         复位引脚    |   必要参数 关键字输入 一个 Pin 实例
#       LCD_TYPE        屏幕类型    |   必要参数 关键字输入 LCD_Drv.(LCD200_TYPE, LCD114_TYPE)
#       return          返回内容    |   正常情况下返回对应 LCD_Drv 的对象
# ------------------------------------------------------------------------------
drv = LCD_Drv(SPI_INDEX = 2, BAUDRATE = 60000000, DC_PIN = dc, RST_PIN = rst, LCD_TYPE = LCD_Drv.LCD114_TYPE)

# ------------------------------------------------------------------------------
# 构造接口 用于构建一个 LCD 对象
#   LCD(LCD_Drv)
#       LCD_Drv         接口对象    |   必要参数 LCD_Drv 对象
#       return          返回内容    |   正常情况下返回对应 LCD 的对象
# ------------------------------------------------------------------------------
lcd = LCD(drv)

# LCD 接口 :
# ------------------------------------------------------------------------------
#   修改 LCD 的前景色与背景色
#   LCD.color(pcolor, bgcolor)
#       pcolor          前景色     |   必要参数 RGB565 格式
#       bgcolor         背景色     |   必要参数 RGB565 格式
# ------------------------------------------------------------------------------
#   修改 LCD 的显示方向
#   LCD.mode(dir)
#       dir             显示方向    |   必要参数 [0-竖屏, 1-横屏, 2-竖屏180旋转, 3-横屏180旋转]
# ------------------------------------------------------------------------------
#   清屏 不传入参数就使用当前的 背景色 清屏
#   LCD.clear()
#   LCD.clear(color)
#       color           颜色数值    |   非必要参数 RGB565 格式 输入参数则更新背景色并清屏
# ------------------------------------------------------------------------------
#   各字体大小显示字符串
#   LCD.str12(x, y, str, color = pcolor)
#   LCD.str16(x, y, str, color = pcolor)
#   LCD.str24(x, y, str, color = pcolor)
#   LCD.str32(x, y, str, color = pcolor)
#       x               横轴坐标    |   必要参数 起始显示 X 坐标
#       y               纵轴坐标    |   必要参数 起始显示 Y 坐标
#       str             字符对象    |   必要参数 字符串
#       color           颜色数值    |   非必要参数 字符颜色 可以不填使用默认的前景色
# ------------------------------------------------------------------------------
#   显示一条线
#   LCD.line(x_star, y_star, x_end, y_end, color = pcolor, thick = 1)
#       x_star          横轴坐标    |   必要参数 起始 X 坐标
#       y_star          纵轴坐标    |   必要参数 起始 Y 坐标
#       x_end           横轴坐标    |   必要参数 结束 X 坐标
#       y_end           纵轴坐标    |   必要参数 结束 Y 坐标
#       color           颜色数值    |   非必要参数 线条颜色 可以不填使用默认的前景色
#       thick           线条粗细    |   非必要参数 线条粗细 默认一个像素宽度
# ------------------------------------------------------------------------------
#   显示一个波形
#   LCD.wave(x, y, width, high, data, max)
#       x               横轴坐标    |   必要参数 起始显示 X 坐标
#       y               纵轴坐标    |   必要参数 起始显示 Y 坐标
#       width           显示宽度    |   必要参数 波形显示窗口宽度 最好等同于数据个数
#       high            显示高度    |   必要参数 波形显示窗口高度
#       data            数据对象    |   必要参数 线条颜色 使用 unsigned short 类型的数组对象 兼容适配 TSL1401 数据列表
#       max             最大数值    |   必要参数 数据的最大值 用于进行波形高度的缩放
# ------------------------------------------------------------------------------

lcd.color(0xFFFF, 0x0000)
lcd.mode(1)
lcd.clear(0x0000)

arr = array('h', [0] * 120)
for i in range(0, 60):
    arr[i] = i * 2
    arr[119 - i] = i * 2

while True:
    time.sleep_ms(500)
    lcd.clear(0xF800)
    time.sleep_ms(500)
    lcd.clear(0x07E0)
    time.sleep_ms(500)
    lcd.clear(0x001F)
    time.sleep_ms(500)
    lcd.clear(0xFFFF)
    time.sleep_ms(500)
    lcd.clear(0x0000)
    time.sleep_ms(500)

    # 显示数据与显示字符串对于 Python 来说没有区别
    # 不管你要显示 字符 还是数字
    # 对于 Python 来说他们都是一样的
    # 用 format 或者 "%..."%(...) 统一处理为字符串对象
    
    lcd.str12(0,  0, "15={:b},{:d},{:o},{:#x}.".format(15,15,15,15), 0xF800)
    lcd.str16(0, 12, "1.234={:>.2f}.".format(1.234), 0x07E0)
    lcd.str24(0, 28, "123={:<6d}.".format(123), 0x001F)
    lcd.str32(0, 52, "123={:>6d}.".format(123), 0xFFFF)
    time.sleep_ms(500)
    
    lcd.line(200,   0, 240,  84, color = 0xFFFF, thick = 1)
    time.sleep_ms(500)
    lcd.line(240,   0, 200,  84, color = 0x3616, thick = 3)
    time.sleep_ms(500)
    
    lcd.wave(  0,  84, 120, 32, arr, max = 120)
    lcd.wave(120, 100, 120, 16, arr, max = 120)
    time.sleep_ms(500)
    
    # 如果拨码开关打开 对应引脚拉低 就退出循环
    # 这么做是为了防止写错代码导致异常 有一个退出的手段
    if switch2.value() != state2:
        print("Test program stop.")
        break
    
    # 回收内存
    gc.collect()
