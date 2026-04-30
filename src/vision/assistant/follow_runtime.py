"""辅车角色运行时主体

@file src/vision/assistant/follow_runtime.py
"""

from vision.assistant.diagnostics import build_follow_snapshot
from vision.assistant.velocity_packet import (
    CONSUME_ACCEPTED,
    CONSUME_INVALID,
    split_velocity_line,
)
from vision.serial_protocol import format_ack_packet, is_newer_seq, parse_short_packet


def _default_now_ms() -> int:
    """读取毫秒时间

    @return 当前毫秒时间戳
    """

    import time

    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


class AssistantFollowRuntime:
    """基于共享底盘装配辅车角色运行时外观

    在共享底盘外层接管 UART8 前馈输入、UART6 视觉输入与角色层诊断
    """

    def __init__(self, now_ms=None, uart6=None, uart8=None) -> None:
        from core.runtime import TransportCar

        car = TransportCar()
        self._transport_car = car
        self.wheel_states = car.wheel_states
        self.imu = car.imu
        self._now_ms = now_ms or _default_now_ms
        self._last_error_text = "none"
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
        self.sync_context = None
        self._last_sync_seq = None
        self._sync_apply_count = 0
        self._ensure_uart_ready()

    def mark_tick(self, tick=None) -> None:
        """转发 ticker 中断标记"""

        self._transport_car.mark_tick(tick)

    def set_ticker(self, ticker_obj: object) -> None:
        """转发 ticker 对象"""

        self._transport_car.set_ticker(ticker_obj)

    def step(self) -> bool:
        """执行一拍辅车角色运行时"""

        try:
            self._run_role_cycle()
        except Exception as exc:
            self._record_error("role_cycle failed", exc)
        return self._transport_car.step()

    def _run_role_cycle(self) -> None:
        """执行角色层单拍流程"""

        self._process_input("uart6")
        self._process_input("uart8")
        self._write_effective_velocity()

    def build_follow_snapshot(self) -> dict:
        """返回辅车角色层最小诊断快照"""

        return build_follow_snapshot(
            self._build_transport_command_snapshot(),
            self._inputs["uart6"]["status"],
            self._inputs["uart8"]["status"],
            self._build_velocity_snapshot("uart6"),
            self._build_velocity_snapshot("uart8"),
            self._last_error_text,
        )

    def _ensure_uart_ready(self) -> None:
        """确保 UART 实例已就绪"""

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
        """处理指定来源的输入数据"""

        state = self._inputs[source]
        uart = state["uart"]
        if uart is None:
            state["status"] = self._resolve_input_status(source)
            return False

        buf_len = uart.any()
        if not buf_len:
            state["status"] = self._resolve_input_status(source)
            return False

        has_velocity = False

        try:
            state["buffer"] += uart.read(buf_len).decode()
        except UnicodeDecodeError as exc:
            state["status"] = "error"
            self._record_error("%s decode failed" % source, exc)
            return False
        except Exception as exc:
            state["status"] = "error"
            self._record_error("%s read failed" % source, exc)
            return False

        while True:
            idx = state["buffer"].find("\n")
            if idx == -1:
                state["status"] = self._resolve_input_status(source)
                return has_velocity
            line = state["buffer"][:idx].rstrip("\r").strip()
            state["buffer"] = state["buffer"][idx + 1 :]
            if source == "uart8" and self._handle_sync_packet(line, uart):
                state["status"] = self._resolve_input_status(source)
                continue
            consume_result, parsed = split_velocity_line(line)
            if consume_result == CONSUME_ACCEPTED and parsed is not None:
                state["velocity"] = self._normalize_input_velocity(source, parsed)
                state["status"] = "active"
                has_velocity = True
            elif consume_result == CONSUME_INVALID:
                state["status"] = "invalid"
            else:
                state["status"] = self._resolve_input_status(source)

    def _handle_sync_packet(self, line: str, uart) -> bool:
        packet = parse_short_packet(line)
        if packet is None or packet.get("type") != "s":
            return False
        seq = int(packet["seq"])
        if self._last_sync_seq is None or is_newer_seq(seq, self._last_sync_seq):
            self.sync_context = {
                "seq": seq,
                "state": int(packet["state"]),
                "target": int(packet["target"]),
                "arg": int(packet["arg"]),
            }
            self._last_sync_seq = seq
            self._sync_apply_count += 1
        uart.write("%s\r\n" % format_ack_packet(seq))
        return True

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
        self._last_error_text = "%s: %s" % (prefix, exc)
        self._transport_car.last_exception_text = self._last_error_text

    def _write_effective_velocity(self) -> None:
        """将融合后的有效速度写入共享底盘"""

        uart6_velocity = self._inputs["uart6"]["velocity"]
        uart8_velocity = self._inputs["uart8"]["velocity"]
        if uart6_velocity is None and uart8_velocity is None:
            return
        if uart6_velocity is None:
            uart6_velocity = {"vx": 0.0, "vy": 0.0, "omega": 0.0, "has_omega": False}
        if uart8_velocity is None:
            uart8_velocity = {"vx": 0.0, "vy": 0.0, "omega": 0.0, "has_omega": False}

        vx = float(uart6_velocity.get("vx", 0.0)) + float(uart8_velocity.get("vx", 0.0))
        vy = float(uart6_velocity.get("vy", 0.0)) + float(uart8_velocity.get("vy", 0.0))
        omega = 0.0
        if uart8_velocity.get("has_omega"):
            omega = float(uart8_velocity.get("omega", 0.0))
        self._apply_effective_velocity(vx, vy, omega, bool(uart8_velocity.get("has_omega")))

    def _apply_effective_velocity(self, vx: float, vy: float, omega: float, has_omega: bool) -> None:
        self._transport_car.handle_velocity_packet(
            vx,
            vy,
            omega,
            source="assistant",
            has_omega=has_omega,
        )

    @staticmethod
    def _normalize_input_velocity(source: str, parsed: dict) -> dict:
        velocity = {
            "vx": float(parsed.get("vx", 0.0)),
            "vy": float(parsed.get("vy", 0.0)),
            "omega": 0.0,
            "has_omega": False,
        }
        if source == "uart8":
            velocity["omega"] = float(parsed.get("omega", 0.0))
            velocity["has_omega"] = bool(parsed.get("has_omega"))
        return velocity

    def _build_transport_command_snapshot(self) -> dict:
        return dict(self._transport_car.control_state)

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
    """创建辅车角色运行时对象"""

    return AssistantFollowRuntime()
