"""主车角色运行时主体

@file src/vision/master/forward_runtime.py
"""

import time

from config import motion as motion_params
from config import vision as vision_params
from protocol.codec import (
    LOCAL_VISION_CONTROL_PAUSE,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON,
    LOCAL_VISION_CONTROL_RESUME,
    decode_assistant_event_report_body,
    decode_local_vision_control_body,
    decode_master_vision_event_report_body,
    decode_velocity_body,
    encode_assistant_state_sync_body,
    encode_local_vision_control_body,
    encode_master_vision_task_sync_body,
    encode_velocity_body,
)
from protocol.topic import (
    ROLE_MASTER,
    TOPIC_ASSISTANT_EVENT_REPORT,
    TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
    TOPIC_ASSISTANT_STATE_SYNC,
    TOPIC_LOCAL_VISION_VELOCITY,
    TOPIC_LOCAL_VISION_CONTROL,
    TOPIC_MASTER_VISION_EVENT_REPORT,
    TOPIC_MASTER_VISION_TASK_SYNC,
    UART6,
    UART8,
)
from protocol.transport import (
    DELIVERY_DELIVERED,
    WRITE_ACCEPTED,
    WRITE_OVERWRITTEN,
    create_transport,
)
from play import PlayContext, PlayRunner
from play.routines.master_return_garage import MasterReturnGaragePlay
from play.routines.startup_move import StartupMovePlay
from vision.clear_phase import CLEAR_PHASE_FORWARD, CLEAR_PHASE_RETREAT
from vision.master.state_machine import MasterStateMachine
from vision.master.state_machine import (
    EVENT_ALIGNED,
    EVENT_ARRIVED,
    EVENT_CLEARED,
    EVENT_RETURN_LINE_ALIGNED,
    EVENT_TARGET_FOUND,
    STATE_CLEAR_OBJECT,
    STATE_FINISHED,
    STATE_ORBITING,
    STATE_RETURN_GARAGE_LINE,
    STATE_RETURN_GARAGE_RETREAT,
    STATE_SEARCH_OBJECT,
    STATE_STARTUP_MOVE,
    STATE_STOP,
    STATE_TRANSPORT_OBJECT,
    TARGET_EDGE_LINE,
    TARGET_OBJECT,
)
from utils.startup_log import log, log_exception


