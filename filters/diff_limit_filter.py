class DiffLimitFilter:
    """Clamp per-sample delta to suppress sudden jumps."""

    def __init__(self, max_delta):
        self.max_delta = abs(max_delta) if max_delta is not None else 0.0
        self.prev = None

    def reset(self, value=None):
        self.prev = value

    def update(self, new_val):
        if self.prev is None:
            self.prev = new_val
            return new_val
        if self.max_delta <= 0:
            self.prev = new_val
            return new_val
        lo = self.prev - self.max_delta
        hi = self.prev + self.max_delta
        if new_val < lo:
            new_val = lo
        elif new_val > hi:
            new_val = hi
        self.prev = new_val
        return new_val
