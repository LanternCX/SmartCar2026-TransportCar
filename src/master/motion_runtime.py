"""主车最小运动执行层.

@file src/master/motion_runtime.py
"""

from master.protocol import build_move_command


class MotionRuntime:
    """主车最小运动执行层

    @brief 收口主车自身目标与辅车命令接口
    """

    def __init__(self) -> None:
        self.last_target = None

    def apply_self_target(self, target: dict) -> dict:
        """记录主车当前目标

        @brief 保存最近一次主车自身运动目标
        @param target 主车目标字典
        @return dict
        """

        self.last_target = dict(target)
        return self.last_target

    def build_assistant_command(self, dx: float, dy: float, dtheta: float) -> str:
        """构造辅车运动命令

        @brief 透传最小 MOVE 协议
        @param dx 右向增量
        @param dy 前向增量
        @param dtheta 顺时针角增量
        @return str
        """

        return build_move_command(dx, dy, dtheta)
