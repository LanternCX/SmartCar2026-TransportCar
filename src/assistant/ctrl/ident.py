"""辅车辨识边界.

@file src/assistant/ctrl/ident.py
"""


def ident_status():
    """返回辅车辨识模块当前实现状态.

    @brief 让上层在接线与脚本尚未完全收口前能显式识别该边界仍是占位实现。
    """

    return "pending"
