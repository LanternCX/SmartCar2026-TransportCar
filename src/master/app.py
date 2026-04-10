"""主车应用编排入口

@file src/master/app.py

负责把主车当前保留的底座运行时收口为单拍入口。
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

    @brief 旧跟随整链已经移除, 这里只负责按节拍推进主车应用本体。
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

    def step(self, now_ms):
        """推进一拍主车运行循环

        @brief 旧跟随输入与转发已经退出主车, 当前只按节拍推进应用本体。
        @param now_ms 当前毫秒时钟
        @return dict
        """

        step_input = {"now_ms": now_ms, "run_motion": True, "cycle_token": object()}
        return self.app.step(step_input)


class MasterApp:
    """负责串联主车自身运行时状态.

    @brief 旧跟随视觉与转发链路已经删除, 这里只保留主车底座快照与动作保持入口。
    """

    def __init__(self, hw_bundle=None):
        self.hw_bundle = hw_bundle
        self.motion_state = None
        self._last_self_target = {"kind": "hold"}
        self._last_self_base_state = {
            "heading_deg": 0.0,
            "yaw_rate_deg_s": 0.0,
            "odom_x": 0.0,
            "odom_y": 0.0,
            "base_ok": 0,
        }
        self.last_result = {"self_base_state": dict(self._last_self_base_state)}
        _debug_print("app_init")

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

    @staticmethod
    def _build_result(base_snapshot):
        heading_deg = float(
            base_snapshot.get("heading_est_deg", base_snapshot.get("heading_deg", 0.0))
        )
        odom = base_snapshot.get("odom")
        if odom is None:
            odom_x = float(base_snapshot.get("odom_x", 0.0))
            odom_y = float(base_snapshot.get("odom_y", 0.0))
        else:
            odom_x = float(odom[0])
            odom_y = float(odom[1])
        return {
            "self_base_state": {
                "heading_deg": heading_deg,
                "yaw_rate_deg_s": float(base_snapshot.get("yaw_rate_deg_s", 0.0)),
                "odom_x": odom_x,
                "odom_y": odom_y,
                "base_ok": 1 if base_snapshot.get("base_ok", 0) else 0,
            }
        }

    def step(self, observation=None):
        """推进一次主车流程.

        @brief 旧跟随整链删除后, 主车单拍只刷新底座状态并维持保持目标。
        @param observation 当前观测字典
        @return dict
        """

        now_ms = None
        cycle_token = None
        run_motion = False
        if isinstance(observation, dict):
            now_ms = observation.get("now_ms")
            cycle_token = observation.get("cycle_token")
            run_motion = bool(observation.get("run_motion", False))

        _ = now_ms
        if run_motion:
            self._ensure_motion_state()

        base_snapshot = self._refresh_self_base_state(cycle_token=cycle_token)
        self_target = self._apply_self_target({"kind": "hold"})
        if run_motion:
            run_motion_cycle(
                self._ensure_motion_state(),
                hw_bundle=self.hw_bundle,
                cycle_token=cycle_token,
            )
        self.last_result = self._build_result(base_snapshot)
        self._last_self_base_state = dict(self.last_result["self_base_state"])
        return dict(self.last_result)
