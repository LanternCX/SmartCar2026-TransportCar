class LowPassFilter:
    """Single-pole IIR low-pass filter.

    new_state = (1 - alpha) * prev + alpha * new
    Default alpha=0.3 matches previous setup (old 0.7, new 0.3).
    """

    def __init__(self, alpha=0.3, initial=None):
        self.alpha = alpha
        self.state = initial

    def reset(self, value=None):
        self.state = value

    def update(self, new_val):
        if self.state is None:
            self.state = new_val
        else:
            self.state = (1 - self.alpha) * self.state + self.alpha * new_val
        return self.state
