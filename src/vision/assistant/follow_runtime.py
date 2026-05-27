"""辅车角色运行时主体

@file src/vision/assistant/follow_runtime.py
"""

from config import comm as comm_params
from config import motion as motion_params
from config import vision as vision_params
from protocol.link import should_resend, write_reliable_line
from utils.startup_log import log
from vision.clear_phase import CLEAR_PHASE_FORWARD, CLEAR_PHASE_RETREAT
from vision.assistant.state_machine import (
    ASSISTANT_STATE_CLEAR_OBJECT,
    ASSISTANT_STATE_APPROACH_OBJECT,
    ASSISTANT_STATE_FOLLOW,
    ASSISTANT_STATE_ORBIT,
    ASSISTANT_STATE_TRANSPORT_OBJECT,
    ASSISTANT_TARGET_OBJECT,
    AssistantStateMachine,
)
from vision.assistant.diagnostics import build_follow_snapshot
from vision.assistant.uart8_packet import (
    format_ack_packet,
    format_event_packet,
    format_state_sync_packet,
    is_newer_seq,
    parse_short_packet,
)
from vision.assistant.velocity_packet import (
    CONSUME_ACCEPTED,
    CONSUME_INVALID,
    split_velocity_line,
)


_INPUT_LIMIT = getattr(comm_params, "ASSISTANT_UART_INPUT_LIMIT")
_TARGET_FOUND_EVENT = 6
_ALIGNED_EVENT = 7
_CLEARED_EVENT = 9
_LOCAL_VISION_SYNC_RESEND_INTERVAL_MS = getattr(
    comm_params, "ASSISTANT_LOCAL_VISION_SYNC_RESEND_INTERVAL_MS"
)
_MASTER_REPORT_RESEND_INTERVAL_MS = getattr(comm_params, "RELIABLE_RESEND_INTERVAL_MS")
_ASSISTANT_ORBIT_TARGET_DEG = getattr(motion_params, "ASSISTANT_ORBIT_TARGET_DEG")
_ASSISTANT_ORBIT_RADIUS_SCALE = getattr(motion_params, "ASSISTANT_ORBIT_RADIUS_SCALE")
_ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID = getattr(
    vision_params, "ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID"
)
_ASSISTANT_ORBIT_OBJECT_CONFIG_ID = getattr(
    vision_params, "ASSISTANT_ORBIT_OBJECT_CONFIG_ID"
)
ORBIT_VISION_CORRECTION_ENABLED = bool(
    getattr(vision_params, "ORBIT_VISION_CORRECTION_ENABLED")
)
_ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE = getattr(
    vision_params, "ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE"
)
_TRANSPORT_CLEAR_STEP_DISTANCE_M = getattr(motion_params, "TRANSPORT_CLEAR_STEP_DISTANCE_M")
MOTION_STOP_SPEED_THRESHOLD = getattr(motion_params, "MOTION_STOP_SPEED_THRESHOLD")
MOTION_STOP_CONFIRM_TICKS = getattr(motion_params, "MOTION_STOP_CONFIRM_TICKS")


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
        self._state_machine = AssistantStateMachine()
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
        seed_value = int(self._now_ms()) % 256
        self._local_vision_sync_seq = seed_value
        self._pending_local_vision_sync = None
        self._pending_target_found_report = None
        self._approach_target_found_done = False
        self._last_approach_arg = 0
        self._post_orbit_realign_active = False
        self._clear_completed = False
        self._clear_stop_ticks = 0
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
        keep_running = self._transport_car.step()
        try:
            self._finish_clear_if_needed()
            self._send_pending_target_found_report()
        except Exception as exc:
            self._record_error("clear_finish failed", exc)
        try:
            self._resume_approach_after_orbit()
        except Exception as exc:
            self._record_error("post_orbit failed", exc)
        return keep_running

    def _run_role_cycle(self) -> None:
        """执行角色层单拍流程"""

        self._process_input("uart6")
        self._process_input("uart8")
        self._send_pending_local_vision_sync()
        self._send_pending_target_found_report()
        self._write_effective_velocity()

    def build_follow_snapshot(self) -> dict:
        """返回辅车角色层最小诊断快照"""

        return build_follow_snapshot(
            self._state_machine.state,
            self._state_machine.target,
            self._build_transport_command_snapshot(),
            self._inputs["uart6"]["status"],
            self._inputs["uart8"]["status"],
            self._build_velocity_snapshot("uart6"),
            self._build_velocity_snapshot("uart8"),
            self._pending_local_vision_sync is not None,
            self._approach_target_found_done,
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

    def _process_input(self, source: str):
        """处理指定来源的输入数据"""

        state = self._inputs[source]
        uart = state["uart"]
        if uart is None:
            state["status"] = self._resolve_input_status(source)
            return False

        try:
            buf_len = uart.any()
        except Exception as exc:
            state["status"] = "error"
            self._record_error("%s any failed" % source, exc)
            return False
        if not buf_len:
            state["status"] = self._resolve_input_status(source)
            return False

        has_velocity = False

        input_overflow = buf_len > _INPUT_LIMIT
        if input_overflow:
            buf_len = _INPUT_LIMIT

        try:
            state["buffer"] += uart.read(buf_len).decode()
        except Exception as exc:
            state["status"] = "error"
            if exc.__class__.__name__ == "UnicodeDecodeError":
                self._record_error("%s decode failed" % source, exc)
            else:
                self._record_error("%s read failed" % source, exc)
            return False
        handled_valid = False

        while True:
            idx = state["buffer"].find("\n")
            if idx == -1:
                if input_overflow:
                    discarded = self._discard_pending_input(source, uart)
                    state["buffer"] = ""
                    if discarded and not handled_valid:
                        state["status"] = "invalid"
                    return has_velocity
                if len(state["buffer"]) > _INPUT_LIMIT:
                    state["buffer"] = ""
                    state["status"] = "invalid"
                    return has_velocity
                state["status"] = self._resolve_input_status(source)
                return has_velocity
            if idx > _INPUT_LIMIT:
                state["buffer"] = state["buffer"][idx + 1 :]
                state["status"] = "invalid"
                continue
            line = state["buffer"][:idx].rstrip("\r").strip()
            state["buffer"] = state["buffer"][idx + 1 :]
            if source == "uart8" and self._handle_uart8_control_packet(line, uart):
                self._mark_input_valid(source)
                handled_valid = True
                continue
            if source == "uart6" and self._handle_uart6_control_packet(line):
                self._mark_input_valid(source)
                handled_valid = True
                continue
            if self._state_machine.is_idle():
                state["status"] = self._resolve_input_status(source)
                continue
            consume_result, parsed = split_velocity_line(line)
            if consume_result == CONSUME_ACCEPTED and parsed is not None:
                handled_valid = True
                if self._should_store_velocity(source):
                    state["velocity"] = self._normalize_input_velocity(source, parsed)
                    state["status"] = "active"
                    has_velocity = True
                else:
                    self._mark_input_valid(source)
            elif consume_result == CONSUME_INVALID:
                state["status"] = "invalid"
            else:
                state["status"] = self._resolve_input_status(source)

    def _discard_pending_input(self, source: str, uart) -> bool:
        while True:
            try:
                pending = uart.any()
            except Exception as exc:
                self._inputs[source]["status"] = "error"
                self._record_error("%s any failed" % source, exc)
                return False
            if not pending:
                return True
            if pending > _INPUT_LIMIT:
                pending = _INPUT_LIMIT
            try:
                uart.read(pending)
            except Exception as exc:
                self._inputs[source]["status"] = "error"
                self._record_error("%s read failed" % source, exc)
                return False

    def _mark_input_valid(self, source: str) -> None:
        state = self._inputs[source]
        if state["velocity"] is not None:
            state["status"] = "active"
        else:
            state["status"] = "idle"

    def _handle_uart8_control_packet(self, line: str, uart) -> bool:
        if self._handle_sync_packet(line, uart):
            return True
        packet = parse_short_packet(line)
        if packet is None:
            return False
        if packet.get("type") == "a":
            pending = self._pending_target_found_report
            matched = (
                pending is not None
                and pending.get("sent_once")
                and int(packet["seq"]) == int(pending["seq"])
            )
            if (
                matched
            ):
                self._pending_target_found_report = None
            return True
        if packet.get("type") == "r":
            return True
        return False

    def _handle_sync_packet(self, line: str, uart) -> bool:
        packet = parse_short_packet(line)
        if packet is None or packet.get("type") != "s":
            return False
        if "seq" not in packet:
            return False
        seq = int(packet["seq"])
        is_new_sync = self._last_sync_seq is None or is_newer_seq(seq, self._last_sync_seq)
        if not is_new_sync and seq != self._last_sync_seq:
            self._write_forward_reliable_line(format_ack_packet(seq))
            return True
        accepted = self._apply_sync_context(packet)
        if not accepted:
            return True
        if is_new_sync:
            self.sync_context = {
                "seq": seq,
                "state": int(packet["state"]),
                "target": int(packet["target"]),
                "arg": int(packet["arg"]),
            }
            self._last_sync_seq = seq
            self._sync_apply_count += 1
            self._log_master_sync_done(packet)
        self._write_forward_reliable_line(format_ack_packet(seq))
        return True

    def _apply_sync_context(self, packet: dict) -> bool:
        """应用新的 UART8 同步上下文"""

        accepted = self._state_machine.apply_master_state(
            packet["state"], packet["target"], packet["arg"]
        )
        if not accepted:
            self._record_error_text(
                "unknown assistant sync state: %s" % int(packet["state"])
            )
            return False
        if self._state_machine.is_idle():
            self._inputs["uart6"]["velocity"] = None
            self._inputs["uart8"]["velocity"] = None
            self._pending_local_vision_sync = None
            self._pending_target_found_report = None
            self._approach_target_found_done = False
            self._post_orbit_realign_active = False
            self._clear_completed = False
            self._transport_car.handle_velocity_packet(
                0.0,
                0.0,
                0.0,
                source="assistant_idle",
                has_omega=True,
            )
        elif self._state_machine.state == ASSISTANT_STATE_FOLLOW:
            self._inputs["uart6"]["velocity"] = None
            self._inputs["uart8"]["velocity"] = None
            self._pending_target_found_report = None
            self._approach_target_found_done = False
            self._post_orbit_realign_active = False
            self._clear_completed = False
            self._enter_follow_state()
        elif self._state_machine.state == ASSISTANT_STATE_APPROACH_OBJECT:
            self._post_orbit_realign_active = False
            self._clear_completed = False
            self._enter_approach_object_state(packet)
        elif self._state_machine.state == ASSISTANT_STATE_ORBIT:
            self._post_orbit_realign_active = False
            self._clear_completed = False
            self._enter_orbit_state()
        elif self._state_machine.state == ASSISTANT_STATE_TRANSPORT_OBJECT:
            self._post_orbit_realign_active = False
            self._clear_completed = False
            self._enter_transport_state(packet)
        elif self._state_machine.state == ASSISTANT_STATE_CLEAR_OBJECT:
            self._post_orbit_realign_active = False
            self._enter_clear_object_state()
        return True

    def _handle_uart6_control_packet(self, line: str) -> bool:
        packet = parse_short_packet(line)
        if packet is None:
            return False
        packet_type = packet.get("type")
        if packet_type == "a":
            pending = self._pending_local_vision_sync
            if (
                pending is not None
                and pending.get("sent_once")
                and int(packet["seq"]) == int(pending["seq"])
            ):
                self._log_local_vision_sync_done(pending)
                self._pending_local_vision_sync = None
            return True
        if packet_type == "r":
            self._write_uart6_reliable_line(format_ack_packet(packet["seq"]))
            if (
                self._state_machine.state == ASSISTANT_STATE_APPROACH_OBJECT
                and int(packet["event"]) == _TARGET_FOUND_EVENT
                and not self._approach_target_found_done
                and not self._post_orbit_realign_active
            ):
                self._handle_local_target_found(packet["seq"], packet["value"])
            elif (
                self._state_machine.state == ASSISTANT_STATE_APPROACH_OBJECT
                and int(packet["event"]) == _ALIGNED_EVENT
                and self._post_orbit_realign_active
                and not self._approach_target_found_done
            ):
                self._handle_local_aligned(packet["seq"], packet["value"])
            return True
        if packet_type == "s":
            return True
        return False

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

    def _record_error_text(self, text: str) -> None:
        self._last_error_text = text
        self._transport_car.last_exception_text = text

    def _write_effective_velocity(self) -> None:
        """将融合后的有效速度写入共享底盘"""

        if self._state_machine.state == ASSISTANT_STATE_APPROACH_OBJECT:
            self._write_approach_object_velocity()
            return
        if self._state_machine.state == ASSISTANT_STATE_ORBIT:
            self._write_orbit_velocity_correction()
            return
        if self._state_machine.state == ASSISTANT_STATE_CLEAR_OBJECT:
            return
        if self._state_machine.state == ASSISTANT_STATE_TRANSPORT_OBJECT:
            self._write_transport_object_velocity()
            return

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

    def _write_approach_object_velocity(self) -> None:
        """在找物体阶段只使用本地视觉平移速度"""

        if self._pending_local_vision_sync is not None or self._approach_target_found_done:
            return
        uart6_velocity = self._inputs["uart6"]["velocity"]
        if uart6_velocity is None:
            return
        self._apply_effective_velocity(
            float(uart6_velocity.get("vx", 0.0)),
            float(uart6_velocity.get("vy", 0.0)),
            0.0,
            False,
        )

    def _write_transport_object_velocity(self) -> None:
        """在搬运阶段融合头对头前馈和本地视觉修正"""

        uart6_velocity = self._inputs["uart6"]["velocity"]
        uart8_velocity = self._inputs["uart8"]["velocity"]
        if uart6_velocity is None and uart8_velocity is None:
            return

        vx = 0.0
        vy = 0.0
        if uart8_velocity is not None:
            scale = float(_ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE)
            vx += -float(uart8_velocity.get("vx", 0.0)) * scale
            vy += -float(uart8_velocity.get("vy", 0.0)) * scale
        if uart6_velocity is not None:
            vx += float(uart6_velocity.get("vx", 0.0))
            vy += float(uart6_velocity.get("vy", 0.0))
        self._apply_effective_velocity(vx, vy, 0.0, False)

    def _write_orbit_velocity_correction(self) -> None:
        """在绕行阶段只使用本地视觉平移修正"""

        if not ORBIT_VISION_CORRECTION_ENABLED:
            return
        if self._pending_local_vision_sync is not None:
            return
        uart6_velocity = self._inputs["uart6"]["velocity"]
        if uart6_velocity is None:
            return
        self._transport_car.set_orbit_velocity_correction(
            float(uart6_velocity.get("vx", 0.0)),
            float(uart6_velocity.get("vy", 0.0)),
        )

    def _apply_effective_velocity(self, vx: float, vy: float, omega: float, has_omega: bool) -> None:
        self._transport_car.handle_velocity_packet(
            vx,
            vy,
            omega,
            source="assistant",
            has_omega=has_omega,
        )
        if (
            self._state_machine.state == ASSISTANT_STATE_APPROACH_OBJECT
            and self._post_orbit_realign_active
        ):
            self._transport_car.set_heading_target(float(_ASSISTANT_ORBIT_TARGET_DEG))

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

    def _should_store_velocity(self, source: str) -> bool:
        if self._state_machine.state == ASSISTANT_STATE_ORBIT:
            return (
                source == "uart6"
                and self._pending_local_vision_sync is None
            )
        if self._state_machine.state == ASSISTANT_STATE_CLEAR_OBJECT:
            return False
        if source == "uart6" and self._pending_local_vision_sync is not None:
            return False
        if self._state_machine.state == ASSISTANT_STATE_TRANSPORT_OBJECT:
            return True
        if self._state_machine.state != ASSISTANT_STATE_APPROACH_OBJECT:
            return True
        if source == "uart8":
            return False
        if self._pending_local_vision_sync is not None:
            return False
        if self._approach_target_found_done:
            return False
        return True

    def _clear_input_cache(self, source: str) -> None:
        state = self._inputs[source]
        state["buffer"] = ""
        state["velocity"] = None
        if state.get("status") != "error":
            state["status"] = "idle"

    def _clear_motion_inputs(self) -> None:
        self._clear_input_cache("uart6")
        self._clear_input_cache("uart8")

    def _enter_follow_state(self) -> None:
        """进入跟随状态并同步本地视觉切回色标跟随任务"""

        self._write_zero_velocity("assistant_follow")
        self._pending_local_vision_sync = {
            "seq": self._local_vision_sync_seq,
            "state": ASSISTANT_STATE_FOLLOW,
            "target": 0,
            "arg": 0,
            "last_sent_ms": None,
            "sent_once": False,
        }
        self._local_vision_sync_seq = (self._local_vision_sync_seq + 1) % 256

    def _write_zero_velocity(self, source: str) -> None:
        self._transport_car.handle_velocity_packet(
            0.0,
            0.0,
            0.0,
            source=source,
            has_omega=True,
        )

    def _enter_approach_object_state(self, packet: dict) -> None:
        self._last_approach_arg = int(packet["arg"])
        self._approach_target_found_done = False
        self._pending_target_found_report = None
        self._clear_motion_inputs()
        self._write_zero_velocity("assistant_approach_object")
        self._pending_local_vision_sync = {
            "seq": self._local_vision_sync_seq,
            "state": int(packet["state"]),
            "target": int(packet["target"]),
            "arg": int(packet["arg"]),
            "last_sent_ms": None,
            "sent_once": False,
        }
        self._local_vision_sync_seq = (self._local_vision_sync_seq + 1) % 256

    def _enter_orbit_state(self) -> None:
        self._approach_target_found_done = False
        self._pending_target_found_report = None
        self._clear_motion_inputs()
        self._pending_local_vision_sync = {
            "seq": self._local_vision_sync_seq,
            "state": ASSISTANT_STATE_ORBIT,
            "target": ASSISTANT_TARGET_OBJECT,
            "arg": int(_ASSISTANT_ORBIT_OBJECT_CONFIG_ID),
            "last_sent_ms": None,
            "sent_once": False,
        }
        self._local_vision_sync_seq = (self._local_vision_sync_seq + 1) % 256
        self._transport_car.set_orbit_target(
            float(_ASSISTANT_ORBIT_TARGET_DEG),
            float(_ASSISTANT_ORBIT_RADIUS_SCALE),
        )

    def _handle_local_target_found(self, seq: int, value: int) -> None:
        self._approach_target_found_done = True
        self._inputs["uart6"]["velocity"] = None
        self._write_zero_velocity("assistant_target_found")
        self._pending_target_found_report = {
            "seq": int(seq),
            "event": _TARGET_FOUND_EVENT,
            "value": int(value),
            "last_sent_ms": None,
            "sent_once": False,
        }

    def _handle_local_aligned(self, seq: int, value: int) -> None:
        self._approach_target_found_done = True
        self._inputs["uart6"]["velocity"] = None
        self._write_zero_velocity("assistant_aligned")
        self._pending_target_found_report = {
            "seq": int(seq),
            "event": _ALIGNED_EVENT,
            "value": int(value),
            "last_sent_ms": None,
            "sent_once": False,
        }

    def _enter_transport_state(self, packet: dict) -> None:
        self._approach_target_found_done = False
        self._pending_target_found_report = None
        self._post_orbit_realign_active = False
        self._clear_completed = False
        self._clear_motion_inputs()
        self._write_zero_velocity("assistant_transport")
        self._pending_local_vision_sync = {
            "seq": self._local_vision_sync_seq,
            "state": ASSISTANT_STATE_APPROACH_OBJECT,
            "target": int(packet["target"]),
            "arg": int(_ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID),
            "last_sent_ms": None,
            "sent_once": False,
        }
        self._local_vision_sync_seq = (self._local_vision_sync_seq + 1) % 256

    def _enter_clear_object_state(self) -> None:
        self._approach_target_found_done = False
        self._pending_local_vision_sync = None
        self._pending_target_found_report = None
        self._post_orbit_realign_active = False
        self._clear_completed = False
        self._clear_stop_ticks = 0
        self._clear_motion_inputs()
        clear_phase = int(self._state_machine.arg)
        if clear_phase == CLEAR_PHASE_RETREAT:
            self._transport_car.set_relative_translation_target(
                0.0,
                -float(_TRANSPORT_CLEAR_STEP_DISTANCE_M) * 0.5,
            )
            return
        if clear_phase == CLEAR_PHASE_FORWARD:
            self._transport_car.set_relative_translation_target(
                0.0,
                float(_TRANSPORT_CLEAR_STEP_DISTANCE_M),
            )

    def _resume_approach_after_orbit(self) -> None:
        if self._state_machine.state != ASSISTANT_STATE_ORBIT:
            return
        if bool(getattr(self._transport_car, "command_lock", False)):
            return
        if self._post_orbit_realign_active:
            return
        if self._last_approach_arg <= 0:
            return
        self._state_machine.apply_master_state(
            ASSISTANT_STATE_APPROACH_OBJECT,
            ASSISTANT_TARGET_OBJECT,
            _ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
        )
        self._enter_approach_object_state(
            {
                "state": ASSISTANT_STATE_APPROACH_OBJECT,
                "target": ASSISTANT_TARGET_OBJECT,
                "arg": _ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
            }
        )
        self._post_orbit_realign_active = True
        self._send_pending_local_vision_sync()

    def _finish_clear_if_needed(self) -> None:
        if self._state_machine.state != ASSISTANT_STATE_CLEAR_OBJECT:
            self._clear_stop_ticks = 0
            return
        if self._clear_completed:
            self._clear_stop_ticks = 0
            return
        if bool(getattr(self._transport_car, "command_lock", False)):
            self._clear_stop_ticks = 0
            return
        if not self._are_all_wheels_near_stop():
            self._clear_stop_ticks = 0
            return
        self._clear_stop_ticks += 1
        if self._clear_stop_ticks < int(MOTION_STOP_CONFIRM_TICKS):
            return
        self._clear_stop_ticks = 0
        self._clear_completed = True
        self._write_zero_velocity("assistant_clear_complete")
        self._pending_target_found_report = {
            "seq": int(self._now_ms()) % 256,
            "event": _CLEARED_EVENT,
            "value": int(self._state_machine.arg),
            "last_sent_ms": None,
            "sent_once": False,
        }

    def _are_all_wheels_near_stop(self) -> bool:
        """判断三轮实际轮速是否都已进入静止范围"""

        wheel_states = getattr(self._transport_car, "wheel_states", ())
        if len(wheel_states) < 3:
            return False
        threshold = float(MOTION_STOP_SPEED_THRESHOLD)
        for state in wheel_states:
            if abs(float(state.get("filtered_speed", 0.0))) > threshold:
                return False
        return True

    def _send_pending_local_vision_sync(self) -> None:
        pending = self._pending_local_vision_sync
        if pending is None:
            return
        now_ms = self._now_ms()
        if not should_resend(
            now_ms,
            pending.get("last_sent_ms"),
            _LOCAL_VISION_SYNC_RESEND_INTERVAL_MS,
        ):
            return
        if self._write_uart6_reliable_line(
            format_state_sync_packet(
                pending["seq"],
                pending["state"],
                pending["target"],
                pending["arg"],
            )
        ):
            if not pending.get("sent_once"):
                self._log_local_vision_sync_start(pending)
            pending["last_sent_ms"] = now_ms
            pending["sent_once"] = True

    def _send_pending_target_found_report(self) -> None:
        pending = self._pending_target_found_report
        if pending is None:
            return
        now_ms = self._now_ms()
        if not should_resend(
            now_ms,
            pending.get("last_sent_ms"),
            _MASTER_REPORT_RESEND_INTERVAL_MS,
        ):
            return
        if self._write_forward_reliable_line(
            format_event_packet(
                pending["seq"],
                pending["event"],
                pending["value"],
            )
        ):
            pending["last_sent_ms"] = now_ms
            pending["sent_once"] = True

    def _write_forward_reliable_line(self, line: str) -> bool:
        uart = self._inputs["uart8"]["uart"]
        if uart is None:
            return False
        try:
            wrote_all = bool(write_reliable_line(uart, line))
            return wrote_all
        except Exception as exc:
            self._record_error("uart8 write failed", exc)
            return False

    def _log_master_sync_done(self, packet: dict) -> None:
        log(
            "sync",
            "master->assistant sync done seq=%d state=%d target=%d arg=%d"
            % (
                int(packet["seq"]),
                int(packet["state"]),
                int(packet["target"]),
                int(packet["arg"]),
            ),
        )

    def _log_local_vision_sync_start(self, pending: dict) -> None:
        log(
            "sync",
            "assistant->camera sync start seq=%d state=%d target=%d arg=%d"
            % (
                int(pending["seq"]),
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _log_local_vision_sync_done(self, pending: dict) -> None:
        log(
            "sync",
            "assistant->camera sync done seq=%d state=%d target=%d arg=%d"
            % (
                int(pending["seq"]),
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _write_uart6_reliable_line(self, line: str) -> bool:
        uart = self._inputs["uart6"]["uart"]
        if uart is None:
            return False
        try:
            wrote_all = bool(write_reliable_line(uart, line))
            return wrote_all
        except Exception as exc:
            self._record_error("uart6 write failed", exc)
            return False

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
