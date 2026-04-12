"""辅车存储边界.

@file src/assistant/ctrl/storage.py
"""


def storage_status():
    """返回辅车存储模块当前实现状态.

    @brief 让上层区分参数持久化能力是否已经从占位状态进入可用实现。
    """

    return "pending"
