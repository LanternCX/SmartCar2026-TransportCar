"""视觉状态与迁移包装注册表."""


class TransitionSpec:
    """目标状态与迁移原因的组合对象."""

    def __init__(self, state, reason):
        """保存目标状态与原因标识."""
        self.state = state
        self.reason = str(reason)


class StateSpec:
    """带有迁移元信息的状态对象."""

    RESET = None
    OBSERVATION_LOST = None
    DONE_HOLD_ELAPSED = None
    UNKNOWN_STATE_GUARD = None
    OBSERVATION_ACQUIRED = None
    ANGLE_ERROR_REENTRY = None
    ANGLE_ALIGNED_STABLE = None
    DISTANCE_NOT_READY = None
    DISTANCE_ALIGNED_STABLE = None
    HEADING_ALIGNED = None
    HEADING_NOT_READY = None
    ENTER_PUSHING = None
    PUSH_DISTANCE_REACHED = None
    RETURN_HEADING_REACHED = None

    def __init__(self, state_id, name):
        """保存状态 ID 与显示名."""
        self.id = int(state_id)
        self.name = str(name)

    def bind(self, attr_name, reason):
        """为当前状态绑定一个可复用的迁移对象."""
        transition = TransitionSpec(self, reason)
        setattr(self, attr_name, transition)
        return transition

    def __eq__(self, other):
        """允许状态对象与整数状态 ID 直接比较."""
        if hasattr(other, "id"):
            return self.id == int(other.id)
        try:
            return self.id == int(other)
        except (TypeError, ValueError):
            return False

    def __int__(self):
        """返回状态 ID,兼容旧接口."""
        return self.id

    def __hash__(self):
        """以状态 ID 作为哈希键."""
        return hash(self.id)

    def __bool__(self):
        """状态对象始终视为真值."""
        return True


class VisionStateRegistry:
    """统一管理视觉状态与迁移原因元信息."""

    def __init__(self):
        """初始化空注册表."""
        self._states = {}

    def register_state(self, state):
        """注册一个状态对象."""
        self._states[int(state)] = state
        return state

    def coerce_state(self, state):
        """将整数或状态对象统一转换为状态对象."""
        if isinstance(state, StateSpec):
            return state
        if hasattr(state, "id"):
            state = state.id
        return self._states.get(int(state))

    def build_transition(self, state, reason):
        """基于状态与原因构造临时迁移对象."""
        coerced_state = self.coerce_state(state)
        return TransitionSpec(coerced_state, reason)

    def get_state_name(self, state_id):
        """返回状态显示名,未知状态返回 UNKNOWN."""
        state = self.coerce_state(state_id)
        if state is None:
            return "UNKNOWN"
        return state.name

    def get_reason_name(self, reason_id):
        """返回迁移原因显示名,未知原因返回 unknown."""
        if reason_id is None:
            return "unknown"
        return str(reason_id)


vision_state_registry = VisionStateRegistry()
