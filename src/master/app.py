"""主车应用编排入口

@file src/master/app.py

负责把视觉输入、状态判断、底座运行时和辅车输出串成主车单拍主链。
"""

_USE_DIRECT_IMPORTS = globals().get("__package__") in ("", None)


def _debug_print(stage, **payload):
    if not payload:
        print("[master.app] %s" % str(stage))
        return
    parts = []
    for key in sorted(payload):
        parts.append("%s=%s" % (str(key), str(payload[key])))
    print("[master.app] %s | %s" % (str(stage), ", ".join(parts)))


if _USE_DIRECT_IMPORTS:
    from hw.encoders import build_encoder_bundle
    from hw.imu import build_imu_bundle
    from hw.motors import build_motor_bundle
    from hw.uart import build_uart_bundle
    from motion_runtime import (
        apply_motion_target,
        base_chain_ready,
        create_runtime_state,
        run_base_cycle,
        run_motion_cycle,
    )
    from protocol import parse_assistant_state
    from vision.decision import decide_from_observation
    from vision.ingress import VisionIngress
    from vision.state_machine import MarkerStateMachine
else:
    from .hw.encoders import build_encoder_bundle
    from .hw.imu import build_imu_bundle
    from .hw.motors import build_motor_bundle
    from .hw.uart import build_uart_bundle
    from .motion_runtime import (
        apply_motion_target,
        base_chain_ready,
        create_runtime_state,
        run_base_cycle,
        run_motion_cycle,
    )
    from .protocol import parse_assistant_state
    from .vision.decision import decide_from_observation
    from .vision.ingress import VisionIngress
    from .vision.state_machine import MarkerStateMachine


def build_hw_bundle():
    """构造主车硬件装配入口.

    @brief 当前阶段先收口已存在的新框架硬件边界对象。
    @return dict
    """

    bundle = {
        "uart": build_uart_bundle(),
        "motors": build_motor_bundle(),
        "encoders": build_encoder_bundle(),
        "imu": build_imu_bundle(),
    }
    _debug_print("build_hw_bundle", keys=tuple(sorted(bundle.keys())))
    return bundle


class MasterRuntimeLoop:
    """主车当前主线运行循环.

    @brief 串起双路视觉读入与 UART3 控制输出, 自身不持有底座长期状态。
    """

    def __init__(self, hw_bundle, app=None):
        if app is None:
            app = MasterApp(hw_bundle=hw_bundle)
        app_hw_bundle = self._resolve_app_hw_bundle(app)
        if app_hw_bundle is not hw_bundle:
            raise ValueError("hw_bundle 与 app 必须引用同一套完整装配")
        self.hw_bundle = hw_bundle
        self.uart_bundle = hw_bundle["uart"]
        self.app = app
        self.capture_ticker = None
        _debug_print("runtime_loop_init")

    @staticmethod
    def _resolve_app_hw_bundle(app):
        """确认应用对象暴露唯一硬件装配

        @brief 避免运行循环和应用层各自持有不同硬件 owner。
        @param app 运行循环要接管的应用对象
        @return dict
        """

        motion_state = getattr(app, "motion_state", None)
        state_hw_bundle = getattr(motion_state, "hw_bundle", None)
        app_hw_bundle = getattr(app, "hw_bundle", None)
        bundles = []
        for candidate in (state_hw_bundle, app_hw_bundle):
            if candidate is None:
                continue
            if all(existing is not candidate for existing in bundles):
                bundles.append(candidate)
        if len(bundles) > 1:
            raise ValueError("app 必须暴露唯一 hw_bundle owner")
        if state_hw_bundle is not None:
            return state_hw_bundle
        if app_hw_bundle is not None:
            return app_hw_bundle
        raise ValueError("app 必须暴露唯一 hw_bundle owner")

    def _read_assistant_feedback(self):
        """读取辅车最新状态回包

        @brief 优先复用按行清积压接口, 保证主车决策只消费同拍内最新一条有效状态。
        @return dict | None
        """

        uart3 = self.uart_bundle["uart3"]
        reader = getattr(uart3, "read_latest_line", None)
        if reader is not None:
            return reader(transform=parse_assistant_state)

        latest_state = None
        while True:
            line = uart3.read_line()
            if not line:
                return latest_state
            parsed = parse_assistant_state(line)
            if parsed is not None:
                latest_state = parsed

    def step(self, now_ms):
        """推进一拍主车运行循环

        @brief 读取辅车回包与双路视觉输入, 然后把单拍观测交给应用层产出控制结果。
        @param now_ms 当前毫秒时钟
        @return dict
        """

        # 先收口辅车最新状态, 避免后续控制决策混入过期回包
        assistant_feedback = self._read_assistant_feedback()
        observations = []
        for uart_name in ("uart6", "uart8"):
            uart_port = self.uart_bundle[uart_name]
            reader = getattr(uart_port, "read_latest_line", None)
            if reader is None:
                reader = uart_port.read_line
            line = reader()
            if line:
                observations.append({"uart": uart_name, "line": line})

        # 把同拍输入装成统一结构后再交给应用层, 保证决策上下文只来自当前这一拍
        step_input = {"now_ms": now_ms, "run_motion": True, "cycle_token": object()}
        if assistant_feedback is not None:
            step_input["assistant_feedback"] = assistant_feedback
        if observations:
            step_input["observations"] = observations
        result = self.app.step(step_input)
        self.uart_bundle["uart3"].write_line(result["assistant_command"])
        return result


