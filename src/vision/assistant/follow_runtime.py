"""辅车角色运行时主体

@file src/vision/assistant/follow_runtime.py
"""

import time

from config import motion as motion_params
from config import vision as vision_params
from protocol.codec import (
    decode_assistant_state_sync_body,
    decode_assistant_vision_event_report_body,
    decode_velocity_body,
    encode_assistant_event_report_body,
    encode_assistant_vision_task_sync_body,
)
from protocol.topic import (
    ROLE_ASSISTANT,
    TOPIC_ASSISTANT_EVENT_REPORT,
    TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
    TOPIC_ASSISTANT_STATE_SYNC,
    TOPIC_ASSISTANT_VISION_EVENT_REPORT,
    TOPIC_ASSISTANT_VISION_TASK_SYNC,
    TOPIC_LOCAL_VISION_VELOCITY,
    UART6,
    UART8,
)
from protocol.transport import (
    DELIVERY_DELIVERED,
    WRITE_ACCEPTED,
    WRITE_OVERWRITTEN,
    create_transport,
)
from utils.startup_log import log, log_exception
from vision.assistant.diagnostics import build_follow_snapshot
from vision.assistant.state_machine import (
    ASSISTANT_STATE_APPROACH_OBJECT,
    ASSISTANT_STATE_CLEAR_OBJECT,
    ASSISTANT_STATE_FOLLOW,
    ASSISTANT_STATE_ORBIT,
    ASSISTANT_STATE_TRANSPORT_OBJECT,
    ASSISTANT_TARGET_OBJECT,
    AssistantStateMachine,
)
from vision.clear_phase import CLEAR_PHASE_FORWARD, CLEAR_PHASE_RETREAT


_TARGET_FOUND_EVENT = 6
_ALIGNED_EVENT = 7
_CLEARED_EVENT = 9
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
    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


