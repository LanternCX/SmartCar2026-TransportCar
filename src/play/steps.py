"""Play 步骤定义。"""


class _BaseStep:
    def __init__(self, on_enter=None, on_exit=None):
        self.state = "pending"
        self._entered = False
        self._on_enter = on_enter
        self._on_exit = on_exit

    def _enter(self, ctx):
        if self._on_enter is not None:
            self._on_enter(ctx)

    def _enter_once(self, ctx):
        if self._entered:
            return
        self._enter(ctx)
        self._entered = True

    def _exit(self, ctx):
        if self._on_exit is not None:
            self._on_exit(ctx)

    def _finish(self, ctx):
        self._exit(ctx)
        self.state = "finished"
        return "finished"


class PositionXStep(_BaseStep):
    def __init__(self, target, max_speed_cmd=None, on_enter=None, on_exit=None):
        super().__init__(on_enter=on_enter, on_exit=on_exit)
        self.target = float(target)
        self.max_speed_cmd = None if max_speed_cmd is None else float(max_speed_cmd)

    def _enter(self, ctx):
        super()._enter(ctx)
        ctx.set_position_x(self.target, self.max_speed_cmd)

    def tick(self, ctx):
        self._enter_once(ctx)
        if ctx.is_position_x_done():
            return self._finish(ctx)
        self.state = "waiting"
        return "waiting"


class PositionYStep(_BaseStep):
    def __init__(self, target, max_speed_cmd=None, on_enter=None, on_exit=None):
        super().__init__(on_enter=on_enter, on_exit=on_exit)
        self.target = float(target)
        self.max_speed_cmd = None if max_speed_cmd is None else float(max_speed_cmd)

    def _enter(self, ctx):
        super()._enter(ctx)
        ctx.set_position_y(self.target, self.max_speed_cmd)

    def tick(self, ctx):
        self._enter_once(ctx)
        if ctx.is_position_y_done():
            return self._finish(ctx)
        self.state = "waiting"
        return "waiting"


class AngleStep(_BaseStep):
    def __init__(self, target, on_enter=None, on_exit=None):
        super().__init__(on_enter=on_enter, on_exit=on_exit)
        self.target = float(target)

    def _enter(self, ctx):
        super()._enter(ctx)
        ctx.set_angle(self.target)

    def tick(self, ctx):
        self._enter_once(ctx)
        if ctx.is_angle_done():
            return self._finish(ctx)
        self.state = "waiting"
        return "waiting"


class VelocityXStep(_BaseStep):
    def __init__(self, speed, until=None, on_enter=None, on_exit=None):
        super().__init__(on_enter=on_enter, on_exit=on_exit)
        self.speed = float(speed)
        self.until = until

    def tick(self, ctx):
        self._enter_once(ctx)
        ctx.write_velocity_x(self.speed)
        if self.until is None:
            self.state = "holding"
            return "holding"
        if self.until(ctx):
            return self._finish(ctx)
        self.state = "running"
        return "running"
class VelocityYStep(_BaseStep):
    def __init__(self, speed, until=None, on_enter=None, on_exit=None):
        super().__init__(on_enter=on_enter, on_exit=on_exit)
        self.speed = float(speed)
        self.until = until

    def tick(self, ctx):
        self._enter_once(ctx)
        ctx.write_velocity_y(self.speed)
        if self.until is None:
            self.state = "holding"
            return "holding"
        if self.until(ctx):
            return self._finish(ctx)
        self.state = "running"
        return "running"


class VelocityWStep(_BaseStep):
    def __init__(self, speed, until=None, on_enter=None, on_exit=None):
        super().__init__(on_enter=on_enter, on_exit=on_exit)
        self.speed = float(speed)
        self.until = until

    def tick(self, ctx):
        self._enter_once(ctx)
        ctx.write_omega(self.speed)
        if self.until is None:
            self.state = "holding"
            return "holding"
        if self.until(ctx):
            return self._finish(ctx)
        self.state = "running"
        return "running"
