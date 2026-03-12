"""视觉状态机调试事件与输出辅助."""

from vision.state_registry import vision_state_registry


class VisionTransitionEvent:
    """视觉状态迁移事件."""

    def __init__(
        self,
        old_state,
        transition,
        stable_counter,
        observation_x=None,
        observation_y=None,
        heading_deg=None,
        odom_x=None,
        odom_y=None,
        now_ms=None,
    ):
        """保存状态迁移调试上下文."""
        self.old_state = vision_state_registry.coerce_state(old_state)
        self.transition = transition
        self.stable_counter = int(stable_counter)
        self.observation_x = observation_x
        self.observation_y = observation_y
        self.heading_deg = heading_deg
        self.odom_x = odom_x
        self.odom_y = odom_y
        self.now_ms = now_ms

    @property
    def new_state(self):
        """兼容旧接口,返回目标状态对象."""
        return self.transition.state

    @property
    def reason(self):
        """兼容旧接口,返回迁移原因标识."""
        return self.transition.reason


def build_transition_event(
    old_state,
    stable_counter,
    transition=None,
    new_state=None,
    reason=None,
    observation_x=None,
    observation_y=None,
    heading_deg=None,
    odom_x=None,
    odom_y=None,
    now_ms=None,
):
    """构造视觉状态迁移事件."""
    if transition is None:
        transition = vision_state_registry.build_transition(new_state, reason)
    return VisionTransitionEvent(
        old_state=old_state,
        transition=transition,
        stable_counter=stable_counter,
        observation_x=observation_x,
        observation_y=observation_y,
        heading_deg=heading_deg,
        odom_x=odom_x,
        odom_y=odom_y,
        now_ms=now_ms,
    )


def format_transition_event(event):
    """将视觉状态迁移事件格式化为单行调试文本."""
    parts = [
        "VSM TRANS %s->%s" % (event.old_state.name, event.new_state.name),
        "reason=%s" % vision_state_registry.get_reason_name(event.reason),
        "stable=%d" % event.stable_counter,
    ]
    if event.observation_x is not None and event.observation_y is not None:
        parts.append("obs=(%.1f,%.1f)" % (event.observation_x, event.observation_y))
    if event.heading_deg is not None:
        parts.append("hdg=%.1f" % event.heading_deg)
    if event.odom_x is not None and event.odom_y is not None:
        parts.append("odom=(%.3f,%.3f)" % (event.odom_x, event.odom_y))
    if event.now_ms is not None:
        parts.append("now=%d" % int(event.now_ms))
    return " ".join(parts)


def build_uart_debug_sink(write_line):
    """根据行写入函数构造视觉调试 sink."""

    def sink(event):
        """格式化并输出单条视觉调试事件."""
        write_line(format_transition_event(event))

    return sink


def build_logger_debug_sink(logger):
    """根据全局 logger 构造视觉调试 sink."""

    def sink(event):
        """通过结构化日志输出单条视觉调试事件."""
        logger.info(format_transition_event(event))

    return sink