class AssistantFollowRuntime:
    """基于共享底盘装配辅车角色运行时外观."""

    def __init__(self, now_ms=None, transport=None, uart6=None, uart8=None) -> None:
        from core.runtime import TransportCar

        car = TransportCar()
        self._transport_car = car
        self.wheel_states = car.wheel_states
        self.imu = car.imu
        self._now_ms = now_ms or _default_now_ms
        self.transport_service = transport or create_transport(
            ROLE_ASSISTANT,
            uart6=uart6,
            uart8=uart8,
            now_ms=self._now_ms,
        )
        self._state_machine = AssistantStateMachine()
        self._last_error_text = "none"
        self._uart6_velocity = None
        self._uart8_velocity = None
        self._uart6_reset_version = 0
        self._uart8_reset_version = 0
        self._uart6_status = "idle"
        self._uart8_status = "idle"
        self.sync_context = None
        self._sync_apply_count = 0
        seed_value = int(self._now_ms()) % 256
        self._pending_local_vision_sync = None
        self._pending_target_found_report = None
        self._approach_target_found_done = False
        self._last_approach_arg = 0
        self._post_orbit_realign_active = False
        self._clear_completed = False
        self._clear_stop_ticks = 0
        self._velocity_body = bytearray(7)
        self._sync_body = bytearray(4)
        self._event_body = bytearray(3)
        self._pending_local_vision_sync = {
            "state": ASSISTANT_STATE_FOLLOW,
            "target": 0,
            "arg": 0,
            "queued": False,
        }

    def mark_tick(self, tick=None) -> None:
        self._transport_car.mark_tick(tick)

    def set_ticker(self, ticker_obj: object) -> None:
        self._transport_car.set_ticker(ticker_obj)

    def poll_transport_rx(self) -> None:
        self.transport_service.poll_rx()

    def poll_transport_tx(self) -> None:
        self.transport_service.poll_tx()

    def step(self) -> bool:
        try:
            self._run_role_cycle()
        except Exception as exc:
            self._record_error_text("role_cycle failed: %s" % exc, exc)
        keep_running = self._transport_car.step()
        self._finish_clear_if_needed()
        self._resume_approach_after_orbit()
        return keep_running

    def _run_role_cycle(self) -> None:
        """执行辅车单拍业务编排.

        @details 辅车只从通信层读取主车同步、本地视觉事件和速度输入, 再提交新的业务回报
        """
        self._check_transport_deliveries()
        self._consume_master_sync()
        self._consume_local_vision_event()
        self._consume_velocity_inputs()
        self._write_effective_velocity()
        self._queue_pending_local_vision_sync()
        self._queue_pending_report()

    def _check_transport_deliveries(self) -> None:
        """根据通信层交付状态释放本地视觉同步和主车回报槽."""
        pending = self._pending_local_vision_sync
        if pending is not None and pending.get("queued"):
            if (
                self.transport_service.tcp(UART6).delivery(TOPIC_ASSISTANT_VISION_TASK_SYNC)
                == DELIVERY_DELIVERED
            ):
                self._log_local_vision_sync_done(pending)
                self._pending_local_vision_sync = None
        pending = self._pending_target_found_report
        if pending is not None and pending.get("queued"):
            if (
                self.transport_service.tcp(UART8).delivery(TOPIC_ASSISTANT_EVENT_REPORT)
                == DELIVERY_DELIVERED
            ):
                self._pending_target_found_report = None

    def _consume_master_sync(self) -> None:
        """消费主车下发的辅车状态同步."""
        if (
            self.transport_service.tcp(UART8).read(
                TOPIC_ASSISTANT_STATE_SYNC, self._sync_body
            )
            != "ok"
        ):
            return
        packet = decode_assistant_state_sync_body(self._sync_body)
        accepted = self._apply_sync_context(packet)
        if not accepted:
            text = "unknown assistant sync state: %s" % int(packet["state"])
            self._record_error_text(text, RuntimeError(text))
            return
        self.sync_context = dict(packet)
        self._sync_apply_count += 1
        self._log_master_sync_done(packet)

    def _apply_sync_context(self, packet: dict) -> bool:
        accepted = self._state_machine.apply_master_state(
            packet["state"], packet["target"], packet["arg"]
        )
        if not accepted:
            return False
        if self._state_machine.is_idle():
            self._clear_motion_inputs()
            self._pending_local_vision_sync = None
            self._pending_target_found_report = None
            self._approach_target_found_done = False
            self._post_orbit_realign_active = False
            self._clear_completed = False
            self._write_zero_velocity("assistant_idle")
        elif self._state_machine.state == ASSISTANT_STATE_FOLLOW:
            self._clear_motion_inputs()
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

    def _consume_local_vision_event(self) -> None:
        """消费本地视觉的可靠事件回报."""
        if (
            self.transport_service.tcp(UART6).read(
                TOPIC_ASSISTANT_VISION_EVENT_REPORT, self._event_body
            )
            != "ok"
        ):
            return
        packet = decode_assistant_vision_event_report_body(self._event_body)
        event = int(packet["event"])
        if (
            self._state_machine.state == ASSISTANT_STATE_APPROACH_OBJECT
            and event == _TARGET_FOUND_EVENT
            and not self._approach_target_found_done
            and not self._post_orbit_realign_active
        ):
            self._handle_local_target_found(packet["value"])
        elif (
            self._state_machine.state == ASSISTANT_STATE_APPROACH_OBJECT
            and event == _ALIGNED_EVENT
            and self._post_orbit_realign_active
            and not self._approach_target_found_done
        ):
            self._handle_local_aligned(packet["value"])

    def _consume_velocity_inputs(self) -> None:
        """消费两路 UDP 最新值速度输入.

        @details 通过版本号判断状态切换后的旧值是否仍应被忽略, 不直接清底层缓存
        """
        self._uart6_status = "idle"
        self._uart8_status = "idle"
        if (
            self.transport_service.udp(UART6).read(TOPIC_LOCAL_VISION_VELOCITY, self._velocity_body)
            == "ok"
        ):
            version = self.transport_service.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            if version > self._uart6_reset_version:
                self._uart6_velocity = decode_velocity_body(self._velocity_body)
                self._uart6_velocity["omega"] = 0.0
                self._uart6_velocity["has_omega"] = False
                self._uart6_status = "active"
        if (
            self.transport_service.udp(UART8).read(
                TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
                self._velocity_body,
            )
            == "ok"
        ):
            version = self.transport_service.get_udp_version(
                UART8, TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY
            )
            if version > self._uart8_reset_version:
                self._uart8_velocity = decode_velocity_body(self._velocity_body)
                self._uart8_status = "active"

        if not self._should_store_velocity("uart6"):
            self._uart6_velocity = None
            self._uart6_status = "idle"
        if not self._should_store_velocity("uart8"):
            self._uart8_velocity = None
            self._uart8_status = "idle"

    def _write_effective_velocity(self) -> None:
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
        uart6_velocity = self._uart6_velocity
        uart8_velocity = self._uart8_velocity
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
        if self._pending_local_vision_sync is not None or self._approach_target_found_done:
            return
        uart6_velocity = self._uart6_velocity
        if uart6_velocity is None:
            return
        self._apply_effective_velocity(
            float(uart6_velocity.get("vx", 0.0)),
            float(uart6_velocity.get("vy", 0.0)),
            0.0,
            False,
        )

    def _write_transport_object_velocity(self) -> None:
        uart6_velocity = self._uart6_velocity
        uart8_velocity = self._uart8_velocity
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
        if not ORBIT_VISION_CORRECTION_ENABLED:
            return
        if self._pending_local_vision_sync is not None:
            return
        uart6_velocity = self._uart6_velocity
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
            "assistant",
            has_omega,
        )
        if (
            self._state_machine.state == ASSISTANT_STATE_APPROACH_OBJECT
            and self._post_orbit_realign_active
        ):
            self._transport_car.set_heading_target(float(_ASSISTANT_ORBIT_TARGET_DEG))

    def _should_store_velocity(self, source: str) -> bool:
        if self._state_machine.state == ASSISTANT_STATE_ORBIT:
            return source == "uart6" and self._pending_local_vision_sync is None
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

    def _clear_motion_inputs(self) -> None:
        """在状态切换时丢弃当前业务视角下的旧速度输入."""
        self._uart6_velocity = None
        self._uart8_velocity = None
        self._uart6_reset_version = self.transport_service.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )
        self._uart8_reset_version = self.transport_service.get_udp_version(
            UART8, TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY
        )
        self._uart6_status = "idle"
        self._uart8_status = "idle"

    def _enter_follow_state(self) -> None:
        self._write_zero_velocity("assistant_follow")
        self._pending_local_vision_sync = {
            "state": ASSISTANT_STATE_FOLLOW,
            "target": 0,
            "arg": 0,
            "queued": False,
        }

    def _write_zero_velocity(self, source: str) -> None:
        self._transport_car.handle_velocity_packet(
            0.0,
            0.0,
            0.0,
            source,
            True,
        )

    def _enter_approach_object_state(self, packet: dict) -> None:
        self._last_approach_arg = int(packet["arg"])
        self._approach_target_found_done = False
        self._pending_target_found_report = None
        self._clear_motion_inputs()
        self._write_zero_velocity("assistant_approach_object")
        self._pending_local_vision_sync = {
            "state": int(packet["state"]),
            "target": int(packet["target"]),
            "arg": int(packet["arg"]),
            "queued": False,
        }

    def _enter_orbit_state(self) -> None:
        self._approach_target_found_done = False
        self._pending_target_found_report = None
        self._clear_motion_inputs()
        self._pending_local_vision_sync = {
            "state": ASSISTANT_STATE_ORBIT,
            "target": ASSISTANT_TARGET_OBJECT,
            "arg": int(_ASSISTANT_ORBIT_OBJECT_CONFIG_ID),
            "queued": False,
        }
        self._transport_car.set_orbit_target(
            float(_ASSISTANT_ORBIT_TARGET_DEG),
            float(_ASSISTANT_ORBIT_RADIUS_SCALE),
        )

    def _handle_local_target_found(self, value: int) -> None:
        self._approach_target_found_done = True
        self._uart6_velocity = None
        self._write_zero_velocity("assistant_target_found")
        self._pending_target_found_report = {
            "event": _TARGET_FOUND_EVENT,
            "value": int(value),
            "queued": False,
        }

    def _handle_local_aligned(self, value: int) -> None:
        self._approach_target_found_done = True
        self._uart6_velocity = None
        self._write_zero_velocity("assistant_aligned")
        self._pending_target_found_report = {
            "event": _ALIGNED_EVENT,
            "value": int(value),
            "queued": False,
        }

    def _enter_transport_state(self, packet: dict) -> None:
        self._approach_target_found_done = False
        self._pending_target_found_report = None
        self._post_orbit_realign_active = False
        self._clear_completed = False
        self._clear_motion_inputs()
        self._write_zero_velocity("assistant_transport")
        self._pending_local_vision_sync = {
            "state": ASSISTANT_STATE_APPROACH_OBJECT,
            "target": int(packet["target"]),
            "arg": int(_ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID),
            "queued": False,
        }

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
            "event": _CLEARED_EVENT,
            "value": int(self._state_machine.arg),
            "queued": False,
        }

    def _are_all_wheels_near_stop(self) -> bool:
        wheel_states = getattr(self._transport_car, "wheel_states", ())
        if len(wheel_states) < 3:
            return False
        threshold = float(MOTION_STOP_SPEED_THRESHOLD)
        for state in wheel_states:
            if abs(float(state.get("filtered_speed", 0.0))) > threshold:
                return False
        return True

    def _queue_pending_local_vision_sync(self) -> None:
        pending = self._pending_local_vision_sync
        if pending is None or pending.get("queued"):
            return
        body = encode_assistant_vision_task_sync_body(
            pending["state"],
            pending["target"],
            pending["arg"],
        )
        status = self.transport_service.tcp(UART6).write(TOPIC_ASSISTANT_VISION_TASK_SYNC, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            self._log_local_vision_sync_start(pending)
            pending["queued"] = True

    def _queue_pending_report(self) -> None:
        pending = self._pending_target_found_report
        if pending is None or pending.get("queued"):
            return
        body = encode_assistant_event_report_body(
            pending["event"],
            pending["value"],
        )
        status = self.transport_service.tcp(UART8).write(TOPIC_ASSISTANT_EVENT_REPORT, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            pending["queued"] = True

    def build_follow_snapshot(self) -> dict:
        return build_follow_snapshot(
            self._state_machine.state,
            self._state_machine.target,
            dict(self._transport_car.control_state),
            self._uart6_status,
            self._uart8_status,
            self._build_velocity_snapshot(self._uart6_velocity),
            self._build_velocity_snapshot(self._uart8_velocity),
            self._pending_local_vision_sync is not None,
            self._approach_target_found_done,
            self._last_error_text,
        )

    def _build_velocity_snapshot(self, velocity) -> dict:
        if velocity is None:
            return {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        return {
            "vx": float(velocity.get("vx", 0.0)),
            "vy": float(velocity.get("vy", 0.0)),
            "omega": float(velocity.get("omega", 0.0)),
        }

    def _record_error_text(self, text: str, exc: Exception) -> None:
        if self._last_error_text != text:
            log_exception("assistant_error", text, exc)
        self._last_error_text = text
        self._transport_car.last_exception_text = text

    def _log_master_sync_done(self, packet: dict) -> None:
        log(
            "sync",
            "master->assistant sync done state=%d target=%d arg=%d"
            % (
                int(packet["state"]),
                int(packet["target"]),
                int(packet["arg"]),
            ),
        )

    def _log_local_vision_sync_start(self, pending: dict) -> None:
        log(
            "sync",
            "assistant->camera sync start state=%d target=%d arg=%d"
            % (
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _log_local_vision_sync_done(self, pending: dict) -> None:
        log(
            "sync",
            "assistant->camera sync done state=%d target=%d arg=%d"
            % (
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )


def create_transport_car() -> AssistantFollowRuntime:
    """创建辅车角色运行时对象."""

    return AssistantFollowRuntime()
