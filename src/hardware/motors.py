"""电机控制器工厂函数

封装三个直流电机控制器的引脚分配与方向配置, 适配全向轮底盘布局
"""
from seekfree import MOTOR_CONTROLLER


def _resolve_motor_mapping(vehicle_role):
    """按车辆角色返回三轮电机通道与方向配置."""

    if vehicle_role == "master":
        return {
            "m": (MOTOR_CONTROLLER.PWM_D4_DIR_D5, True),
            "l": (MOTOR_CONTROLLER.PWM_D6_DIR_D7, True),
            "r": (MOTOR_CONTROLLER.PWM_C28_DIR_C29, True),
        }
    if vehicle_role == "assistant":
        return {
            "m": (MOTOR_CONTROLLER.PWM_D4_DIR_D5, True),
            "l": (MOTOR_CONTROLLER.PWM_C30_DIR_C31, True),
            "r": (MOTOR_CONTROLLER.PWM_D6_DIR_D7, True),
        }
    raise ValueError("unknown vehicle role for motors: %s" % vehicle_role)


def create_motors(vehicle_role="assistant"):
    """@brief 创建并配置三个电机控制器

    分别创建中间(m)、左(l)、右(r)三个电机, 配置对应的 PWM 与方向控制引脚
    不同车辆角色使用不同接线映射, 底层控制语义保持一致

    @param vehicle_role 车辆角色, master 使用旧硬件接线, assistant 使用新硬件接线
    @return 字典 {轮子名称 -> 电机对象}, 键为 "m", "l", "r"
    """
    mapping = _resolve_motor_mapping(vehicle_role)
    motor_m = MOTOR_CONTROLLER(mapping["m"][0], 13000, duty=0, invert=mapping["m"][1])
    motor_l = MOTOR_CONTROLLER(mapping["l"][0], 13000, duty=0, invert=mapping["l"][1])
    motor_r = MOTOR_CONTROLLER(mapping["r"][0], 13000, duty=0, invert=mapping["r"][1])
    return {"m": motor_m, "l": motor_l, "r": motor_r}
