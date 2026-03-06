"""编码器工厂函数,封装引脚配置与反转设置."""
from smartcar import encoder
 


def create_encoders():
    """创建三个编码器对象.
    
    分别对应中间(m)、左(l)、右(r)轮.所有编码器均启用反转计数.
    
    返回:
        字典 {轮子名称 -> 编码器对象},键为 "m", "l", "r".
    """
    encoder_m = encoder("D15", "D16", True)
    encoder_l = encoder("C0", "C1", True)
    encoder_r = encoder("C2", "C3", True)
    return {"m": encoder_m, "l": encoder_l, "r": encoder_r}
