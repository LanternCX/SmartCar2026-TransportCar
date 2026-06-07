"""主车角色运行时主体

@file src/vision/master/forward_runtime.py
"""

import time

from config import motion as motion_params
from config import vision as vision_params
from protocol.codec import (
    decode_assistant_event_report_body,
    decode_master_vision_event_report_body,
    decode_velocity_body,
    encode_assistant_state_sync_body,
    encode_master_vision_hook_sync_body,
    encode_velocity_body,
)
from protocol.topic import (
    ROLE_MASTER,
    TOPIC_ASSISTANT_EVENT_REPORT,
    TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
    TOPIC_ASSISTANT_STATE_SYNC,
    TOPIC_LOCAL_VISION_VELOCITY,
    TOPIC_MASTER_VISION_EVENT_REPORT,
    TOPIC_MASTER_VISION_HOOK_SYNC,
    UART6,
    UART8,
)
from protocol.transport import (
    DELIVERY_DELIVERED,
    WRITE_ACCEPTED,
    WRITE_OVERWRITTEN,
    create_transport,
)
from vision.clear_phase import CLEAR_PHASE_FORWARD, CLEAR_PHASE_RETREAT
from vision.master.state_machine import MasterStateMachine
from vision.master.state_machine import (
    EVENT_ALIGNED,
    EVENT_ARRIVED,
    EVENT_CLEARED,
    EVENT_TARGET_FOUND,
    STATE_CLEAR_OBJECT,
    STATE_FINISHED,
    STATE_ORBITING,
    STATE_RETURN_GARAGE_LINE,
    STATE_RETURN_GARAGE_RETREAT,
    STATE_SEARCH_OBJECT,
    STATE_STOP,
    STATE_TRANSPORT_OBJECT,
    TARGET_EDGE_LINE,
    TARGET_OBJECT,
)
from utils.startup_log import log, log_exception


MASTER_SEARCH_HOOK_CONFIG_ID = getattr(vision_params, "MASTER_SEARCH_HOOK_CONFIG_ID")
ASSISTANT_APPROACH_OBJECT_CONFIG_ID = getattr(
    vision_params,
    "ASSISTANT_APPROACH_OBJECT_CONFIG_ID",
)
ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID = getattr(
    vision_params,
    "ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID",
)
MASTER_TRANSPORT_HOOK_CONFIG_ID = getattr(vision_params, "MASTER_TRANSPORT_HOOK_CONFIG_ID")
MASTER_TRANSPORT_FINISH_HOOK_CONFIG_ID = getattr(
    vision_params,
    "MASTER_TRANSPORT_FINISH_HOOK_CONFIG_ID",
)
MASTER_ORBIT_HOOK_CONFIG_ID = getattr(vision_params, "MASTER_ORBIT_HOOK_CONFIG_ID")
MASTER_RETURN_GARAGE_LINE_HOOK_CONFIG_ID = getattr(
    vision_params,
    "MASTER_RETURN_GARAGE_LINE_HOOK_CONFIG_ID",
)
TRANSPORT_OBJECT_TOTAL_COUNT = getattr(vision_params, "TRANSPORT_OBJECT_TOTAL_COUNT")
ORBIT_VISION_CORRECTION_ENABLED = bool(
    getattr(vision_params, "ORBIT_VISION_CORRECTION_ENABLED")
)
MASTER_ORBIT_TARGET_DEG = getattr(motion_params, "MASTER_ORBIT_TARGET_DEG")
MASTER_ORBIT_RADIUS_SCALE = getattr(motion_params, "MASTER_ORBIT_RADIUS_SCALE")
TRANSPORT_FORWARD_SPEED = getattr(motion_params, "TRANSPORT_FORWARD_SPEED")
TRANSPORT_CLEAR_STEP_DISTANCE_M = getattr(motion_params, "TRANSPORT_CLEAR_STEP_DISTANCE_M")
TRANSPORT_CLEAR_RETREAT_DISTANCE_M = getattr(
    motion_params,
    "TRANSPORT_CLEAR_RETREAT_DISTANCE_M",
)
TRANSPORT_CLEAR_RETREAT_MAX_SPEED = getattr(
    motion_params,
    "TRANSPORT_CLEAR_RETREAT_MAX_SPEED",
)
MOTION_STOP_SPEED_THRESHOLD = getattr(motion_params, "MOTION_STOP_SPEED_THRESHOLD")
MOTION_STOP_CONFIRM_TICKS = getattr(motion_params, "MOTION_STOP_CONFIRM_TICKS")
MASTER_TURN_BACK_DELTA_DEG = getattr(motion_params, "MASTER_TURN_BACK_DELTA_DEG")
MASTER_RETURN_GARAGE_RETREAT_SPEED = getattr(
    motion_params,
    "MASTER_RETURN_GARAGE_RETREAT_SPEED",
)
MASTER_RETURN_GARAGE_LEFT_SPEED = getattr(
    motion_params,
    "MASTER_RETURN_GARAGE_LEFT_SPEED",
)


