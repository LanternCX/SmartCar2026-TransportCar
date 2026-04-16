"""辅车速度融合与最小状态机理

@file src/vision/assistant/velocity_fusion.py
"""

# 没有任何有效输入时, 角色层输出零速度
STATE_IDLE = "idle"
# 控制协议和视觉观测同时有效, 按正式跟随输出
STATE_TRACKING = "tracking"
# 只剩视觉观测时按降级速度纠偏
STATE_VISION_ONLY = "vision_only"
# 视觉失效时立即停下, 避免盲跑
STATE_FAULT_STOP = "fault_stop"


class FusionResult:
    """统一的融合输出结果

    @brief 同时携带状态、最终输出和两路贡献, 便于角色层诊断
    """

    __slots__ = (
        "state",
        "vx",
        "vy",
        "omega",
        "control_contribution",
        "vision_contribution",
    )

    def __init__(
        self,
        state: str,
        vx: float,
        vy: float,
        omega: float,
        control_contribution: dict,
        vision_contribution: dict,
    ) -> None:
        self.state = state
        self.vx = vx
        self.vy = vy
        self.omega = omega
        self.control_contribution = control_contribution
        self.vision_contribution = vision_contribution


class VelocityFusion:
    """把控制协议速度量与视觉观测合成为统一速度目标

    @brief 控制协议给节奏, 视觉输入负责本地纠偏
    """

    __slots__ = ("_output_limit", "_degraded_output_limit")

    def __init__(self, output_limit: float, degraded_output_limit: float) -> None:
        self._output_limit = abs(float(output_limit))
        self._degraded_output_limit = abs(float(degraded_output_limit))

    def fuse(self, control: object, vision: object) -> FusionResult:
        # 先拆出两路贡献, 这样状态切换和诊断都能共用同一份表达
        control_contribution = self._build_control_contribution(control)
        vision_contribution = self._build_vision_contribution(vision)

        if control is None and vision is None:
            return FusionResult(
                state=STATE_IDLE,
                vx=0.0,
                vy=0.0,
                omega=0.0,
                control_contribution=control_contribution,
                vision_contribution=vision_contribution,
            )

        if vision is None:
            # 没有视觉锚点时直接收口为停下
            return FusionResult(
                state=STATE_FAULT_STOP,
                vx=0.0,
                vy=0.0,
                omega=0.0,
                control_contribution=control_contribution,
                vision_contribution=vision_contribution,
            )

        if control is None:
            # 只剩视觉时保留保守纠偏, omega 固定为 0
            return FusionResult(
                state=STATE_VISION_ONLY,
                vx=self._clamp(vision_contribution["vx"], self._degraded_output_limit),
                vy=self._clamp(vision_contribution["vy"], self._degraded_output_limit),
                omega=0.0,
                control_contribution=control_contribution,
                vision_contribution=vision_contribution,
            )

        # 正常跟随时由控制协议决定节奏, 视觉在车体系内补本地修正量
        return FusionResult(
            state=STATE_TRACKING,
            vx=self._clamp(
                control_contribution["vx"] + vision_contribution["vx"],
                self._output_limit,
            ),
            vy=self._clamp(
                control_contribution["vy"] + vision_contribution["vy"],
                self._output_limit,
            ),
            omega=self._clamp(control_contribution["omega"], self._output_limit),
            control_contribution=control_contribution,
            vision_contribution=vision_contribution,
        )

    @staticmethod
    def _build_control_contribution(control: object) -> dict:
        if control is None:
            return {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        return {
            "vx": float(getattr(control, "vx")),
            "vy": float(getattr(control, "vy")),
            "omega": float(getattr(control, "omega")),
        }

    @staticmethod
    def _build_vision_contribution(vision: object) -> dict:
        if vision is None:
            return {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        return {
            "vx": float(getattr(vision, "x")),
            "vy": float(getattr(vision, "y")),
            "omega": 0.0,
        }

    @staticmethod
    def _clamp(value: float, limit: float) -> float:
        if value > limit:
            return limit
        if value < -limit:
            return -limit
        return value
