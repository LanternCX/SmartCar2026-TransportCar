"""主车应用编排入口

@file src/master/app.py
"""

try:
    from master.hw.encoders import build_encoder_bundle
    from master.hw.imu import build_imu_bundle
    from master.hw.motors import build_motor_bundle
    from master.hw.uart import build_uart_bundle
    from master.motion_runtime import MotionRuntime
    from master.vision.decision import decide_from_observation
    from master.vision.ingress import VisionIngress
    from master.vision.state_machine import MarkerStateMachine
except ImportError:
    from hw.encoders import build_encoder_bundle
    from hw.imu import build_imu_bundle
    from hw.motors import build_motor_bundle
    from hw.uart import build_uart_bundle
    from motion_runtime import MotionRuntime
    from vision.decision import decide_from_observation
    from vision.ingress import VisionIngress
    from vision.state_machine import MarkerStateMachine


def build_hw_bundle():
    """构造主车硬件装配入口.

    @brief 当前阶段先收口已存在的新框架硬件边界对象。
    @return dict
    """

    return {
        "uart": build_uart_bundle(),
        "motors": build_motor_bundle(),
        "encoders": build_encoder_bundle(),
        "imu": build_imu_bundle(),
    }


class MasterRuntimeLoop:
    """主车当前主线运行循环.

    @brief 串起双路视觉读入与 UART3 控制输出。
    """

    def __init__(self, uart_bundle, app=None):
        self.uart_bundle = uart_bundle
        self.app = app or MasterApp()

    def step(self, now_ms):
        for uart_name in ("uart6", "uart8"):
            line = self.uart_bundle[uart_name].read_line()
            if line:
                result = self.app.step(
                    {"uart": uart_name, "line": line, "now_ms": now_ms}
                )
                self.uart_bundle["uart3"].write_line(result["assistant_command"])
                return result

        result = self.app.step({"now_ms": now_ms})
        self.uart_bundle["uart3"].write_line(result["assistant_command"])
        return result


class MasterApp:
    """负责串联视觉输入、决策输出和运行时状态.

    @brief 对外提供主车流程的单步推进入口。
    """

    def __init__(self, active_uart="uart6", reserved_uarts=("uart8",)):
        self.hw_bundle = build_hw_bundle()
        self.ingress = VisionIngress(
            active_uart=active_uart,
            reserved_uarts=reserved_uarts,
        )
        self.state_machine = MarkerStateMachine()
        self.motion_runtime = MotionRuntime()
        self.last_assistant_command = ""
        self.last_result = {
            "selected_target": "idle",
            "phase": "MARKER_MISSING",
            "active_uart": active_uart,
            "reserved_uarts": tuple(reserved_uarts),
            "self_target": {"kind": "hold"},
            "assistant_command": "",
        }

    def step(self, observation=None):
        """推进一次主车流程.

        @brief 串起视觉输入、状态判断和二维跟随决策。
        @param observation 当前观测字典
        @return dict
        """

        now_ms = None
        prepared_observation = observation
        if isinstance(observation, dict):
            now_ms = observation.get("now_ms")
            prepared_observation = dict(observation)
            prepared_observation.pop("now_ms", None)
            if not prepared_observation:
                prepared_observation = None

        self.ingress.begin_frame(now_ms=now_ms)
        self.ingress.prepare_observation(prepared_observation, now_ms=now_ms)
        selected_observation = self.ingress.select_current_target(now_ms=now_ms)
        state_output = self.state_machine.step(
            has_target=(
                int(selected_observation.get("valid", 0)) == 1
                and int(selected_observation.get("fresh", 0)) == 1
            ),
            err_x=float(selected_observation.get("err_x", 0.0)),
            err_y=float(selected_observation.get("err_y", 0.0)),
            has_new_input=bool(selected_observation.get("has_new_input", 0)),
        )

        selected = dict(selected_observation)
        selected.update(state_output)
        selected["control_seq"] = self.motion_runtime.next_control_seq()

        decision = decide_from_observation(selected)
        self_target = self.motion_runtime.apply_self_target(decision.self_target)
        self.last_assistant_command = decision.assistant_command
        active_uart = str(selected_observation.get("source_uart", "")).strip()
        if not active_uart:
            active_uart = str(
                selected_observation.get("configured_uart", self.ingress.active_uart)
            )

        self.last_result = {
            "selected_target": decision.selected_target,
            "phase": decision.phase,
            "active_uart": active_uart,
            "reserved_uarts": selected_observation.get("reserved_uarts"),
            "self_target": self_target,
            "assistant_state": decision.assistant_state,
            "assistant_command": self.last_assistant_command,
        }
        return dict(self.last_result)
