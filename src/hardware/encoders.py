"""编码器工厂函数

封装三个轮速编码器的引脚配置与反转设置, 统一提供轮速反馈接口
"""
from smartcar import encoder


def _resolve_encoder_mapping(vehicle_role):
    """按车辆角色返回三轮编码器接线与方向配置."""

    if vehicle_role == "master":
        return {
            "m": ("D13", "D14", False),
            "l": ("D15", "D16", False),
            "r": ("C0", "C1", False),
        }
    if vehicle_role == "assistant":
        return {
            "m": ("D13", "D14", False),
            "l": ("C2" , "C3", False),
            "r": ("D15", "D16", False),
        }
    raise ValueError("unknown vehicle role for encoders: %s" % vehicle_role)


def create_encoders(vehicle_role="assistant"):
    """@brief 创建三个编码器对象

    分别对应中间(m)、左(l)、右(r)轮, 按车辆角色选择接线映射

    @param vehicle_role 车辆角色, master 使用旧硬件接线, assistant 使用新硬件接线
    @return 字典 {轮子名称 -> 编码器对象}, 键为 "m", "l", "r"
    """
    mapping = _resolve_encoder_mapping(vehicle_role)
    encoder_m = encoder(mapping["m"][0], mapping["m"][1], mapping["m"][2])
    encoder_l = encoder(mapping["l"][0], mapping["l"][1], mapping["l"][2])
    encoder_r = encoder(mapping["r"][0], mapping["r"][1], mapping["r"][2])
    return {"m": encoder_m, "l": encoder_l, "r": encoder_r}
