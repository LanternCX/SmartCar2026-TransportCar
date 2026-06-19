"""Play 执行上下文."""


class PlayContext:
    """把运行时动作接口收敛为受限 Play 上下文."""

    def __init__(
        self,
        set_position_x=None,
        set_position_y=None,
        set_angle=None,
        write_velocity_x=None,
        write_velocity_y=None,
        write_omega=None,
        is_position_x_done=None,
        is_position_y_done=None,
        is_angle_done=None,
        yellow_line_ready=None,
        clear_yellow_line_ready=None,
        enable_yellow_line_ready_gate=None,
        disable_yellow_line_ready_gate=None,
    ):
        self._set_position_x = set_position_x
        self._set_position_y = set_position_y
        self._set_angle = set_angle
        self._write_velocity_x = write_velocity_x
        self._write_velocity_y = write_velocity_y
        self._write_omega = write_omega
        self._is_position_x_done = is_position_x_done
        self._is_position_y_done = is_position_y_done
        self._is_angle_done = is_angle_done
        self._yellow_line_ready = yellow_line_ready
        self._clear_yellow_line_ready = clear_yellow_line_ready
        self._enable_yellow_line_ready_gate = enable_yellow_line_ready_gate
        self._disable_yellow_line_ready_gate = disable_yellow_line_ready_gate

    def set_position_x(self, value):
        if self._set_position_x is None:
            raise RuntimeError("set_position_x is not available")
        self._set_position_x(value)

    def set_position_y(self, value):
        if self._set_position_y is None:
            raise RuntimeError("set_position_y is not available")
        self._set_position_y(value)

    def set_angle(self, value):
        if self._set_angle is None:
            raise RuntimeError("set_angle is not available")
        self._set_angle(value)

    def write_velocity_x(self, value):
        if self._write_velocity_x is None:
            raise RuntimeError("write_velocity_x is not available")
        self._write_velocity_x(value)

    def write_velocity_y(self, value):
        if self._write_velocity_y is None:
            raise RuntimeError("write_velocity_y is not available")
        self._write_velocity_y(value)

    def write_omega(self, value):
        if self._write_omega is None:
            raise RuntimeError("write_omega is not available")
        self._write_omega(value)

    def is_position_x_done(self):
        if self._is_position_x_done is None:
            return False
        return bool(self._is_position_x_done())

    def is_position_y_done(self):
        if self._is_position_y_done is None:
            return False
        return bool(self._is_position_y_done())

    def is_angle_done(self):
        if self._is_angle_done is None:
            return False
        return bool(self._is_angle_done())

    def yellow_line_ready(self):
        if self._yellow_line_ready is None:
            return False
        return bool(self._yellow_line_ready())

    def clear_yellow_line_ready(self):
        if self._clear_yellow_line_ready is None:
            return
        self._clear_yellow_line_ready()

    def enable_yellow_line_ready_gate(self):
        if self._enable_yellow_line_ready_gate is None:
            return
        self._enable_yellow_line_ready_gate()

    def disable_yellow_line_ready_gate(self):
        if self._disable_yellow_line_ready_gate is None:
            return
        self._disable_yellow_line_ready_gate()
