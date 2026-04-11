"""电机控制器工厂函数."""
from seekfree import MOTOR_CONTROLLER


def create_motors():
    """创建并配置三个电机控制器.
    
    创建中间(m)、左(l)、右(r)三个电机,配置对应的 PWM 和方向控制引脚.
    中间电机不反向,左电机反向以适应全向轮配置,右电机不反向.
    
    返回:
        字典 {轮子名称 -> 电机对象},键为 "m", "l", "r".
    """
    motor_m = MOTOR_CONTROLLER(
        MOTOR_CONTROLLER.PWM_C30_DIR_C31, 13000, duty=0, invert=False
    )
    motor_l = MOTOR_CONTROLLER(
        MOTOR_CONTROLLER.PWM_D4_DIR_D5, 13000, duty=0, invert=False
    )
    motor_r = MOTOR_CONTROLLER(
        MOTOR_CONTROLLER.PWM_D6_DIR_D7, 13000, duty=0, invert=True
    )
    return {"m": motor_m, "l": motor_l, "r": motor_r}