MASTER_SEARCH_TASK_CONFIG_ID = getattr(vision_params, "MASTER_SEARCH_TASK_CONFIG_ID")
ASSISTANT_APPROACH_OBJECT_CONFIG_ID = getattr(
    vision_params,
    "ASSISTANT_APPROACH_OBJECT_CONFIG_ID",
)
ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID = getattr(
    vision_params,
    "ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID",
)
MASTER_TRANSPORT_TASK_CONFIG_ID = getattr(vision_params, "MASTER_TRANSPORT_TASK_CONFIG_ID")
MASTER_TRANSPORT_FINISH_TASK_CONFIG_ID = getattr(
    vision_params,
    "MASTER_TRANSPORT_FINISH_TASK_CONFIG_ID",
)
MASTER_ORBIT_TASK_CONFIG_ID = getattr(vision_params, "MASTER_ORBIT_TASK_CONFIG_ID")
MASTER_RETURN_GARAGE_LINE_TASK_CONFIG_ID = getattr(
    vision_params,
    "MASTER_RETURN_GARAGE_LINE_TASK_CONFIG_ID",
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
MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG = getattr(
    motion_params,
    "MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG",
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

        car = TransportCar(vehicle_role=ROLE_MASTER)
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
            search_task_arg=MASTER_SEARCH_TASK_CONFIG_ID,
            boot_heading_deg=float(getattr(car, "heading_est", 0.0)),
            orbit_delta_deg=MASTER_ORBIT_TARGET_DEG,
            assistant_object_arg=ASSISTANT_APPROACH_OBJECT_CONFIG_ID,
            assistant_transport_arg=ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
            transport_task_arg=MASTER_TRANSPORT_TASK_CONFIG_ID,
            finish_task_arg=MASTER_TRANSPORT_FINISH_TASK_CONFIG_ID,
            return_line_task_arg=MASTER_RETURN_GARAGE_LINE_TASK_CONFIG_ID,
            total_object_count=TRANSPORT_OBJECT_TOTAL_COUNT,
            initial_context_id=seed_value,
        )
        self._last_error_text = "none"
        self._latest_uart6_velocity = None
        self._uart6_reset_version = 0
        self._active_task_context_id = None
        self._pending_task_sync = None
        self._pending_task_event = None
        self._current_object_threshold = (0, 0, 0, 0, 0, 0)
        self._pending_sync = None
        self._pending_assistant_sync = None
        self._orbit_command_active = False
        self.play = PlayRunner()
        self._transport_sync_acknowledged = False
        self._transport_task_acknowledged = False
        self._clear_sync_acknowledged = False
        self._clear_motion_started = False
        self._clear_master_completed_phase = None
        self._clear_motion_stop_ticks = 0
        self._turn_back_rotation_started = False
        self._turn_back_stop_ticks = 0
        self._turn_back_target_heading_deg = None
        self._last_task_sync_status = None
        self._last_transport_flow_log = None
        self._last_feedforward_flow_log = None
        self._velocity_body = bytearray(7)
        self._local_vision_control_body = bytearray(1)
        self._task_event_body = bytearray(10)
        self._assistant_event_body = bytearray(3)
        self._local_vision_control_paused = False
        self._last_role_state = int(self._state_machine.state)
        self._return_line_aligned = False
        self._return_line_gate_action = None
        self._return_play_context = PlayContext(
            set_position_x=self._play_set_position_x,
            set_position_y=self._play_set_position_y,
            set_angle=self._play_set_angle,
            is_position_x_done=self._play_motion_done,
            write_velocity_y=self._play_write_velocity_y,
            is_position_y_done=self._play_motion_done,
            is_angle_done=self._play_motion_done,
            yellow_line_ready=self._play_yellow_line_ready,
            clear_yellow_line_ready=self._play_clear_yellow_line_ready,
            enable_yellow_line_ready_gate=self._play_enable_yellow_line_ready_gate,
            disable_yellow_line_ready_gate=self._play_disable_yellow_line_ready_gate,
        )
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
            "threshold": (0, 0, 0, 0, 0, 0),
            "queued": False,
        }
        self._pending_sync = pending
        return int(state)

    def _run_role_cycle(self) -> None:
        """执行主车单拍业务编排.

        @details 角色层只消费通信层缓存并提交新的业务意图, 不直接管理 UART 收发
        """
        self._check_transport_deliveries()
        self._sync_role_state_transition()
        self._advance_state_machine()
        self._sync_role_state_transition()
        self._drain_state_machine_outputs()
        self._consume_uart6_inputs()
        self._consume_uart8_inputs()
        self._check_transport_deliveries()
        self._sync_role_state_transition()
        self._drain_state_machine_outputs()
        self._apply_motion_outputs()
        self._run_clear_phase()
        self._sync_role_state_transition()
        self._run_turn_back_phase()
        self._sync_role_state_transition()
        self._drain_state_machine_outputs()
        self._queue_transport_outputs()

    def _sync_role_state_transition(self) -> None:
        current_state = int(self._state_machine.state)
        if current_state == int(self._last_role_state):
            return
        self._clear_local_vision_pause_residue()
        self._return_line_aligned = False
        if current_state != STATE_RETURN_GARAGE_RETREAT and current_state != STATE_STARTUP_MOVE:
            self._return_line_gate_action = None
            self.play.current_play = None
        self._last_role_state = current_state

    def _clear_local_vision_pause_residue(self) -> None:
        self._local_vision_control_paused = False
        self._latest_uart6_velocity = None
        self._uart6_reset_version = self.transport_service.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )

    def _consume_uart6_inputs(self) -> None:
        """消费本车视觉链路上的 UDP 速度与 TCP 事件."""
        if (
            self.transport_service.tcp(UART6).read(
                TOPIC_LOCAL_VISION_CONTROL, self._local_vision_control_body
            )
            == "ok"
        ):
            packet = decode_local_vision_control_body(self._local_vision_control_body)
            self._handle_local_vision_control(packet)
        if (
            self.transport_service.udp(UART6).read(
                TOPIC_LOCAL_VISION_VELOCITY, self._velocity_body
            )
            == "ok"
        ):
            version = self.transport_service.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            if version > self._uart6_reset_version and not self._local_vision_control_paused:
                packet = decode_velocity_body(self._velocity_body)
                if (
                    self._state_machine.allows_search_velocity()
                    or self._state_machine.state == STATE_TRANSPORT_OBJECT
                    or (
                        self._state_machine.state == STATE_ORBITING
                        and self._pending_task_sync is None
                    )
                ):
                    self._latest_uart6_velocity = packet
        if (
            self.transport_service.tcp(UART6).read(
                TOPIC_MASTER_VISION_EVENT_REPORT, self._task_event_body
            )
            == "ok"
        ):
            packet = decode_master_vision_event_report_body(self._task_event_body)
            self._handle_task_event(packet)

    def _handle_local_vision_control(self, packet: dict) -> None:
        """处理 OpenART 慢帧前后的可靠暂停控制."""

        action = int(packet.get("action", 0))
        if action == LOCAL_VISION_CONTROL_PAUSE and not self._allows_local_vision_control():
            self._local_vision_control_paused = False
            return
        self._latest_uart6_velocity = None
        self._uart6_reset_version = self.transport_service.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )
        if action == LOCAL_VISION_CONTROL_PAUSE:
            self._local_vision_control_paused = True
            if not bool(getattr(self._transport_car, "command_lock", False)):
                self._transport_car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    "local_vision_pause",
                    True,
                )
            return
        if action == LOCAL_VISION_CONTROL_RESUME:
            self._local_vision_control_paused = False

    def _allows_local_vision_control(self) -> bool:
        return int(self._state_machine.state) == int(STATE_SEARCH_OBJECT)

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

    def _handle_task_event(self, packet: dict) -> None:
        context_id = int(packet["context_id"])
        log(
            "master_event",
            "received context=%d event=%d value=%d"
            % (
                context_id,
                int(packet["event"]),
                int(packet["value"]),
            ),
        )
        if self._active_task_context_id == context_id:
            self._clear_local_velocity_for_reliable_event("master_vision_event")
            self._remember_task_event_threshold(packet)
            log(
                "master_event",
                "active context=%d state=%d event=%d value=%d"
                % (
                    context_id,
                    int(self._state_machine.state),
                    int(packet["event"]),
                    int(packet["value"]),
                ),
            )
            if (
                self._state_machine.state == STATE_RETURN_GARAGE_RETREAT
                and int(packet["event"]) == int(EVENT_RETURN_LINE_ALIGNED)
            ):
                self._return_line_aligned = True
                log(
                    "master_gate",
                    "ready_on context=%d value=%d"
                    % (context_id, int(packet["value"])),
                )
            self._state_machine.handle_event(
                context_id,
                packet["event"],
                packet["value"],
            )
            if int(packet["event"]) == int(EVENT_ARRIVED):
                log(
                    "master_finish",
                    "arrived context=%d state=%d value=%d"
                    % (
                        context_id,
                        int(self._state_machine.state),
                        int(packet["value"]),
                    ),
                )
                if self._state_machine.state != STATE_TRANSPORT_OBJECT:
                    self._active_task_context_id = None
                    self._latest_uart6_velocity = None
                    self._uart6_reset_version = self.transport_service.get_udp_version(
                        UART6, TOPIC_LOCAL_VISION_VELOCITY
                    )
            return
        if self._pending_task_sync is not None and context_id == int(self._pending_task_sync["context_id"]):
            self._clear_local_velocity_for_reliable_event("master_vision_event")
            log(
                "master_event",
                "pending context=%d state=%d event=%d value=%d"
                % (
                    context_id,
                    int(self._state_machine.state),
                    int(packet["event"]),
                    int(packet["value"]),
                ),
            )
            self._pending_task_event = {
                "context_id": context_id,
                "event": int(packet["event"]),
                "value": int(packet["value"]),
                "threshold": tuple(packet.get("threshold", (0, 0, 0, 0, 0, 0))),
            }
            return
        pending_context = -1
        if self._pending_task_sync is not None:
            pending_context = int(self._pending_task_sync["context_id"])
        active_context = -1
        if self._active_task_context_id is not None:
            active_context = int(self._active_task_context_id)
        log(
            "master_event",
            "drop context=%d active=%d pending=%d state=%d event=%d value=%d"
            % (
                context_id,
                active_context,
                pending_context,
                int(self._state_machine.state),
                int(packet["event"]),
                int(packet["value"]),
            ),
        )

    def _remember_task_event_threshold(self, packet: dict) -> None:
        threshold = tuple(packet.get("threshold", (0, 0, 0, 0, 0, 0)))
        if self._threshold_has_value(threshold):
            self._current_object_threshold = threshold

    def _threshold_has_value(self, threshold: tuple) -> bool:
        for value in threshold:
            if int(value) != 0:
                return True
        return False

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
        pending = self._pending_task_sync
        if pending is not None and pending.get("queued"):
            if (
                self.transport_service.tcp(UART6).delivery(TOPIC_MASTER_VISION_TASK_SYNC)
                == DELIVERY_DELIVERED
            ):
                self._log_task_sync_done(pending)
                self._active_task_context_id = int(pending["context_id"])
                if pending.get("kind") == "transport_task":
                    self._transport_task_acknowledged = True
                    if self._transport_sync_acknowledged:
                        self._state_machine.mark_transport_ready()
                elif self._state_machine.state == STATE_SEARCH_OBJECT:
                    self._state_machine.mark_restart_search_task_acknowledged()
                self._pending_task_sync = None
                self._drain_pending_task_event()
        pending_gate = self._return_line_gate_action
        if pending_gate is not None and pending_gate.get("queued"):
            if (
                self.transport_service.tcp(UART6).delivery(TOPIC_LOCAL_VISION_CONTROL)
                == DELIVERY_DELIVERED
            ):
                log("master_gate", "done action=%d" % int(pending_gate["action"]))
                self._return_line_gate_action = None

        pending = self._pending_assistant_sync
        if pending is not None and pending.get("queued"):
            if (
                self.transport_service.tcp(UART8).delivery(TOPIC_ASSISTANT_STATE_SYNC)
                == DELIVERY_DELIVERED
            ):
                self._log_sync_done("master->assistant", pending)
                if pending.get("kind") == "assistant_object":
                    self._state_machine.mark_assistant_object_acknowledged()
                elif pending.get("kind") == "assistant_startup":
                    self._state_machine.mark_startup_sync_acknowledged()
                elif pending.get("kind") == "assistant_follow":
                    self._state_machine.mark_assistant_follow_acknowledged()
                elif pending.get("kind") == "assistant_transport":
                    self._transport_sync_acknowledged = True
                    if self._transport_task_acknowledged:
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
        if self._local_vision_control_paused:
            if not bool(getattr(self._transport_car, "command_lock", False)):
                self._transport_car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    "local_vision_pause",
                    True,
                )
            return
        if self._state_machine.state == STATE_TRANSPORT_OBJECT:
            if not self._is_transport_finish_task_ready():
                self._transport_car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    "master_wait_finish_task",
                    True,
                )
                return
            self._apply_transport_velocity()
            return
        if self._state_machine.state == STATE_ORBITING:
            self._apply_orbit_velocity_correction()
            return
        if self._state_machine.state == STATE_CLEAR_OBJECT:
            if not self._clear_motion_started:
                self._transport_car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    "master_clear_hold",
                    True,
                )
            return
        if self._state_machine.state == STATE_RETURN_GARAGE_RETREAT:
            self._run_return_play()
            return
        if self._state_machine.state == STATE_STARTUP_MOVE:
            self._run_startup_move_play()
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

    def _is_transport_finish_task_ready(self) -> bool:
        return self._active_task_context_id == int(self._state_machine._current_context_id)

    def _run_return_play(self) -> None:
        if self.play.current_play is None:
            self.play.run(MasterReturnGaragePlay)
        self.play.tick(self._return_play_context)

    def _run_startup_move_play(self) -> None:
        if self.play.current_play is None:
            self.play.run(StartupMovePlay)
        result = self.play.tick(self._return_play_context)
        if result.status == "finished":
            self._state_machine.mark_startup_move_completed()

    def _play_set_position_x(self, value, max_speed_cmd=None) -> None:
        self._transport_car.set_relative_translation_target(
            float(value),
            0.0,
            max_speed_cmd=max_speed_cmd,
        )

    def _play_set_position_y(self, value, max_speed_cmd=None) -> None:
        self._transport_car.set_relative_translation_target(
            0.0,
            float(value),
            max_speed_cmd=max_speed_cmd,
        )

    def _play_set_angle(self, value) -> None:
        target_heading_deg = float(getattr(self._transport_car, "heading_est", 0.0)) + float(value)
        self._transport_car.set_heading_transition_target(target_heading_deg)

    def _play_write_velocity_y(self, value) -> None:
        self._transport_car.handle_velocity_packet(
            0.0,
            float(value),
            0.0,
            "master_play",
            False,
        )

    def _play_motion_done(self) -> bool:
        return not bool(getattr(self._transport_car, "command_lock", False))

    def _play_yellow_line_ready(self) -> bool:
        return bool(self._return_line_aligned)

    def _play_clear_yellow_line_ready(self) -> None:
        self._return_line_aligned = False

    def _play_enable_yellow_line_ready_gate(self) -> None:
        self._return_line_gate_action = {
            "action": LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON,
            "queued": False,
        }

    def _play_disable_yellow_line_ready_gate(self) -> None:
        self._return_line_gate_action = {
            "action": LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF,
            "queued": False,
        }

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
        self._log_transport_flow(vx, vy)
        self._transport_car.handle_velocity_packet(
            vx,
            vy,
            0.0,
            "master_transport",
            False,
        )

    def _queue_transport_outputs(self) -> None:
        """提交本拍要发送的 task、状态同步和前馈速度."""
        self._queue_pending_task_sync()
        self._queue_return_line_gate_action()
        self._queue_pending_sync()
        self._queue_feedforward_velocity()

    def _queue_pending_task_sync(self) -> None:
        pending = self._pending_task_sync
        if pending is None or pending.get("queued"):
            return
        body = encode_master_vision_task_sync_body(
            pending["context_id"],
            pending["state"],
            pending["target"],
            pending["arg"],
        )
        status = self.transport_service.tcp(UART6).write(TOPIC_MASTER_VISION_TASK_SYNC, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            self._log_task_sync_start(pending)
            self._last_task_sync_status = None
            pending["queued"] = True
            return
        if self._last_task_sync_status == status:
            return
        self._last_task_sync_status = status
        self._log_task_sync_blocked(pending, status)

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
            self._threshold_for_assistant_sync(pending),
        )
        status = self.transport_service.tcp(UART8).write(TOPIC_ASSISTANT_STATE_SYNC, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            self._log_sync_start("master->assistant", pending)
            pending["queued"] = True

    def _queue_return_line_gate_action(self) -> None:
        pending = self._return_line_gate_action
        if pending is None or pending.get("queued"):
            return
        body = encode_local_vision_control_body(pending["action"])
        status = self.transport_service.tcp(UART6).write(TOPIC_LOCAL_VISION_CONTROL, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            log("master_gate", "start action=%d" % int(pending["action"]))
            pending["queued"] = True

    def _queue_feedforward_velocity(self) -> None:
        """提交主车当前底盘速度前馈.

        @details 是否真正写出由 transport 的统一仲裁决定, 主车角色层不额外做发送互斥
        """
        if self._pending_assistant_sync is not None or self._pending_sync is not None:
            self._log_feedforward_flow("blocked_sync")
            return
        if (
            self._state_machine.state == STATE_TRANSPORT_OBJECT
            and not self._is_transport_finish_task_ready()
        ):
            self._log_feedforward_flow("blocked_finish_task")
            return
        if not self._state_machine.allows_assistant_velocity_forward():
            self._log_feedforward_flow("blocked_state")
            return
        if self._state_machine.needs_assistant_report_turn():
            self._log_feedforward_flow("blocked_report_turn")
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
        self._log_feedforward_flow("sent")

    def _advance_state_machine(self) -> None:
        orbit_finished = False
        if self._orbit_command_active:
            orbit_finished = not bool(getattr(self._transport_car, "command_lock", False))
        self._state_machine.step(orbit_finished)
        if self._state_machine.state != STATE_ORBITING:
            self._orbit_command_active = False

    def _drain_state_machine_outputs(self) -> None:
        """消费状态机一次性输出并刷新本拍业务意图."""
        task_request = self._state_machine.poll_task_request()
        if task_request is not None:
            self._active_task_context_id = None
            self._latest_uart6_velocity = None
            self._uart6_reset_version = self.transport_service.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            self._pending_task_event = None
            self._transport_task_acknowledged = False
            self._pending_task_sync = {
                "kind": task_request.get("kind"),
                "context_id": int(task_request["context_id"]),
                "state": int(task_request["state"]),
                "target": int(task_request["target"]),
                "arg": int(task_request["arg"]),
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
                self._active_task_context_id = None
                self._latest_uart6_velocity = None
                self._uart6_reset_version = self.transport_service.get_udp_version(
                    UART6, TOPIC_LOCAL_VISION_VELOCITY
                )
                self._pending_task_event = None
                self._transport_sync_acknowledged = False
                self._transport_task_acknowledged = False
                self._transport_car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    "master_wait_transport_ready",
                    True,
                )
                self._pending_task_sync = {
                    "kind": "transport_task",
                    "context_id": int(self._state_machine._current_context_id),
                    "state": STATE_SEARCH_OBJECT,
                    "target": int(assistant_request["target"]),
                    "arg": int(MASTER_TRANSPORT_TASK_CONFIG_ID),
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
                "threshold": self._threshold_for_assistant_request(assistant_request),
                "queued": False,
            }

        orbit_command = self._state_machine.poll_orbit_command()
        if orbit_command is not None:
            self._active_task_context_id = None
            self._latest_uart6_velocity = None
            self._uart6_reset_version = self.transport_service.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            self._pending_task_event = None
            self._pending_task_sync = {
                "kind": "orbit_task",
                "context_id": int(self._state_machine._current_context_id),
                "state": STATE_ORBITING,
                "target": TARGET_OBJECT,
                "arg": int(MASTER_ORBIT_TASK_CONFIG_ID),
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
                if self._is_turn_back_within_unlock_tolerance():
                    self._transport_car.handle_velocity_packet(
                        0.0,
                        0.0,
                        0.0,
                        "master_turn_back_tolerance",
                        True,
                    )
                    self._turn_back_rotation_started = False
                    self._turn_back_stop_ticks = 0
                    self._state_machine.mark_turn_back_completed()
                    return
                self._turn_back_stop_ticks = 0
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

    def _is_turn_back_within_unlock_tolerance(self) -> bool:
        target_deg = self._turn_back_target_heading_deg
        if target_deg is None:
            return False
        err_deg = float(target_deg) - float(
            getattr(self._transport_car, "heading_est", 0.0)
        )
        while err_deg >= 180.0:
            err_deg -= 360.0
        while err_deg < -180.0:
            err_deg += 360.0
        return abs(err_deg) <= float(MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG)

    def _are_all_wheels_near_stop(self) -> bool:
        wheel_states = getattr(self._transport_car, "wheel_states", ())
        if len(wheel_states) < 3:
            return False
        threshold = float(MOTION_STOP_SPEED_THRESHOLD)
        for state in wheel_states:
            if abs(float(state.get("filtered_speed", 0.0))) > threshold:
                return False
        return True

    def _drain_pending_task_event(self) -> None:
        pending_event = self._pending_task_event
        if pending_event is None:
            return
        self._pending_task_event = None
        self._remember_task_event_threshold(pending_event)
        self._state_machine.handle_event(
            pending_event["context_id"],
            pending_event["event"],
            pending_event["value"],
        )
        if (
            int(pending_event["event"]) == int(EVENT_ARRIVED)
            and self._state_machine.state != STATE_TRANSPORT_OBJECT
        ):
            self._active_task_context_id = None
            self._latest_uart6_velocity = None
            self._uart6_reset_version = self.transport_service.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )

    def _log_transport_flow(self, vx: float, vy: float) -> None:
        active_context = -1
        if self._active_task_context_id is not None:
            active_context = int(self._active_task_context_id)
        pending_kind = "none"
        pending_context = -1
        pending_queued = 0
        if self._pending_task_sync is not None:
            pending_kind = str(self._pending_task_sync.get("kind", "task"))
            pending_context = int(self._pending_task_sync["context_id"])
            pending_queued = 1 if bool(self._pending_task_sync.get("queued")) else 0
        signature = (
            int(self._state_machine.state),
            active_context,
            pending_kind,
            pending_context,
            pending_queued,
            int(self._transport_task_acknowledged),
            int(self._transport_sync_acknowledged),
        )
        if self._last_transport_flow_log == signature:
            return
        self._last_transport_flow_log = signature
        log(
            "master_transport",
            "drive state=%d active=%d pending_kind=%s pending=%d queued=%d task_ack=%d assistant_ack=%d vx=%.2f vy=%.2f"
            % (
                int(self._state_machine.state),
                active_context,
                pending_kind,
                pending_context,
                pending_queued,
                int(self._transport_task_acknowledged),
                int(self._transport_sync_acknowledged),
                float(vx),
                float(vy),
            ),
        )

    def _log_feedforward_flow(self, status: str) -> None:
        pending_kind = "none"
        pending_queued = 0
        if self._pending_assistant_sync is not None:
            pending_kind = str(self._pending_assistant_sync.get("kind", "sync"))
            pending_queued = 1 if bool(self._pending_assistant_sync.get("queued")) else 0
        elif self._pending_sync is not None:
            pending_kind = str(self._pending_sync.get("kind", "sync"))
            pending_queued = 1 if bool(self._pending_sync.get("queued")) else 0
        signature = (
            str(status),
            int(self._state_machine.state),
            pending_kind,
            pending_queued,
            int(self._state_machine.allows_assistant_velocity_forward()),
            int(self._state_machine.needs_assistant_report_turn()),
        )
        if self._last_feedforward_flow_log == signature:
            return
        self._last_feedforward_flow_log = signature
        log(
            "master_feedforward",
            "status=%s state=%d pending_kind=%s queued=%d allow=%d report_turn=%d"
            % (
                str(status),
                int(self._state_machine.state),
                pending_kind,
                pending_queued,
                int(self._state_machine.allows_assistant_velocity_forward()),
                int(self._state_machine.needs_assistant_report_turn()),
            ),
        )

    def _threshold_for_assistant_request(self, assistant_request: dict) -> tuple:
        if int(assistant_request.get("target", 0)) == TARGET_OBJECT:
            return tuple(self._current_object_threshold)
        return (0, 0, 0, 0, 0, 0)

    def _threshold_for_assistant_sync(self, pending: dict) -> tuple:
        if int(pending.get("target", 0)) == TARGET_OBJECT:
            return tuple(self._current_object_threshold)
        return tuple(pending.get("threshold", (0, 0, 0, 0, 0, 0)))

    def _log_sync_start(self, link_name: str, pending: dict) -> None:
        log(
            "sync",
            "%s sync start kind=%s state=%d target=%d arg=%d"
            % (
                link_name,
                str(pending.get("kind", "sync")),
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _log_sync_done(self, link_name: str, pending: dict) -> None:
        log(
            "sync",
            "%s sync done kind=%s state=%d target=%d arg=%d"
            % (
                link_name,
                str(pending.get("kind", "sync")),
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _log_task_sync_start(self, pending: dict) -> None:
        log(
            "sync",
            "master->camera sync start kind=%s context=%d state=%d target=%d arg=%d"
            % (
                str(pending.get("kind", "task")),
                int(pending["context_id"]),
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _log_task_sync_done(self, pending: dict) -> None:
        log(
            "sync",
            "master->camera sync done kind=%s context=%d state=%d target=%d arg=%d"
            % (
                str(pending.get("kind", "task")),
                int(pending["context_id"]),
                int(pending["state"]),
                int(pending["target"]),
                int(pending["arg"]),
            ),
        )

    def _log_task_sync_blocked(self, pending: dict, status: str) -> None:
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
