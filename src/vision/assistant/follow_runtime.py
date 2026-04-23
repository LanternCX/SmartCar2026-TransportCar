"""辅车角色运行时主体

@file src/vision/assistant/follow_runtime.py
"""

from vision.assistant.diagnostics import build_follow_snapshot
from vision.assistant.velocity_packet import CONSUME_ACCEPTED, split_velocity_line


def _default_now_ms() -> int:
    """读取毫秒时间

    @brief 同时兼容板端 ticks_ms 和主机测试环境
    """

    import time

    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


def _has_translational_position_target_command(text: str) -> bool:
    for fragment in text.split(","):
        item = fragment.strip()
        if not item or "=" not in item:
            continue
        key = item.split("=", 1)[0].strip().lower()
        if key in ("x", "y", "dx", "dy"):
            return True
    return False


def _has_angular_velocity_fragment(text: str) -> bool:
    for fragment in text.split(","):
        item = fragment.strip()
        if not item or "=" not in item:
            continue
        key = item.split("=", 1)[0].strip().lower()
        if key in ("omega", "w"):
            return True
    return False


class AssistantFollowRuntime:
    """基于共享底盘装配辅车角色运行时外观

    @brief 在共享底盘外层接管 UART8 前馈输入、UART6 视觉输入与角色层诊断
    """

    def __init__(self, now_ms=None, uart6=None, uart8=None) -> None:
        from core.runtime import TransportCar

        # 共享底盘实例
        car = TransportCar()
        self._transport_car = car
        # 轮组状态视图
        self.wheel_states = car.wheel_states
        # IMU 视图
        self.imu = car.imu
        # 角色层毫秒时基
        self._now_ms = now_ms or _default_now_ms
        # 最近一次错误文本
        self._last_error_text = "none"
        # 双路输入状态: UART8 提供前馈, UART6 提供视觉速度
        self._inputs = {
            "uart6": {
                "uart": uart6,
                "buffer": "",
                "status": "idle",
                "velocity": None,
                "factory": "create_uart6",
            },
            "uart8": {
                "uart": uart8,
                "buffer": "",
                "status": "idle",
                "velocity": None,
                "factory": "create_uart8",
            },
        }
        # 只对平移位置透传做保护, 单独角度透传允许继续写回线速度
        self._hold_passthrough_targets = False
        self._ensure_uart_ready()

    def mark_tick(self, tick=None) -> None:
        """转发 ticker 中断标记

        @brief 角色层不改时钟节拍, tick 入口仍由共享底盘处理
        """

        self._transport_car.mark_tick(tick)

    def set_ticker(self, ticker_obj: object) -> None:
        """转发 ticker 对象

        @brief 让共享底盘持有真实的控制周期驱动器
        """

        self._transport_car.set_ticker(ticker_obj)

    def step(self) -> bool:
        """执行一拍辅车角色运行时

        @brief 先跑角色层输入接管与观测记录, 再进入共享底盘的执行周期
        """

        try:
            self._run_role_cycle()
        except Exception as exc:
            self._record_error("role_cycle failed", exc)
        return self._transport_car.step()

    def _run_role_cycle(self) -> None:
        """执行角色层单拍流程

        @brief 这一拍先接管前馈和视觉输入, 再把融合后的速度通过共享底盘入口写回
        """

        uart6_has_velocity, uart6_has_translation_target = self._process_input("uart6")
        uart8_has_velocity, uart8_has_translation_target = self._process_input("uart8")
        if uart8_has_translation_target or uart6_has_translation_target:
            self._hold_passthrough_targets = True
        elif uart8_has_velocity or uart6_has_velocity:
            self._hold_passthrough_targets = False
        self._write_effective_velocity()

    def build_follow_snapshot(self) -> dict:
        """返回辅车角色层最小诊断快照

        @brief 只有外部需要观察时才组织完整字典, 避免控制周期反复分配
        """

        return build_follow_snapshot(
            self._build_transport_command_snapshot(),
            self._inputs["uart6"]["status"],
            self._inputs["uart8"]["status"],
            self._build_velocity_snapshot("uart6"),
            self._build_velocity_snapshot("uart8"),
            self._last_error_text,
        )

    def _ensure_uart_ready(self) -> None:
        uart_bus = None
        try:
            import hardware.uart_bus as uart_bus  # type: ignore
        except Exception:
            uart_bus = None

        for source, state in self._inputs.items():
            if state["uart"] is not None:
                continue
            try:
                if uart_bus is None:
                    raise RuntimeError("uart_bus unavailable")
                factory = getattr(uart_bus, state["factory"])
                state["uart"] = factory()
            except Exception as exc:
                state["status"] = "error"
                self._record_error("%s init failed" % source, exc)
                return

    def _process_input(self, source: str):
        state = self._inputs[source]
        uart = state["uart"]
        if uart is None:
            state["status"] = self._resolve_input_status(source)
            return False, False

        buf_len = uart.any()
        if not buf_len:
            state["status"] = self._resolve_input_status(source)
            return False, False

        has_velocity = False
        has_translation_target_passthrough = False

        try:
            state["buffer"] += uart.read(buf_len).decode()
        except UnicodeDecodeError as exc:
            state["status"] = "error"
            self._record_error("%s decode failed" % source, exc)
            return False, False
        except Exception as exc:
            state["status"] = "error"
            self._record_error("%s read failed" % source, exc)
            return False, False

        while True:
            idx = state["buffer"].find("\n")
            if idx == -1:
                state["status"] = self._resolve_input_status(source)
                return has_velocity, has_translation_target_passthrough
            line = state["buffer"][:idx].rstrip("\r").strip()
            state["buffer"] = state["buffer"][idx + 1 :]
            has_omega_fragment = _has_angular_velocity_fragment(line)
            consume_result, parsed, passthrough_line = split_velocity_line(line)
            if consume_result == CONSUME_ACCEPTED and parsed is not None:
                state["velocity"] = self._normalize_input_velocity(
                    source, parsed, has_omega_fragment
                )
                state["status"] = "active"
                has_velocity = True
            elif consume_result == "invalid":
                state["status"] = "invalid"
            else:
                state["status"] = self._resolve_input_status(source)
            if passthrough_line:
                if _has_translational_position_target_command(passthrough_line):
                    has_translation_target_passthrough = True
                    if consume_result != CONSUME_ACCEPTED:
                        state["velocity"] = None
                self._transport_car._handle_uart_line(passthrough_line, source=source)

    def _resolve_input_status(self, source: str) -> str:
        state = self._inputs[source]
        if state["status"] == "error":
            return "error"
        if state["status"] == "invalid":
            return "invalid"
        if state["velocity"] is not None:
            return "active"
        return "idle"

    def _record_error(self, prefix: str, exc: Exception) -> None:
        # 只保留最近一次错误文本, 方便现场联调判断先出问题的输入来源
        self._last_error_text = "%s: %s" % (prefix, exc)
        self._transport_car.last_exception_text = self._last_error_text

    def _write_effective_velocity(self) -> None:
        if self._should_skip_velocity_write():
            return
        uart6_velocity = self._inputs["uart6"]["velocity"]
        uart8_velocity = self._inputs["uart8"]["velocity"]
        if uart6_velocity is None and uart8_velocity is None:
            return
        if uart6_velocity is None:
            uart6_velocity = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        if uart8_velocity is None:
            uart8_velocity = {"vx": 0.0, "vy": 0.0, "omega": 0.0}

        vx = float(uart6_velocity.get("vx", 0.0)) + float(uart8_velocity.get("vx", 0.0))
        vy = float(uart6_velocity.get("vy", 0.0)) + float(uart8_velocity.get("vy", 0.0))
        omega = None
        if uart8_velocity.get("has_omega"):
            omega = float(uart8_velocity.get("omega", 0.0))
        self._transport_car._handle_uart_line(
            self._format_velocity_command(vx, vy, omega), source="assistant"
        )

    @staticmethod
    def _normalize_input_velocity(source: str, parsed: dict, has_omega_fragment: bool) -> dict:
        velocity = {
            "vx": float(parsed.get("vx", 0.0)),
            "vy": float(parsed.get("vy", 0.0)),
            "omega": 0.0,
            "has_omega": False,
        }
        if source == "uart8":
            velocity["omega"] = float(parsed.get("omega", 0.0))
            velocity["has_omega"] = bool(has_omega_fragment)
        return velocity

    def _should_skip_velocity_write(self) -> bool:
        if not self._hold_passthrough_targets:
            return False

        active_getter = getattr(self._transport_car, "_has_active_translation_target", None)
        if active_getter is not None:
            active = bool(active_getter())
        else:
            last_cmd = self._transport_car.last_cmd
            active = last_cmd.get("x") is not None or last_cmd.get("y") is not None
        if not active:
            self._hold_passthrough_targets = False
            return False
        return True

    @staticmethod
    def _format_velocity_command(vx: float, vy: float, omega) -> str:
        if omega is None:
            return "vx=%s,vy=%s" % (vx, vy)
        return "vx=%s,vy=%s,omega=%s" % (vx, vy, omega)

    def _build_transport_command_snapshot(self) -> dict:
        # 角色层只导出共享底盘当前真实生效的命令状态
        return dict(self._transport_car.last_cmd)

    def _build_velocity_snapshot(self, source: str) -> dict:
        velocity = self._inputs[source]["velocity"]
        if velocity is None:
            return {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        return {
            "vx": float(velocity.get("vx", 0.0)),
            "vy": float(velocity.get("vy", 0.0)),
            "omega": float(velocity.get("omega", 0.0)),
        }


def create_transport_car() -> AssistantFollowRuntime:
    """创建辅车角色运行时对象

    @brief 给角色分发入口返回会进入控制周期的辅车运行时
    """

    return AssistantFollowRuntime()
