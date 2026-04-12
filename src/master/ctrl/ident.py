"""主车辨识边界.

@file src/master/ctrl/ident.py
"""


def ident_status():
    """返回主车辨识模块当前占位状态.

    @brief 让上层能显式看出这里尚未接入正式辨识运行时。
    """

    return "pending"
