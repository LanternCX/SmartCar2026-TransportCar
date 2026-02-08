"""编码器工厂函数，封装原引脚与反转配置。"""
from smartcar import encoder


def create_encoders():
    encoder_m = encoder("D15", "D16", True)
    encoder_l = encoder("C0", "C1", True)
    encoder_r = encoder("C2", "C3", True)
    return {"m": encoder_m, "l": encoder_l, "r": encoder_r}
