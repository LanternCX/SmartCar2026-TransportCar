"""命令会话状态与路由后处理."""

import math


class CommandSession:
    """命令状态唯一拥有者, 负责锁定与相对意图收口."""

    def __init__(self) -> None:
        self.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self.command_lock = False
        self.lock_start_time = 0
        self.rear_only_mode = False
        self.last_rear_mode = False
        self.pending_dx = None  # type: float | None
        self.pending_dy = None  # type: float | None
        self.pending_d_angle = None  # type: float | None
        self.rear_mode_changed = False

    def reset_runtime_state(self) -> None:
        """复位命令态, 清空锁定、目标和暂存意图."""
        self.last_cmd = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self.command_lock = False
        self.lock_start_time = 0
        self.rear_only_mode = False
        self.last_rear_mode = False
        self.pending_dx = None
        self.pending_dy = None
        self.pending_d_angle = None
        self.rear_mode_changed = False

    def set_rear_mode(self, enabled: bool) -> None:
        """设置后轮模式并记录本次是否发生切换."""
        new_mode = bool(enabled)
        self.rear_mode_changed = new_mode != self.rear_only_mode
        self.rear_only_mode = new_mode

    def clear_pending_relative(self) -> None:
        """清空相对位移与相对角度暂存."""
        self.pending_dx = None
        self.pending_dy = None
        self.pending_d_angle = None

    def finalize_route(
        self,
        dispatched,
        heading_target: float,
        odom_x: float,
        odom_y: float,
        heading_est: float,
        now_ms: int,
    ) -> bool:
        """在一次路由结束后收敛相对意图与锁定语义.

        返回:
            True 表示本次仍处于速度模式, 调用方可继续做即时逆解回显
        """
        if "reset" in dispatched:
            return False

        if self.command_lock:
            self.clear_pending_relative()
            self.rear_mode_changed = False
            return False

        is_pos_cmd = False
        if self.pending_d_angle is not None:
            self.last_cmd["angle"] = heading_target + self.pending_d_angle
            self.pending_d_angle = None
            is_pos_cmd = True

        if self.pending_dx is not None or self.pending_dy is not None:
            dx_body = self.pending_dx if self.pending_dx is not None else 0.0
            dy_body = self.pending_dy if self.pending_dy is not None else 0.0
            theta_rad = math.radians(heading_est)
            cos_t = math.cos(theta_rad)
            sin_t = math.sin(theta_rad)
            self.last_cmd["x"] = odom_x + dx_body * cos_t - dy_body * sin_t
            self.last_cmd["y"] = odom_y + dx_body * sin_t + dy_body * cos_t
            self.last_cmd.pop("vx", None)
            self.last_cmd.pop("vy", None)
            self.pending_dx = None
            self.pending_dy = None
            is_pos_cmd = True

        if not is_pos_cmd:
            is_pos_cmd = (
                "x" in dispatched
                or "y" in dispatched
                or "angle" in dispatched
                or "yaw" in dispatched
            )

        rear_mode_changed = self.rear_mode_changed
        self.rear_mode_changed = False
        if is_pos_cmd or rear_mode_changed:
            if not self.command_lock:
                self.command_lock = True
                self.lock_start_time = int(now_ms)
        else:
            self.command_lock = False

        self.last_rear_mode = self.rear_only_mode
        return not is_pos_cmd
