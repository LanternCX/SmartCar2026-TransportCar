"""主车运行时状态收口

@file src/master/motion_runtime.py
"""


class MotionRuntime:
    """负责保存主车目标和辅车控制序号

    @brief 为应用层提供状态写回和序号分配能力
    """

    def __init__(self):
        # 最近一次主车目标保存在运行时中, 供状态查询复用
        self.last_target = None
        # 跟随控制序号保持单调递增, 供辅车去重
        self._control_seq = 0

    def apply_self_target(self, target):
        """记录主车当前目标

        @brief 保存最近一次主车动作目标
        @param target 主车目标字典
        @return dict
        """

        self.last_target = dict(target)
        return self.last_target

    def next_control_seq(self):
        """分配新的跟随控制序号

        @brief 保证发给辅车的控制序号单调递增
        @return int
        """

        self._control_seq += 1
        return self._control_seq