class MasterApp:
    """负责串联视觉输入、决策输出和运行时状态.

    @brief 对外提供主车流程的单步推进入口, 视觉状态机只负责阶段切换, 底座状态由过程式状态容器承接。
    """

    def __init__(
        self,
        active_uart="uart6",
        reserved_uarts=("uart8",),
        hw_bundle=None,
    ):
        self.hw_bundle = hw_bundle
        self.ingress = VisionIngress(
            active_uart=active_uart,
            reserved_uarts=reserved_uarts,
        )
        self.state_machine = MarkerStateMachine()
        # 运行态首次需要推进底座时才创建, 避免纯逻辑测试被硬件依赖绑死
        self.motion_state = None
        # 控制序号跟随每拍输出递增, 供辅车忽略重复控制报文
        self._control_seq = 0
        # 状态机无新输入时沿用上一拍输出, 保持阶段结论稳定
        self._last_state_output = {"phase": "MARKER_MISSING", "hold": True}
        self._last_has_target = False
        self.last_assistant_command = ""
        self._last_self_target = {"kind": "hold"}
        # 底座快照作为应用层默认回包骨架, 目标暂失时仍能对外给出稳定状态
        self._last_self_base_state = {
            "heading_deg": 0.0,
            "yaw_rate_deg_s": 0.0,
            "odom_x": 0.0,
            "odom_y": 0.0,
            "base_ok": 0,
        }
        self._last_assistant_feedback = None
        self.last_result = {
            "selected_target": "idle",
            "phase": "MARKER_MISSING",
            "active_uart": active_uart,
            "reserved_uarts": tuple(reserved_uarts),
            "self_target": {"kind": "hold"},
            "self_base_state": dict(self._last_self_base_state),
            "assistant_feedback": None,
            "assistant_command": "",
        }
        _debug_print("app_init")

    def _next_control_seq(self):
        self._control_seq += 1
        return self._control_seq

    def _ensure_motion_state(self):
        if self.motion_state is None:
            self.motion_state = create_runtime_state(hw_bundle=self.hw_bundle)
            _debug_print("motion_state_created")
        return self.motion_state

    def _apply_self_target(self, target):
        prepared_target = dict(target)
        if str(prepared_target.get("kind", "hold")) == "vel":
            self._last_self_target = apply_motion_target(
                self._ensure_motion_state(),
                prepared_target,
            )
        else:
            self._last_self_target = {"kind": "hold"}
            if self.motion_state is not None:
                apply_motion_target(self.motion_state, self._last_self_target)
        return dict(self._last_self_target)

    def _refresh_self_base_state(self, cycle_token=None):
        if self.motion_state is None:
            snapshot = dict(self._last_self_base_state)
            snapshot["base_ok"] = 1 if base_chain_ready(self.hw_bundle) else 0
            return snapshot
        return run_base_cycle(
            self.motion_state,
            hw_bundle=self.hw_bundle,
            cycle_token=cycle_token,
        )

    def step(self, observation=None):
        """推进一次主车流程.

        @brief 串起视觉输入、状态判断和二维跟随决策。
        @param observation 当前观测字典
        @return dict
        """

        # 先拆出当前拍调度字段, 视觉观测本体继续交给 ingress 统一整理
        now_ms = None
        cycle_token = None
        run_motion = False
        prepared_observation = observation
        observation_items = None
        if isinstance(observation, dict):
            now_ms = observation.get("now_ms")
            cycle_token = observation.get("cycle_token")
            run_motion = bool(observation.get("run_motion", False))
            if "assistant_feedback" in observation:
                self._last_assistant_feedback = observation["assistant_feedback"]
            if "observations" in observation:
                observation_items = observation.get("observations") or ()
                prepared_observation = None
            else:
                payload_keys = []
                for key in observation:
                    if key not in (
                        "now_ms",
                        "cycle_token",
                        "run_motion",
                        "assistant_feedback",
                    ):
                        payload_keys.append(key)
                if not payload_keys:
                    prepared_observation = None
                elif len(payload_keys) == len(observation):
                    prepared_observation = observation
                else:
                    prepared_observation = {}
                    for key in payload_keys:
                        prepared_observation[key] = observation[key]

        # 需要执行底座控制时, 先确保运行态 owner 已经装配完成
        if run_motion:
            self._ensure_motion_state()

        # 每拍先刷新底座观测, 这样后续决策总能拿到同一时刻的姿态与里程
        base_snapshot = self._refresh_self_base_state(cycle_token=cycle_token)

        # 把双路视觉输入收口成当前应该使用的一份目标观测
        self.ingress.begin_frame(now_ms=now_ms)
        if observation_items is not None:
            for item in observation_items:
                self.ingress.prepare_observation(item, now_ms=now_ms)
        else:
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
        selected.update(base_snapshot)
        selected["control_seq"] = self._next_control_seq()

        # 状态机结论与底座快照拼好后再做控制决策, 保证主辅车输出来自同一拍上下文
        decision = decide_from_observation(selected)
        self._last_self_base_state = dict(decision.self_base_state)
        self_target = self._apply_self_target(decision.self_target)
        if run_motion:
            # 只有运行态拍才真正推进电机控制, 纯逻辑拍只更新目标与快照
            run_motion_cycle(
                self._ensure_motion_state(),
                hw_bundle=self.hw_bundle,
                cycle_token=cycle_token,
            )
        self.last_assistant_command = decision.assistant_command
        active_uart = str(selected_observation.get("source_uart", "")).strip()
        if not active_uart:
            active_uart = str(
                selected_observation.get("configured_uart", self.ingress.active_uart)
            )

        # 对外结果只保留 review 和联调需要的关键骨架字段
        self.last_result = {
            "selected_target": decision.selected_target,
            "phase": decision.phase,
            "active_uart": active_uart,
            "reserved_uarts": selected_observation.get("reserved_uarts"),
            "self_target": self_target,
            "self_base_state": dict(self._last_self_base_state),
            "assistant_state": decision.assistant_state,
            "assistant_feedback": self._last_assistant_feedback,
            "assistant_command": self.last_assistant_command,
        }
        return dict(self.last_result)
