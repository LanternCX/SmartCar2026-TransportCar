"""主车应用编排入口

@file src/master/app.py
"""

from master.hw.encoders import build_encoder_bundle
from master.hw.imu import build_imu_bundle
from master.hw.motors import build_motor_bundle
from master.hw.uart import build_uart_bundle
from master.motion_runtime import MotionRuntime
from master.vision.decision import decide_from_observation
from master.vision.ingress import VisionIngress
from master.vision.state_machine import MarkerStateMachine


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
        self.app = app or MasterApp(uart_bundle=uart_bundle)

    def step(self, now_ms):
        last_result = None
        for uart_name in ("uart6", "uart8"):
            line = self.uart_bundle[uart_name].read_line()
            if line:
                last_result = self.app.step(
                    {"uart": uart_name, "line": line, "now_ms": now_ms}
                )

        if last_result is not None:
            self.uart_bundle["uart3"].write_line(last_result["assistant_command"])
            return last_result

        result = self.app.step({"now_ms": now_ms})
        self.uart_bundle["uart3"].write_line(result["assistant_command"])
        return result


class MasterApp:
    """负责串联视觉输入、决策输出和运行时状态.

    @brief 对外提供主车流程的单步推进入口。
    """

    def __init__(
        self,
        active_uart="uart6",
        reserved_uarts=("uart8",),
        hw_bundle=None,
        uart_bundle=None,
    ):
        if hw_bundle is not None and uart_bundle is not None:
            if hw_bundle.get("uart") is not uart_bundle:
                raise ValueError("hw_bundle 与 uart_bundle 必须引用同一套串口装配")
        elif hw_bundle is None:
            if uart_bundle is None:
                hw_bundle = build_hw_bundle()
            else:
                hw_bundle = {"uart": uart_bundle}

        self.hw_bundle = hw_bundle
        self.ingress = VisionIngress(
            active_uart=active_uart,
            reserved_uarts=reserved_uarts,
        )
        self.state_machine = MarkerStateMachine()
        self.motion_runtime = None
        self._control_seq = 0
        self._last_self_target = {"kind": "hold"}
        self._last_state_output = {"phase": "MARKER_MISSING", "hold": True}
        self._last_has_target = False
        self.last_assistant_command = ""
        self.last_result = {
            "selected_target": "idle",
            "phase": "MARKER_MISSING",
            "active_uart": active_uart,
            "reserved_uarts": tuple(reserved_uarts),
            "self_target": {"kind": "hold"},
            "assistant_command": "",
        }

    def _next_control_seq(self):
        if self.motion_runtime is not None:
            return self.motion_runtime.next_control_seq()
        self._control_seq += 1
        return self._control_seq

    def _ensure_motion_runtime(self):
        if self.motion_runtime is None:
            runtime = MotionRuntime()
            runtime._control_seq = self._control_seq
            runtime.last_target = dict(self._last_self_target)
            self.motion_runtime = runtime
        return self.motion_runtime

    def _apply_self_target(self, target):
        prepared_target = dict(target)
        if (
            prepared_target.get("kind", "hold") == "hold"
            and self.motion_runtime is None
        ):
            self._last_self_target = prepared_target
            return dict(self._last_self_target)
        self._last_self_target = self._ensure_motion_runtime().apply_self_target(
            prepared_target
        )
        return dict(self._last_self_target)

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
        has_target = (
            int(selected_observation.get("valid", 0)) == 1
            and int(selected_observation.get("fresh", 0)) == 1
        )
        has_new_input = bool(selected_observation.get("has_new_input", 0))
        if has_new_input or has_target != self._last_has_target:
            self._last_state_output = self.state_machine.step(
                has_target=has_target,
                err_x=float(selected_observation.get("err_x", 0.0)),
                err_y=float(selected_observation.get("err_y", 0.0)),
                has_new_input=has_new_input,
            )
            self._last_has_target = has_target
        state_output = dict(self._last_state_output)

        selected = dict(selected_observation)
        selected.update(state_output)
        selected["control_seq"] = self._next_control_seq()

        decision = decide_from_observation(selected)
        self_target = self._apply_self_target(decision.self_target)
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
