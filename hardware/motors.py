"""电机控制器工厂函数"""
from seekfree import MOTOR_CONTROLLER


def create_motors():
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

