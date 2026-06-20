"""辅车角色运行时主体

@file src/vision/assistant/follow_runtime.py
"""

import time

from config import motion as motion_params
from config import vision as vision_params
from protocol.codec import (
    LOCAL_VISION_CONTROL_PAUSE,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON,
    LOCAL_VISION_CONTROL_RESUME,
    decode_assistant_state_sync_body,
    decode_assistant_vision_event_report_body,
    decode_local_vision_control_body,
    decode_velocity_body,
    encode_assistant_event_report_body,
    encode_assistant_vision_task_sync_body,
    encode_local_vision_control_body,
)
from protocol.topic import (
    ROLE_ASSISTANT,
    TOPIC_ASSISTANT_EVENT_REPORT,
    TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
    TOPIC_ASSISTANT_STATE_SYNC,
    TOPIC_ASSISTANT_VISION_EVENT_REPORT,
    TOPIC_ASSISTANT_VISION_TASK_SYNC,
    TOPIC_LOCAL_VISION_CONTROL,
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
from play import PlayContext, PlayRunner
from play.routines.assistant_return_garage import AssistantReturnGaragePlay
from play.routines.startup_move import StartupMovePlay
from utils.startup_log import log, log_exception
from vision.assistant.diagnostics import build_follow_snapshot
from vision.assistant.state_machine import (
    ASSISTANT_STATE_APPROACH_OBJECT,
    ASSISTANT_STATE_CLEAR_OBJECT,
    ASSISTANT_STATE_FINISHED,
    ASSISTANT_STATE_FOLLOW,
    ASSISTANT_STATE_ORBIT,
    ASSISTANT_STATE_RETURN_FOLLOW,
    ASSISTANT_STATE_STARTUP_MOVE,
    ASSISTANT_STATE_TRANSPORT_OBJECT,
    ASSISTANT_TARGET_OBJECT,
    AssistantStateMachine,
)
from vision.clear_phase import CLEAR_PHASE_FORWARD, CLEAR_PHASE_RETREAT
from vision.task_sync import pack_task_arg, unpack_task_arg_config, unpack_task_arg_object_id


_TARGET_FOUND_EVENT = 6
_ALIGNED_EVENT = 7
_CLEARED_EVENT = 9
_RETURN_LINE_ALIGNED_EVENT = 10
_ASSISTANT_ORBIT_TARGET_DEG = getattr(motion_params, "ASSISTANT_ORBIT_TARGET_DEG")
_ASSISTANT_ORBIT_RADIUS_SCALE = getattr(motion_params, "ASSISTANT_ORBIT_RADIUS_SCALE")
_ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID = getattr(
    vision_params, "ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID"
)
_ASSISTANT_ORBIT_OBJECT_CONFIG_ID = getattr(
    vision_params, "ASSISTANT_ORBIT_OBJECT_CONFIG_ID"
)
ASSISTANT_RETURN_GARAGE_LINE_CONFIG_ID = getattr(
    vision_params, "ASSISTANT_RETURN_GARAGE_LINE_CONFIG_ID"
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

        car = TransportCar(vehicle_role=ROLE_ASSISTANT)
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
        self.play = PlayRunner()
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
        self._current_object_id = 0
        self._current_object_threshold = (0, 0, 0, 0, 0, 0)
        self._post_orbit_realign_active = False
        self._clear_completed = False
        self._clear_stop_ticks = 0
        self._velocity_body = bytearray(7)
        self._local_vision_control_body = bytearray(1)
        self._sync_body = bytearray(10)
        self._event_body = bytearray(3)
        self._local_vision_control_paused = False
        self._return_line_aligned = False
        self._return_line_gate_action = None
        self._return_play_context = PlayContext(
            set_position_x=self._play_set_position_x,
            set_position_y=self._play_set_position_y,
            set_angle=self._play_set_angle,
            write_velocity_y=self._play_write_velocity_y,
            is_position_x_done=self._play_motion_done,
            is_position_y_done=self._play_motion_done,
            is_angle_done=self._play_motion_done,
            yellow_line_ready=self._play_yellow_line_ready,
            clear_yellow_line_ready=self._play_clear_yellow_line_ready,
            enable_yellow_line_ready_gate=self._play_enable_yellow_line_ready_gate,
            disable_yellow_line_ready_gate=self._play_disable_yellow_line_ready_gate,
        )

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
        self._queue_return_line_gate_action()
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
        pending_gate = self._return_line_gate_action
        if pending_gate is not None and pending_gate.get("queued"):
            if (
                self.transport_service.tcp(UART6).delivery(TOPIC_LOCAL_VISION_CONTROL)
                == DELIVERY_DELIVERED
            ):
                log("assistant_gate", "done action=%d" % int(pending_gate["action"]))
                self._return_line_gate_action = None
        pending = self._pending_target_found_report
        if pending is not None and pending.get("queued"):
            if (
                self.transport_service.tcp(UART8).delivery(TOPIC_ASSISTANT_EVENT_REPORT)
                == DELIVERY_DELIVERED
            ):
                self._pending_target_found_report = None

    def _consume_master_sync(self) -> None:
        """消费主车下发的辅车状态同步."""
        if self._state_machine.state == ASSISTANT_STATE_STARTUP_MOVE:
            return
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
        if self._state_machine.state != ASSISTANT_STATE_RETURN_FOLLOW:
            self.play.current_play = None
            self._return_line_aligned = False
            self._return_line_gate_action = None
        self._clear_local_vision_pause_residue()
        if self._state_machine.is_idle():
            self._current_object_id = 0
            self._current_object_threshold = (0, 0, 0, 0, 0, 0)
            self._clear_motion_inputs()
            self._pending_local_vision_sync = None
            self._pending_target_found_report = None
            self._approach_target_found_done = False
            self._post_orbit_realign_active = False
            self._clear_completed = False
            self._write_zero_velocity("assistant_idle")
        elif self._state_machine.state == ASSISTANT_STATE_FOLLOW:
            self._current_object_id = 0
            self._current_object_threshold = (0, 0, 0, 0, 0, 0)
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
        elif self._state_machine.state == ASSISTANT_STATE_RETURN_FOLLOW:
            self._current_object_id = 0
            self._current_object_threshold = (0, 0, 0, 0, 0, 0)
            self._clear_motion_inputs()
            self._pending_target_found_report = None
            self._approach_target_found_done = False
            self._post_orbit_realign_active = False
            self._clear_completed = False
            self._return_line_aligned = False
            self._enter_return_follow_state()
        elif self._state_machine.state == ASSISTANT_STATE_FINISHED:
            self._current_object_id = 0
            self._current_object_threshold = (0, 0, 0, 0, 0, 0)
            self._clear_motion_inputs()
            self._pending_local_vision_sync = None
            self._pending_target_found_report = None
            self._approach_target_found_done = False
            self._post_orbit_realign_active = False
            self._clear_completed = False
            self._write_zero_velocity("assistant_finished")
        return True

    def _clear_local_vision_pause_residue(self) -> None:
        self._local_vision_control_paused = False
        self._uart6_velocity = None
        self._uart8_velocity = None
        self._uart6_reset_version = self.transport_service.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )
        self._uart8_reset_version = self.transport_service.get_udp_version(
            UART8, TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY
        )

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
        elif (
            self._state_machine.state == ASSISTANT_STATE_RETURN_FOLLOW
            and event == _RETURN_LINE_ALIGNED_EVENT
        ):
            self._return_line_aligned = True
            log("assistant_gate", "ready_on value=%d" % int(packet["value"]))

    def _consume_velocity_inputs(self) -> None:
        """消费两路 UDP 最新值速度输入.

        @details 通过版本号判断状态切换后的旧值是否仍应被忽略, 不直接清底层缓存
        """
        self._uart6_status = "idle"
        self._uart8_status = "idle"
        if (
            self.transport_service.tcp(UART6).read(
                TOPIC_LOCAL_VISION_CONTROL, self._local_vision_control_body
            )
            == "ok"
        ):
            packet = decode_local_vision_control_body(self._local_vision_control_body)
            self._handle_local_vision_control(packet)
        if (
            self.transport_service.udp(UART6).read(TOPIC_LOCAL_VISION_VELOCITY, self._velocity_body)
            == "ok"
        ):
            version = self.transport_service.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            if version > self._uart6_reset_version and not self._local_vision_control_paused:
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
            if version > self._uart8_reset_version and not self._local_vision_control_paused:
                self._uart8_velocity = decode_velocity_body(self._velocity_body)
                self._uart8_status = "active"

        if not self._should_store_velocity("uart6"):
            self._uart6_velocity = None
            self._uart6_status = "idle"
        if not self._should_store_velocity("uart8"):
            self._uart8_velocity = None
            self._uart8_status = "idle"

    def _handle_local_vision_control(self, packet: dict) -> None:
        """处理 OpenART 慢帧前后的可靠暂停控制."""

        action = int(packet.get("action", 0))
        if action == LOCAL_VISION_CONTROL_PAUSE and not self._allows_local_vision_control():
            self._local_vision_control_paused = False
            return
        self._uart6_velocity = None
        self._uart8_velocity = None
        self._uart6_reset_version = self.transport_service.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )
        self._uart8_reset_version = self.transport_service.get_udp_version(
            UART8, TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY
        )
        if action == LOCAL_VISION_CONTROL_PAUSE:
            self._local_vision_control_paused = True
            self._write_zero_velocity("local_vision_pause")
            return
        if action == LOCAL_VISION_CONTROL_RESUME:
            self._local_vision_control_paused = False

    def _allows_local_vision_control(self) -> bool:
        if self._state_machine.state == ASSISTANT_STATE_FOLLOW:
            return True
        if self._state_machine.state == ASSISTANT_STATE_APPROACH_OBJECT:
            return True
        if self._state_machine.state != ASSISTANT_STATE_ORBIT:
            return False
        return int(unpack_task_arg_config(self._state_machine.arg)) == int(
            _ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID
        )

    def _write_effective_velocity(self) -> None:
        if self._local_vision_control_paused:
            self._write_zero_velocity("local_vision_pause")
            return
        if self._state_machine.state == ASSISTANT_STATE_APPROACH_OBJECT:
            self._write_approach_object_velocity()
            return
        if self._state_machine.state == ASSISTANT_STATE_ORBIT:
            self._write_orbit_velocity_correction()
            return
        if self._state_machine.state == ASSISTANT_STATE_CLEAR_OBJECT:
            return
        if self._state_machine.state == ASSISTANT_STATE_FINISHED:
            self._write_zero_velocity("assistant_finished")
            return
        if self._state_machine.state == ASSISTANT_STATE_RETURN_FOLLOW:
            self._run_return_play()
            return
        if self._state_machine.state == ASSISTANT_STATE_STARTUP_MOVE:
            self._run_startup_move_play()
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
        if self._state_machine.state == ASSISTANT_STATE_FINISHED:
            return False
        if self._state_machine.state == ASSISTANT_STATE_RETURN_FOLLOW:
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
            "threshold": (0, 0, 0, 0, 0, 0),
            "queued": False,
        }

    def _enter_return_follow_state(self) -> None:
        self._write_zero_velocity("assistant_return_play")
        self._pending_local_vision_sync = {
            "state": ASSISTANT_STATE_RETURN_FOLLOW,
            "target": 0,
            "arg": int(ASSISTANT_RETURN_GARAGE_LINE_CONFIG_ID),
            "threshold": (0, 0, 0, 0, 0, 0),
            "queued": False,
        }

    def _run_return_play(self) -> None:
        if self.play.current_play is None:
            self.play.run(AssistantReturnGaragePlay)
        self.play.tick(self._return_play_context)

    def _run_startup_move_play(self) -> None:
        if self.play.current_play is None:
            self.play.run(StartupMovePlay)
        result = self.play.tick(self._return_play_context)
        if result.status == "finished":
            self._state_machine.mark_startup_move_completed()
            self._enter_follow_state()

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
            "assistant_play",
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
        self._current_object_id = unpack_task_arg_object_id(packet["arg"])
        self._current_object_threshold = tuple(
            packet.get("threshold", self._current_object_threshold)
        )
        self._approach_target_found_done = False
        self._pending_target_found_report = None
        self._clear_motion_inputs()
        self._write_zero_velocity("assistant_approach_object")
        self._pending_local_vision_sync = {
            "state": int(packet["state"]),
            "target": int(packet["target"]),
            "arg": int(packet["arg"]),
            "threshold": self._current_object_threshold,
            "queued": False,
        }

    def _enter_orbit_state(self) -> None:
        self._approach_target_found_done = False
        self._pending_target_found_report = None
        self._clear_motion_inputs()
        self._pending_local_vision_sync = {
            "state": ASSISTANT_STATE_ORBIT,
            "target": ASSISTANT_TARGET_OBJECT,
            "arg": pack_task_arg(
                _ASSISTANT_ORBIT_OBJECT_CONFIG_ID,
                self._current_object_id,
            ),
            "threshold": self._current_object_threshold,
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
        self._current_object_id = unpack_task_arg_object_id(packet["arg"])
        self._current_object_threshold = tuple(
            packet.get("threshold", self._current_object_threshold)
        )
        self._approach_target_found_done = False
        self._pending_target_found_report = None
        self._post_orbit_realign_active = False
        self._clear_completed = False
        self._clear_motion_inputs()
        self._write_zero_velocity("assistant_transport")
        self._pending_local_vision_sync = {
            "state": ASSISTANT_STATE_TRANSPORT_OBJECT,
            "target": int(packet["target"]),
            "arg": pack_task_arg(
                _ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
                self._current_object_id,
            ),
            "threshold": self._current_object_threshold,
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
            pack_task_arg(
                _ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
                self._current_object_id,
            ),
        )
        self._enter_approach_object_state(
            {
                "state": ASSISTANT_STATE_APPROACH_OBJECT,
                "target": ASSISTANT_TARGET_OBJECT,
                "arg": pack_task_arg(
                    _ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
                    self._current_object_id,
                ),
                "threshold": self._current_object_threshold,
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
            pending.get("threshold"),
        )
        status = self.transport_service.tcp(UART6).write(TOPIC_ASSISTANT_VISION_TASK_SYNC, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            self._log_local_vision_sync_start(pending)
            pending["queued"] = True

    def _queue_return_line_gate_action(self) -> None:
        pending = self._return_line_gate_action
        if pending is None or pending.get("queued"):
            return
        body = encode_local_vision_control_body(pending["action"])
        status = self.transport_service.tcp(UART6).write(TOPIC_LOCAL_VISION_CONTROL, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            log("assistant_gate", "start action=%d" % int(pending["action"]))
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
