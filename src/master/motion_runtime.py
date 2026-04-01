"""主车运行时状态收口

@file src/master/motion_runtime.py
"""

import master.runtime_params as runtime_params


class MotionRuntime:
    """负责保存主车目标和辅车控制序号

    @brief 为应用层提供状态写回和序号分配能力
    """

    def __init__(self):
        # 最近一次主车目标保存在运行时中, 供状态查询复用
        self.last_target = {"kind": "hold"}
        # 跟随控制序号保持单调递增, 供辅车去重
        self._control_seq = 0
        self.heading_hold_enabled = True
        self.yaw_kp = float(runtime_params.YAW_KP)
        self.yaw_ki = float(runtime_params.YAW_KI)
        self.yaw_i_max = float(runtime_params.YAW_I_MAX)
        self.auto_omega_max = float(runtime_params.AUTO_OMEGA_MAX)
        self.target_heading_deg = 0.0
        self._yaw_integral = 0.0

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

    def update_heading_hold(self, current_heading_deg):
        target = dict(self.last_target)
        if target.get("kind") != "vel":
            return target
        error = self.target_heading_deg - float(current_heading_deg)
        self._yaw_integral += error
        self._yaw_integral = max(
            -self.yaw_i_max, min(self.yaw_i_max, self._yaw_integral)
        )
        omega = error * self.yaw_kp + self._yaw_integral * self.yaw_ki
        updated_target = {
            "kind": target.get("kind", "hold"),
            "vx": float(target.get("vx", 0.0)),
            "vy": float(target.get("vy", 0.0)),
            "omega": max(-self.auto_omega_max, min(self.auto_omega_max, omega)),
        }
        self.last_target = dict(updated_target)
        return updated_target