def _default_now_ms():
    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


class MasterForwardRuntime:
    """基于共享底盘装配主车角色运行时外观."""

    def __init__(self, now_ms=None, transport=None) -> None:
        from core.runtime import TransportCar

        car = TransportCar()
        self._transport_car = car
        self.wheel_states = car.wheel_states
        self.imu = car.imu
        self._now_ms = now_ms or _default_now_ms
        self.transport_service = transport or create_transport(
            ROLE_MASTER,
            now_ms=self._now_ms,
        )
        seed_value = int(self._now_ms()) % 256
        self._state_machine = MasterStateMachine(
            hook_arg=MASTER_SEARCH_HOOK_CONFIG_ID,
            boot_heading_deg=float(getattr(car, "heading_est", 0.0)),
            orbit_delta_deg=MASTER_ORBIT_TARGET_DEG,
            assistant_object_arg=ASSISTANT_APPROACH_OBJECT_CONFIG_ID,
            assistant_transport_arg=ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
            transport_hook_arg=MASTER_TRANSPORT_HOOK_CONFIG_ID,
            finish_hook_arg=MASTER_TRANSPORT_FINISH_HOOK_CONFIG_ID,
            return_line_hook_arg=MASTER_RETURN_GARAGE_LINE_HOOK_CONFIG_ID,
            total_object_count=TRANSPORT_OBJECT_TOTAL_COUNT,
            initial_context_id=seed_value,
        )
        self._last_error_text = "none"
        self._latest_uart6_velocity = None
        self._uart6_reset_version = 0
        self._active_hook_context_id = None
        self._pending_hook = None
        self._pending_hook_event = None
        self._pending_sync = None
        self._pending_assistant_sync = None
        self._orbit_command_active = False
        self._transport_sync_acknowledged = False
        self._transport_hook_acknowledged = False
        self._clear_sync_acknowledged = False
        self._clear_motion_started = False
        self._clear_master_completed_phase = None
        self._clear_motion_stop_ticks = 0
        self._turn_back_rotation_started = False
        self._turn_back_stop_ticks = 0
        self._turn_back_target_heading_deg = None
        self._last_hook_sync_status = None
        self._velocity_body = bytearray(7)
        self._hook_event_body = bytearray(4)
        self._assistant_event_body = bytearray(3)
        self.last_report = None

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
            self._record_error("master role cycle failed: %s" % exc, exc)
        return self._transport_car.step()

    def request_state_sync(self, state: int, target: int, arg: int) -> int:
        pending = {
            "kind": "generic",
            "state": int(state),
            "target": int(target),
            "arg": int(arg),
            "queued": False,
        }
        self._pending_sync = pending
        return int(state)

    def _run_role_cycle(self) -> None:
        """执行主车单拍业务编排.

        @details 角色层只消费通信层缓存并提交新的业务意图, 不直接管理 UART 收发
        """
        self._check_transport_deliveries()
        self._advance_state_machine()
        self._drain_state_machine_outputs()
        self._consume_uart6_inputs()
        self._consume_uart8_inputs()
        self._check_transport_deliveries()
        self._drain_state_machine_outputs()
        self._apply_motion_outputs()
        self._run_clear_phase()
        self._run_turn_back_phase()
        self._drain_state_machine_outputs()
        self._queue_transport_outputs()

    def _consume_uart6_inputs(self) -> None:
        """消费本车视觉链路上的 UDP 速度与 TCP 事件."""
        if (
            self.transport_service.udp(UART6).read(
                TOPIC_LOCAL_VISION_VELOCITY, self._velocity_body
            )
            == "ok"
        ):
            version = self.transport_service.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            if version > self._uart6_reset_version:
                packet = decode_velocity_body(self._velocity_body)
                if (
                    self._state_machine.allows_search_velocity()
                    or self._state_machine.state == STATE_TRANSPORT_OBJECT
                    or (
                        self._state_machine.state == STATE_ORBITING
                        and self._pending_hook is None
                    )
                    or (
                        self._state_machine.state == STATE_RETURN_GARAGE_LINE
                        and self._pending_hook is None
                    )
                ):
                    self._latest_uart6_velocity = packet
        if (
            self.transport_service.tcp(UART6).read(
                TOPIC_MASTER_VISION_EVENT_REPORT, self._hook_event_body
            )
            == "ok"
        ):
            packet = decode_master_vision_event_report_body(self._hook_event_body)
            self._handle_hook_event(packet)

    def _consume_uart8_inputs(self) -> None:
        """消费辅车回报的可靠事件."""
        if (
            self.transport_service.tcp(UART8).read(
                TOPIC_ASSISTANT_EVENT_REPORT, self._assistant_event_body
            )
            == "ok"
        ):
            packet = decode_assistant_event_report_body(self._assistant_event_body)
            self._clear_local_velocity_for_reliable_event("assistant_event")
            self.last_report = dict(packet)
            if int(packet["event"]) == EVENT_TARGET_FOUND:
                self._state_machine.handle_assistant_target_found(packet["value"])
            elif int(packet["event"]) == EVENT_ALIGNED:
                self._state_machine.handle_assistant_aligned(packet["value"])
            elif int(packet["event"]) == EVENT_CLEARED:
                self._state_machine.handle_assistant_cleared(packet["value"])

    def _handle_hook_event(self, packet: dict) -> None:
        context_id = int(packet["context_id"])
        if self._active_hook_context_id == context_id:
            self._clear_local_velocity_for_reliable_event("master_vision_event")
            self._state_machine.handle_event(
                context_id,
                packet["event"],
                packet["value"],
            )
            return
        if self._pending_hook is not None and context_id == int(self._pending_hook["context_id"]):
            self._clear_local_velocity_for_reliable_event("master_vision_event")
            self._pending_hook_event = {
                "context_id": context_id,
                "event": int(packet["event"]),
                "value": int(packet["value"]),
            }

    def _clear_local_velocity_for_reliable_event(self, source: str) -> None:
        """可靠业务事件到达时, 丢弃旧 UDP 速度并按需写入零速度语义."""

        self._latest_uart6_velocity = None
        self._uart6_reset_version = self.transport_service.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )
        if bool(getattr(self._transport_car, "command_lock", False)):
            return
        self._transport_car.handle_velocity_packet(
            0.0,
            0.0,
            0.0,
            source,
            True,
        )

    def _check_transport_deliveries(self) -> None:
        """把通信层的交付结果映射回角色状态机."""
        pending = self._pending_hook
        if pending is not None and pending.get("queued"):
            if (
                self.transport_service.tcp(UART6).delivery(TOPIC_MASTER_VISION_HOOK_SYNC)
                == DELIVERY_DELIVERED
            ):
                self._log_hook_sync_done(pending)
                self._active_hook_context_id = int(pending["context_id"])
                if pending.get("kind") == "transport_hook":
                    self._transport_hook_acknowledged = True
                    if self._transport_sync_acknowledged:
                        self._state_machine.mark_transport_ready()
                elif self._state_machine.state == STATE_SEARCH_OBJECT:
                    self._state_machine.mark_restart_search_hook_acknowledged()
                self._pending_hook = None
                self._drain_pending_hook_event()

        pending = self._pending_assistant_sync
        if pending is not None and pending.get("queued"):
            if (
                self.transport_service.tcp(UART8).delivery(TOPIC_ASSISTANT_STATE_SYNC)
                == DELIVERY_DELIVERED
            ):
                self._log_sync_done("master->assistant", pending)
                if pending.get("kind") == "assistant_object":
                    self._state_machine.mark_assistant_object_acknowledged()
                elif pending.get("kind") == "assistant_follow":
                    self._state_machine.mark_assistant_follow_acknowledged()
                elif pending.get("kind") == "assistant_transport":
                    self._transport_sync_acknowledged = True
                    if self._transport_hook_acknowledged:
                        self._state_machine.mark_transport_ready()
                elif pending.get("kind") == "assistant_clear":
                    self._clear_sync_acknowledged = True
                self._pending_assistant_sync = None

        pending = self._pending_sync
        if pending is not None and pending.get("queued"):
            if (
                self.transport_service.tcp(UART8).delivery(TOPIC_ASSISTANT_STATE_SYNC)
                == DELIVERY_DELIVERED
            ):
                self._log_sync_done("master->assistant", pending)
                self._pending_sync = None

    def _apply_motion_outputs(self) -> None:
        if self._state_machine.state == STATE_TRANSPORT_OBJECT:
            self._apply_transport_velocity()
            return
        if self._state_machine.state == STATE_ORBITING:
            self._apply_orbit_velocity_correction()
            return
        if self._state_machine.state == STATE_RETURN_GARAGE_RETREAT:
            self._transport_car.handle_velocity_packet(
                0.0,
                float(MASTER_RETURN_GARAGE_RETREAT_SPEED),
                0.0,
                "master_return_retreat",
                False,
            )
            return
        if self._state_machine.state == STATE_RETURN_GARAGE_LINE:
            packet = self._latest_uart6_velocity
            vy = 0.0
            if packet is not None:
                vy = float(packet.get("vy", 0.0))
            self._transport_car.handle_velocity_packet(
                float(MASTER_RETURN_GARAGE_LEFT_SPEED),
                vy,
                0.0,
                "master_return_line",
                False,
            )
            return
        if self._state_machine.state == STATE_FINISHED:
            self._transport_car.handle_velocity_packet(
                0.0,
                0.0,
                0.0,
                "master_finished",
                True,
            )
            return
        if self._state_machine.state == STATE_SEARCH_OBJECT and getattr(
            self._state_machine, "_master_aligned", False
        ):
            self._transport_car.handle_velocity_packet(
                0.0,
                0.0,
                0.0,
                "master_aligned_hold",
                True,
            )
            return
        if self._state_machine.allows_search_velocity():
            self._apply_latest_uart6_velocity()

    def _apply_latest_uart6_velocity(self) -> None:
        packet = self._latest_uart6_velocity
        if packet is None:
            return
        self._transport_car.handle_velocity_packet(
            float(packet["vx"]),
            float(packet["vy"]),
            0.0,
            "uart6",
            False,
        )
        if self._state_machine.state == STATE_SEARCH_OBJECT and getattr(
            self._state_machine, "_orbit_completed", False
        ):
            target_heading_deg = (
                float(self._state_machine._boot_heading_deg)
                + float(MASTER_ORBIT_TARGET_DEG)
            )
            self._transport_car.set_heading_target(target_heading_deg)

    def _apply_orbit_velocity_correction(self) -> None:
        if not ORBIT_VISION_CORRECTION_ENABLED:
            return
        packet = self._latest_uart6_velocity
        if packet is None:
            return
        self._transport_car.set_orbit_velocity_correction(
            float(packet["vx"]),
            float(packet["vy"]),
        )

    def _apply_transport_velocity(self) -> None:
        packet = self._latest_uart6_velocity
        vx = 0.0
        vy = float(TRANSPORT_FORWARD_SPEED)
        if packet is not None:
            vx += float(packet.get("vx", 0.0))
            vy += float(packet.get("vy", 0.0))
        self._transport_car.handle_velocity_packet(
            vx,
            vy,
            0.0,
            "master_transport",
            False,
        )

    def _queue_transport_outputs(self) -> None:
        """提交本拍要发送的 hook、状态同步和前馈速度."""
        self._queue_pending_hook()
        self._queue_pending_sync()
        self._queue_feedforward_velocity()

    def _queue_pending_hook(self) -> None:
        pending = self._pending_hook
        if pending is None or pending.get("queued"):
            return
        body = encode_master_vision_hook_sync_body(
            pending["context_id"],
            pending["state"],
            pending["target"],
            pending["arg"],
        )
        status = self.transport_service.tcp(UART6).write(TOPIC_MASTER_VISION_HOOK_SYNC, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            self._log_hook_sync_start(pending)
            self._last_hook_sync_status = None
            pending["queued"] = True
            return
        if self._last_hook_sync_status == status:
            return
        self._last_hook_sync_status = status
        self._log_hook_sync_blocked(pending, status)

    def _queue_pending_sync(self) -> None:
        pending = self._pending_assistant_sync
        if pending is None:
            pending = self._pending_sync
        if pending is None or pending.get("queued"):
            return
        body = encode_assistant_state_sync_body(
            pending["state"],
            pending["target"],
            pending["arg"],
        )
        status = self.transport_service.tcp(UART8).write(TOPIC_ASSISTANT_STATE_SYNC, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            self._log_sync_start("master->assistant", pending)
            pending["queued"] = True

    def _queue_feedforward_velocity(self) -> None:
        """提交主车当前底盘速度前馈.

        @details 是否真正写出由 transport 的统一仲裁决定, 主车角色层不额外做发送互斥
        """
        if not self._state_machine.allows_assistant_velocity_forward():
            return
        if self._state_machine.needs_assistant_report_turn():
            return
        state = self._transport_car.control_state
        target = getattr(self._transport_car, "last_chassis_target", {})
        has_omega = bool(target.get("has_omega"))
        omega = float(state.get("omega", 0.0)) if has_omega else 0.0
        body = encode_velocity_body(
            state.get("vx", 0.0),
            state.get("vy", 0.0),
            omega,
            has_omega,
        )
        self.transport_service.udp(UART8).write(
            TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
            body,
        )

    def _advance_state_machine(self) -> None:
        orbit_finished = False
        if self._orbit_command_active:
            orbit_finished = not bool(getattr(self._transport_car, "command_lock", False))
        self._state_machine.step(orbit_finished)
        if self._state_machine.state != STATE_ORBITING:
            self._orbit_command_active = False

    def _drain_state_machine_outputs(self) -> None:
        """消费状态机一次性输出并刷新本拍业务意图."""
        hook_request = self._state_machine.poll_hook_request()
        if hook_request is not None:
            self._active_hook_context_id = None
            self._latest_uart6_velocity = None
            self._uart6_reset_version = self.transport_service.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            self._pending_hook_event = None
            self._transport_hook_acknowledged = False
            self._pending_hook = {
                "kind": hook_request.get("kind"),
                "context_id": int(hook_request["context_id"]),
                "state": int(hook_request["state"]),
                "target": int(hook_request["target"]),
                "arg": int(hook_request["arg"]),
                "queued": False,
            }
        assistant_request = self._state_machine.poll_assistant_request()
        if assistant_request is not None:
            request_kind = assistant_request.get("kind")
            if request_kind == "assistant_object":
                self._latest_uart6_velocity = None
                self._uart6_reset_version = self.transport_service.get_udp_version(
                    UART6, TOPIC_LOCAL_VISION_VELOCITY
                )
            elif request_kind == "assistant_follow":
                self._latest_uart6_velocity = None
                self._uart6_reset_version = self.transport_service.get_udp_version(
                    UART6, TOPIC_LOCAL_VISION_VELOCITY
                )
            elif request_kind == "assistant_transport":
                self._active_hook_context_id = None
                self._latest_uart6_velocity = None
                self._uart6_reset_version = self.transport_service.get_udp_version(
                    UART6, TOPIC_LOCAL_VISION_VELOCITY
                )
                self._pending_hook_event = None
                self._transport_sync_acknowledged = False
                self._transport_hook_acknowledged = False
                self._transport_car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    "master_wait_transport_ready",
                    True,
                )
                self._pending_hook = {
                    "kind": "transport_hook",
                    "context_id": int(self._state_machine._current_context_id),
                    "state": STATE_SEARCH_OBJECT,
                    "target": int(assistant_request["target"]),
                    "arg": int(MASTER_TRANSPORT_HOOK_CONFIG_ID),
                    "queued": False,
                }
            elif request_kind == "assistant_clear":
                self._latest_uart6_velocity = None
                self._uart6_reset_version = self.transport_service.get_udp_version(
                    UART6, TOPIC_LOCAL_VISION_VELOCITY
                )
                self._clear_sync_acknowledged = False
                self._clear_motion_started = False
                self._clear_master_completed_phase = None
                self._clear_motion_stop_ticks = 0
                self._transport_car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    "master_wait_clear_ready",
                    True,
                )
            self._pending_assistant_sync = {
                "kind": request_kind,
                "state": int(assistant_request["state"]),
                "target": int(assistant_request["target"]),
                "arg": int(assistant_request["arg"]),
                "queued": False,
            }

        orbit_command = self._state_machine.poll_orbit_command()
        if orbit_command is not None:
            self._active_hook_context_id = None
            self._latest_uart6_velocity = None
            self._uart6_reset_version = self.transport_service.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            self._pending_hook_event = None
            self._pending_hook = {
                "kind": "orbit_hook",
                "context_id": int(self._state_machine._current_context_id),
                "state": STATE_ORBITING,
                "target": TARGET_OBJECT,
                "arg": int(MASTER_ORBIT_HOOK_CONFIG_ID),
                "queued": False,
            }
            self._transport_car.set_orbit_target(
                float(orbit_command["target_heading_deg"]),
                float(MASTER_ORBIT_RADIUS_SCALE),
            )
            self._orbit_command_active = True

    def _run_clear_phase(self) -> None:
        if self._state_machine.state != STATE_CLEAR_OBJECT:
            self._clear_motion_started = False
            self._clear_master_completed_phase = None
            self._clear_motion_stop_ticks = 0
            self._turn_back_target_heading_deg = None
            return
        clear_phase = int(self._state_machine.get_clear_phase())
        if clear_phase != CLEAR_PHASE_RETREAT and clear_phase != CLEAR_PHASE_FORWARD:
            self._clear_motion_started = False
            self._clear_motion_stop_ticks = 0
            return
        if self._clear_motion_started:
            if bool(getattr(self._transport_car, "command_lock", False)):
                self._clear_motion_stop_ticks = 0
                return
            if not self._are_all_wheels_near_stop():
                self._clear_motion_stop_ticks = 0
                return
            self._clear_motion_stop_ticks += 1
            if self._clear_motion_stop_ticks < int(MOTION_STOP_CONFIRM_TICKS):
                return
            self._clear_motion_started = False
            self._clear_master_completed_phase = clear_phase
            self._clear_motion_stop_ticks = 0
            self._state_machine.mark_master_cleared()
            return
        if not self._clear_sync_acknowledged:
            return
        if self._clear_master_completed_phase == clear_phase:
            return
        if clear_phase == CLEAR_PHASE_RETREAT:
            self._transport_car.set_relative_translation_target(
                0.0,
                -float(TRANSPORT_CLEAR_RETREAT_DISTANCE_M),
                None,
                float(TRANSPORT_CLEAR_RETREAT_MAX_SPEED),
            )
        else:
            self._transport_car.set_relative_translation_target(
                0.0,
                float(TRANSPORT_CLEAR_STEP_DISTANCE_M),
                self._turn_back_target_heading_deg,
            )
        self._clear_motion_started = True
        self._clear_motion_stop_ticks = 0

    def _run_turn_back_phase(self) -> None:
        if not self._state_machine.is_post_clear_turn_back_pending():
            self._turn_back_rotation_started = False
            self._turn_back_stop_ticks = 0
            return
        if self._turn_back_rotation_started:
            if bool(getattr(self._transport_car, "command_lock", False)):
                self._turn_back_stop_ticks = 0
                return
            if not self._are_all_wheels_near_stop():
                self._turn_back_stop_ticks = 0
                return
            self._turn_back_stop_ticks += 1
            if self._turn_back_stop_ticks < int(MOTION_STOP_CONFIRM_TICKS):
                return
            self._turn_back_rotation_started = False
            self._turn_back_stop_ticks = 0
            self._state_machine.mark_turn_back_completed()
            return
        if not self._state_machine.can_start_turn_back_rotation():
            return
        target_heading_deg = (
            float(getattr(self._transport_car, "heading_est", 0.0))
            + float(MASTER_TURN_BACK_DELTA_DEG)
        )
        self._turn_back_target_heading_deg = target_heading_deg
        self._transport_car.set_heading_transition_target(target_heading_deg)
        self._turn_back_rotation_started = True
        self._turn_back_stop_ticks = 0

    def _are_all_wheels_near_stop(self) -> bool:
        wheel_states = getattr(self._transport_car, "wheel_states", ())
        if len(wheel_states) < 3:
            return False
        threshold = float(MOTION_STOP_SPEED_THRESHOLD)
        for state in wheel_states:
            if abs(float(state.get("filtered_speed", 0.0))) > threshold:
                return False
        return True

    def _drain_pending_hook_event(self) -> None:
        pending_event = self._pending_hook_event
        if pending_event is None:
            return
        self._pending_hook_event = None
        self._state_machine.handle_event(
            pending_event["context_id"],
            pending_event["event"],
            pending_event["value"],
        )

    def _log_sync_start(self, link_name: str, pending: dict) -> None:
        log(
            "sync",
            "%s sync start state=%d target=%d arg=%d"
            % (
                link_name,
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _log_sync_done(self, link_name: str, pending: dict) -> None:
        log(
            "sync",
            "%s sync done state=%d target=%d arg=%d"
            % (
                link_name,
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _log_hook_sync_start(self, pending: dict) -> None:
        log(
            "sync",
            "master->camera sync start context=%d state=%d target=%d arg=%d"
            % (
                int(pending["context_id"]),
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _log_hook_sync_done(self, pending: dict) -> None:
        log(
            "sync",
            "master->camera sync done context=%d state=%d target=%d arg=%d"
            % (
                int(pending["context_id"]),
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _log_hook_sync_blocked(self, pending: dict, status: str) -> None:
        log(
            "sync",
            "master->camera sync blocked status=%s context=%d state=%d target=%d arg=%d"
            % (
                status,
                int(pending["context_id"]),
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _record_error(self, text: str, exc: Exception) -> None:
        if self._last_error_text != text:
            log_exception("master_error", text, exc)
        self._last_error_text = text
        self._transport_car.last_exception_text = text
