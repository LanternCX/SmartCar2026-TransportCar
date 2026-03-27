"""主车最小运动执行层.

@file src/master/motion_runtime.py
"""


class MotionRuntime:
    """主车最小运动执行层

    @brief 收口主车自身目标与辅车命令接口
    """

    def __init__(self):
        self.last_target = None
        self._control_seq = 0

    def apply_self_target(self, target):
        """记录主车当前目标

        @brief 保存最近一次主车自身运动目标
        @param target 主车目标字典
        @return dict
        """

        self.last_target = dict(target)
        return self.last_target

    def next_control_seq(self):
        """分配新的跟随控制序号

        @brief 保证主车发给辅车的 `seq` 单调递增
        @return int
        """

        self._control_seq += 1
        return self._control_seq
