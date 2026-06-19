"""电机控制器工厂函数

封装三个直流电机控制器的引脚分配与方向配置, 适配全向轮底盘布局
"""
from seekfree import MOTOR_CONTROLLER


def create_motors():
    """@brief 创建并配置三个电机控制器

    分别创建中间(m)、左(l)、右(r)三个电机, 配置对应的 PWM 与方向控制引脚
    左电机启用反向, 以补偿全向轮安装方位导致的转向方向差异

    @return 字典 {轮子名称 -> 电机对象}, 键为 "m", "l", "r"
    """
    motor_m = MOTOR_CONTROLLER(
        MOTOR_CONTROLLER.PWM_D4_DIR_D5, 13000, duty=0, invert=False
    )
    motor_l = MOTOR_CONTROLLER(
        MOTOR_CONTROLLER.PWM_D6_DIR_D7, 13000, duty=0, invert=False
    )
    motor_r = MOTOR_CONTROLLER(
        MOTOR_CONTROLLER.PWM_C30_DIR_C31, 13000, duty=0, invert=False
    )
    return {"m": motor_m, "l": motor_l, "r": motor_r}
