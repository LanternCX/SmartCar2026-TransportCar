class SpikeMedianFilter:
    """Median filter with fixed small window to suppress spike outliers."""

    def __init__(self, window=3):
        self.window = max(3, int(window) or 3)
        if self.window % 2 == 0:
            self.window += 1  # keep odd window for median
        self.buf = []

    def reset(self, value=None):
        self.buf = [] if value is None else [value] * self.window

    def update(self, new_val):
        if len(self.buf) >= self.window:
            self.buf.pop(0)
        self.buf.append(new_val)
        # simple median of current buffer
        sorted_buf = sorted(self.buf)
        mid = len(sorted_buf) // 2
        return sorted_buf[mid]
