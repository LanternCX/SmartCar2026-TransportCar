"""辅车角色运行时主体

@file src/role/assistant/follow_runtime.py
"""

import time

from config import motion as motion_params
from config import vision as vision_params
from protocol.codec import (
    AE_EVENT,
    AE_VALUE,
    AS_ARG,
    AS_STATE,
    AS_TARGET,
    AS_TH,
    CTL_ACTION,
    LOCAL_VISION_CONTROL_PAUSE,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON,
    LOCAL_VISION_CONTROL_RESUME,
    VEL_HAS_W,
    VEL_W,
    VEL_X,
    VEL_Y,
    decode_assistant_state_sync_body,
    decode_assistant_vision_event_report_body,
    decode_local_vision_control_body,
    decode_velocity_body_into,
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
from utils.startup_log import log_exception
from role.assistant.state_machine import (
    ASSISTANT_STATE_APPROACH_OBJECT,
    ASSISTANT_STATE_CLEAR_OBJECT,
    ASSISTANT_STATE_FINISHED,
    ASSISTANT_STATE_FOLLOW,
    ASSISTANT_STATE_IDLE,
    ASSISTANT_STATE_ORBIT,
    ASSISTANT_STATE_RETURN_FOLLOW,
    ASSISTANT_STATE_STARTUP_MOVE,
    ASSISTANT_STATE_TRANSPORT_OBJECT,
    ASSISTANT_TARGET_OBJECT,
    AssistantStateMachine,
)
from role.clear_phase import CLEAR_PHASE_FORWARD, CLEAR_PHASE_RETREAT
from role.task_sync import pack_task_arg, unpack_task_arg_config, unpack_task_arg_object_id
from role.transport_plan import (
    heading_with_offset,
    push_heading_for_edge,
    target_edge_for_object,
)

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value


_TARGET_FOUND_EVENT = const(6)
_ALIGNED_EVENT = const(7)
_CLEARED_EVENT = const(9)
_RETURN_LINE_ALIGNED_EVENT = const(10)
_ASSISTANT_ORBIT_TARGET_DEG = motion_params.ASSISTANT_ORBIT_TARGET_DEG
_ASSISTANT_ORBIT_RADIUS_SCALE = motion_params.ASSISTANT_ORBIT_RADIUS_SCALE
_TRANSPORT_AVOIDANCE_DEMO_ENABLED = bool(motion_params.TRANSPORT_AVOIDANCE_DEMO_ENABLED)
_TRANSPORT_AVOIDANCE_ORBIT_OFFSET_DEG = motion_params.TRANSPORT_AVOIDANCE_ORBIT_OFFSET_DEG
_ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID = vision_params.ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID
_ASSISTANT_ORBIT_OBJECT_CONFIG_ID = vision_params.ASSISTANT_ORBIT_OBJECT_CONFIG_ID
ASSISTANT_RETURN_GARAGE_LINE_CONFIG_ID = (
    vision_params.ASSISTANT_RETURN_GARAGE_LINE_CONFIG_ID
)
ORBIT_VISION_CORRECTION_ENABLED = bool(vision_params.ORBIT_VISION_CORRECTION_ENABLED)
_ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE = (
    vision_params.ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE
)
_TRANSPORT_FORWARD_SPEED = motion_params.TRANSPORT_FORWARD_SPEED
_TRANSPORT_AVOIDANCE_SHIFT_DISTANCE_M = (
    motion_params.TRANSPORT_AVOIDANCE_SHIFT_DISTANCE_M
)
_TRANSPORT_CLEAR_STEP_DISTANCE_M = motion_params.TRANSPORT_CLEAR_STEP_DISTANCE_M
MOTION_STOP_SPEED_THRESHOLD = motion_params.MOTION_STOP_SPEED_THRESHOLD
MOTION_STOP_CONFIRM_TICKS = motion_params.MOTION_STOP_CONFIRM_TICKS

_L_STATE = const(0)
_L_TARGET = const(1)
_L_ARG = const(2)
_L_THRESHOLD = const(3)
_L_QUEUED = const(4)

_R_EVENT = const(0)
_R_VALUE = const(1)
_R_QUEUED = const(2)

_G_ACTION = const(0)
_G_QUEUED = const(1)
_SRC_U6 = const(6)
_SRC_U8 = const(8)


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
        # 主路径长期 owner 使用短字段：_car 是底盘，_sm 是辅车状态机。
        self._car = car
        self.wheel_encoders = car.wheel_encoders
        self.imu = car.imu
        self._now_ms = now_ms or _default_now_ms
        self._ts = transport or create_transport(
            ROLE_ASSISTANT,
            uart6=uart6,
            uart8=uart8,
            now_ms=self._now_ms,
        )
        self._sm = AssistantStateMachine()
        self.play_kind = 0
        self.play_step = 0
        self.play_entered = False
        self._err = "none"
        # UART 缓存短字段：_u6v/_u8v 是速度槽，_u6_ver/_u8_ver 是版本线。
        self._u6v = None
        self._u8v = None
        self._u6_pkt = [0.0, 0.0, 0.0, False]
        self._u8_pkt = [0.0, 0.0, 0.0, False]
        self._u6_ver = 0
        self._u8_ver = 0
        self._sync_apply_count = 0
        seed_value = int(self._now_ms()) % 256
        # 本地视觉同步和主车回报 pending；object/clear 为当前任务阶段状态。
        self._p_local = None
        self._p_report = None
        # object 状态保存当前目标、阈值和是否需要重新对齐。
        self._found_done = False
        self._last_approach_arg = 0
        self._obj_id = 0
        self._obj_th = (0, 0, 0, 0, 0, 0)
        self._realign = False
        self._av_orbit = False
        self._av_shift = False
        self._align_heading = float(_ASSISTANT_ORBIT_TARGET_DEG)
        self._shift_done = False
        self._shift_x = 0.0
        self._shift_y = 0.0
        # clear/tick 状态只用于当前清障阶段，不暴露给诊断输出。
        self._clear_done = False
        self._clear_ticks = 0
        # 复用发送缓冲，避免每次组包都创建新的 bytes 对象。
        self._vel_body = bytearray(7)
        self._ctrl_body = bytearray(1)
        self._sync_body = bytearray(10)
        self._event_body = bytearray(3)
        # 本地视觉门控与返回线状态，gate 保存待切换动作和是否已下发。
        self._lv_pause = False
        self._line_ok = False
        self._gate = None

    def prepare_runtime(self) -> None:
        from play import sequence as play_sequence

        play_sequence.clear(self)

    def mark_tick(self, tick=None) -> None:
        self._car.mark_tick(tick)

    def set_ticker(self, ticker_obj: object) -> None:
        self._car.set_ticker(ticker_obj)

    def has_pending_tick(self) -> bool:
        return self._car.has_pending_tick()

    def step_control(self) -> bool:
        return self._car.step_control()

    def collect_garbage(self) -> None:
        self._car.collect_garbage()

    def poll_transport_rx(self) -> None:
        self._ts.poll_rx()

    def poll_transport_tx(self) -> None:
        self._ts.poll_tx()

    def step_motion_input(self) -> bool:
        try:
            self._run_motion_input_cycle()
        except Exception as exc:
            self._record_error_text("motion_input failed: %s" % exc, exc)
        self._finish_clear_if_needed()
        self._finish_shift_if_needed()
        self._resume_approach_after_orbit()
        return True

    def step_role(self) -> bool:
        try:
            self._run_role_cycle()
        except Exception as exc:
            self._record_error_text("role_cycle failed: %s" % exc, exc)
        return True

    def step(self) -> bool:
        self.step_role()
        self.step_motion_input()
        keep_running = self._car.step()
        return keep_running

    def _run_motion_input_cycle(self) -> None:
        """执行视觉速度输入和底盘目标写入."""
        self._consume_velocity_inputs()
        self._write_effective_velocity()

    def _run_role_cycle(self) -> None:
        """执行辅车单拍业务编排.

        @details 辅车只从通信层读取主车同步、本地视觉事件和速度输入, 再提交新的业务回报
        """
        self._check_transport_deliveries()
        self._consume_master_sync()
        self._consume_local_vision_event()
        self._queue_pending_local_vision_sync()
        self._queue_return_line_gate_action()
        self._queue_pending_report()

    def _check_transport_deliveries(self) -> None:
        """根据通信层交付状态释放本地视觉同步和主车回报槽."""
        pending = self._p_local
        if pending is not None and pending[_L_QUEUED]:
            if (
                self._ts.tcp_delivery(UART6, TOPIC_ASSISTANT_VISION_TASK_SYNC)
                == DELIVERY_DELIVERED
            ):
                self._p_local = None
        pending_gate = self._gate
        if pending_gate is not None and pending_gate[_G_QUEUED]:
            if (
                self._ts.tcp_delivery(UART6, TOPIC_LOCAL_VISION_CONTROL)
                == DELIVERY_DELIVERED
            ):
                self._gate = None
        pending = self._p_report
        if pending is not None and pending[_R_QUEUED]:
            if (
                self._ts.tcp_delivery(UART8, TOPIC_ASSISTANT_EVENT_REPORT)
                == DELIVERY_DELIVERED
            ):
                self._p_report = None

    def _consume_master_sync(self) -> None:
        """消费主车下发的辅车状态同步."""
        if (
            self._ts.tcp_read(
                UART8,
                TOPIC_ASSISTANT_STATE_SYNC, self._sync_body
            )
            != "ok"
        ):
            return
        packet = decode_assistant_state_sync_body(self._sync_body)
        state, _, _, _ = packet
        accepted = self._apply_sync_context(packet)
        if not accepted:
            text = "unknown assistant sync state: %s" % int(state)
            self._record_error_text(text, RuntimeError(text))
            return
        self._sync_apply_count += 1

    def _apply_sync_context(self, packet) -> bool:
        state, target, arg, _ = packet
        accepted = self._sm.apply_master_state(
            state, target, arg
        )
        if not accepted:
            return False
        if self._sm.state != ASSISTANT_STATE_RETURN_FOLLOW:
            from play import sequence as play_sequence

            play_sequence.clear(self)
            self._line_ok = False
            self._gate = None
        self._clear_local_vision_pause_residue()
        if self._sm.is_idle():
            self._obj_id = 0
            self._obj_th = (0, 0, 0, 0, 0, 0)
            self._clear_motion_inputs()
            self._p_local = None
            self._p_report = None
            self._found_done = False
            self._realign = False
            self._av_orbit = False
            self._av_shift = False
            self._align_heading = float(_ASSISTANT_ORBIT_TARGET_DEG)
            self._shift_done = False
            self._clear_done = False
            self._write_zero_velocity()
        elif self._sm.state == ASSISTANT_STATE_FOLLOW:
            self._obj_id = 0
            self._obj_th = (0, 0, 0, 0, 0, 0)
            self._clear_motion_inputs()
            self._p_report = None
            self._found_done = False
            self._realign = False
            self._av_orbit = False
            self._av_shift = False
            self._align_heading = float(_ASSISTANT_ORBIT_TARGET_DEG)
            self._shift_done = False
            self._clear_done = False
            self._enter_follow_state()
        elif self._sm.state == ASSISTANT_STATE_STARTUP_MOVE:
            self._clear_motion_inputs()
            self._p_local = None
            self._p_report = None
            self._found_done = False
            self._realign = False
            self._av_orbit = False
            self._av_shift = False
            self._align_heading = float(_ASSISTANT_ORBIT_TARGET_DEG)
            self._shift_done = False
            self._clear_done = False
        elif self._sm.state == ASSISTANT_STATE_APPROACH_OBJECT:
            self._av_shift = False
            self._shift_done = False
            self._realign = False
            self._clear_done = False
            self._enter_approach_object_state(packet)
        elif self._sm.state == ASSISTANT_STATE_ORBIT:
            self._realign = False
            self._clear_done = False
            self._enter_orbit_state()
        elif self._sm.state == ASSISTANT_STATE_TRANSPORT_OBJECT:
            self._realign = False
            self._clear_done = False
            self._enter_transport_state(packet)
        elif self._sm.state == ASSISTANT_STATE_CLEAR_OBJECT:
            self._realign = False
            self._enter_clear_object_state()
        elif self._sm.state == ASSISTANT_STATE_RETURN_FOLLOW:
            self._obj_id = 0
            self._obj_th = (0, 0, 0, 0, 0, 0)
            self._clear_motion_inputs()
            self._p_report = None
            self._found_done = False
            self._realign = False
            self._av_orbit = False
            self._av_shift = False
            self._align_heading = float(_ASSISTANT_ORBIT_TARGET_DEG)
            self._shift_done = False
            self._clear_done = False
            self._line_ok = False
            self._enter_return_follow_state()
        elif self._sm.state == ASSISTANT_STATE_FINISHED:
            self._obj_id = 0
            self._obj_th = (0, 0, 0, 0, 0, 0)
            self._clear_motion_inputs()
            self._p_local = None
            self._p_report = None
            self._found_done = False
            self._realign = False
            self._av_orbit = False
            self._av_shift = False
            self._align_heading = float(_ASSISTANT_ORBIT_TARGET_DEG)
            self._shift_done = False
            self._clear_done = False
            self._write_zero_velocity()
        return True

    def _clear_local_vision_pause_residue(self) -> None:
        self._lv_pause = False
        self._u6v = None
        self._u8v = None
        self._u6_ver = self._ts.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )
        self._u8_ver = self._ts.get_udp_version(
            UART8, TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY
        )

    def _consume_local_vision_event(self) -> None:
        """消费本地视觉的可靠事件回报."""
        if (
            self._ts.tcp_read(
                UART6,
                TOPIC_ASSISTANT_VISION_EVENT_REPORT, self._event_body
            )
            != "ok"
        ):
            return
        packet = decode_assistant_vision_event_report_body(self._event_body)
        event = int(packet[AE_EVENT])
        if (
            self._sm.state == ASSISTANT_STATE_APPROACH_OBJECT
            and event == _TARGET_FOUND_EVENT
            and not self._found_done
            and not self._realign
        ):
            self._handle_local_target_found(packet[AE_VALUE])
        elif (
            self._sm.state == ASSISTANT_STATE_APPROACH_OBJECT
            and event == _ALIGNED_EVENT
            and self._realign
            and not self._found_done
        ):
            self._handle_local_aligned(packet[AE_VALUE])
        elif (
            self._sm.state == ASSISTANT_STATE_RETURN_FOLLOW
            and event == _RETURN_LINE_ALIGNED_EVENT
        ):
            self._line_ok = True

    def _consume_velocity_inputs(self) -> None:
        """消费两路 UDP 最新值速度输入.

        @details 通过版本号判断状态切换后的旧值是否仍应被忽略, 不直接清底层缓存
        """
        if (
            self._ts.tcp_read(
                UART6,
                TOPIC_LOCAL_VISION_CONTROL, self._ctrl_body
            )
            == "ok"
        ):
            packet = decode_local_vision_control_body(self._ctrl_body)
            self._handle_local_vision_control(packet)
        if (
            self._ts.udp_read(UART6, TOPIC_LOCAL_VISION_VELOCITY, self._vel_body)
            == "ok"
        ):
            version = self._ts.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            if version > self._u6_ver and not self._lv_pause:
                self._u6v = decode_velocity_body_into(
                    self._vel_body, self._u6_pkt
                )
                self._u6v[VEL_W] = 0.0
                self._u6v[VEL_HAS_W] = False
        if (
            self._ts.udp_read(
                UART8,
                TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
                self._vel_body,
            )
            == "ok"
        ):
            version = self._ts.get_udp_version(
                UART8, TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY
            )
            if version > self._u8_ver and not self._lv_pause:
                self._u8v = decode_velocity_body_into(
                    self._vel_body, self._u8_pkt
                )

        if not self._should_store_velocity(_SRC_U6):
            self._u6v = None
        if not self._should_store_velocity(_SRC_U8):
            self._u8v = None

    def _handle_local_vision_control(self, packet) -> None:
        """处理 OpenART 慢帧前后的可靠暂停控制."""

        action = int(packet[CTL_ACTION])
        if self._sm.state == ASSISTANT_STATE_ORBIT:
            self._clear_local_vision_pause_residue()
            return
        if action == LOCAL_VISION_CONTROL_PAUSE and not self._allows_local_vision_control():
            self._lv_pause = False
            return
        self._u6v = None
        self._u8v = None
        self._u6_ver = self._ts.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )
        self._u8_ver = self._ts.get_udp_version(
            UART8, TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY
        )
        if action == LOCAL_VISION_CONTROL_PAUSE:
            self._lv_pause = True
            self._write_zero_velocity()
            return
        if action == LOCAL_VISION_CONTROL_RESUME:
            self._lv_pause = False

    def _allows_local_vision_control(self) -> bool:
        if self._sm.state == ASSISTANT_STATE_FOLLOW:
            return True
        if self._sm.state == ASSISTANT_STATE_APPROACH_OBJECT:
            return True
        if self._sm.state != ASSISTANT_STATE_ORBIT:
            return False
        return int(unpack_task_arg_config(self._sm.arg)) == int(
            _ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID
        )

    def _write_effective_velocity(self) -> None:
        if self._lv_pause:
            self._write_zero_velocity()
            return
        if self._sm.state == ASSISTANT_STATE_APPROACH_OBJECT:
            self._write_approach_object_velocity()
            return
        if self._sm.state == ASSISTANT_STATE_ORBIT:
            self._write_orbit_velocity_correction()
            return
        if self._sm.state == ASSISTANT_STATE_CLEAR_OBJECT:
            return
        if self._sm.state == ASSISTANT_STATE_FINISHED:
            self._write_zero_velocity()
            return
        if self._sm.state == ASSISTANT_STATE_RETURN_FOLLOW:
            self._run_return_play()
            return
        if self._sm.state == ASSISTANT_STATE_STARTUP_MOVE:
            self._run_startup_move_play()
            return
        if self._sm.state == ASSISTANT_STATE_TRANSPORT_OBJECT:
            self._write_transport_object_velocity()
            return
        uart6_velocity = self._u6v
        uart8_velocity = self._u8v
        if uart6_velocity is None and uart8_velocity is None:
            return
        if uart6_velocity is None:
            uart6_velocity = (0.0, 0.0, 0.0, False)
        if uart8_velocity is None:
            uart8_velocity = (0.0, 0.0, 0.0, False)
        vx = float(uart6_velocity[VEL_X]) + float(uart8_velocity[VEL_X])
        vy = float(uart6_velocity[VEL_Y]) + float(uart8_velocity[VEL_Y])
        omega = 0.0
        if uart8_velocity[VEL_HAS_W]:
            omega = float(uart8_velocity[VEL_W])
        self._apply_effective_velocity(vx, vy, omega, bool(uart8_velocity[VEL_HAS_W]))

    def _write_approach_object_velocity(self) -> None:
        if self._p_local is not None or self._found_done:
            return
        uart6_velocity = self._u6v
        if uart6_velocity is None:
            return
        self._apply_effective_velocity(
            float(uart6_velocity[VEL_X]),
            float(uart6_velocity[VEL_Y]),
            0.0,
            False,
        )

    def _write_transport_object_velocity(self) -> None:
        uart6_velocity = self._u6v
        vx = 0.0
        scale = float(_ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE)
        vy = -float(_TRANSPORT_FORWARD_SPEED) * scale
        if uart6_velocity is not None:
            vx += float(uart6_velocity[VEL_X])
        self._apply_effective_velocity(vx, vy, 0.0, False)

    def _write_orbit_velocity_correction(self) -> None:
        if not ORBIT_VISION_CORRECTION_ENABLED:
            return
        if not bool(getattr(self._car, "orbit_mode", False)):
            return
        if self._p_local is not None:
            return
        uart6_velocity = self._u6v
        if uart6_velocity is None:
            return
        self._car.set_orbit_velocity_correction(
            float(uart6_velocity[VEL_X]),
            float(uart6_velocity[VEL_Y]),
        )

    def _apply_effective_velocity(self, vx: float, vy: float, omega: float, has_omega: bool) -> None:
        self._car.handle_velocity_packet(
            vx,
            vy,
            omega,
            None,
            has_omega,
        )
        if (
            self._sm.state == ASSISTANT_STATE_APPROACH_OBJECT
            and self._realign
        ):
            self._car.set_heading_target(float(self._align_heading))

    def _should_store_velocity(self, source) -> bool:
        if self._sm.state == ASSISTANT_STATE_IDLE:
            return False
        if self._sm.state == ASSISTANT_STATE_STARTUP_MOVE:
            return False
        if self._sm.state == ASSISTANT_STATE_ORBIT:
            return source == _SRC_U6 and self._p_local is None
        if self._sm.state == ASSISTANT_STATE_CLEAR_OBJECT:
            return False
        if self._sm.state == ASSISTANT_STATE_FINISHED:
            return False
        if self._sm.state == ASSISTANT_STATE_RETURN_FOLLOW:
            return False
        if source == _SRC_U6 and self._p_local is not None:
            return False
        if self._sm.state == ASSISTANT_STATE_TRANSPORT_OBJECT:
            return True
        if self._sm.state != ASSISTANT_STATE_APPROACH_OBJECT:
            return True
        if source == _SRC_U8:
            return False
        if self._p_local is not None:
            return False
        if self._found_done:
            return False
        return True

    def _clear_motion_inputs(self) -> None:
        """在状态切换时丢弃当前业务视角下的旧速度输入."""
        self._u6v = None
        self._u8v = None
        self._u6_ver = self._ts.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )
        self._u8_ver = self._ts.get_udp_version(
            UART8, TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY
        )

    def _enter_follow_state(self) -> None:
        self._write_zero_velocity()
        self._p_local = (
            ASSISTANT_STATE_FOLLOW,
            0,
            0,
            (0, 0, 0, 0, 0, 0),
            False,
        )

    def _enter_return_follow_state(self) -> None:
        self._write_zero_velocity()
        self._p_local = (
            ASSISTANT_STATE_RETURN_FOLLOW,
            0,
            int(ASSISTANT_RETURN_GARAGE_LINE_CONFIG_ID),
            (0, 0, 0, 0, 0, 0),
            False,
        )

    def _run_return_play(self) -> None:
        from play import sequence as play_sequence

        play_sequence.start(self, play_sequence.PLAY_ASSISTANT_RETURN)
        play_sequence.tick(self)

    def _run_startup_move_play(self) -> None:
        from play import sequence as play_sequence

        play_sequence.start(self, play_sequence.PLAY_STARTUP)
        if play_sequence.tick(self):
            self._sm.mark_startup_move_completed()
            self._enter_follow_state()

    def play_set_position_x(self, value, max_speed_cmd=None) -> None:
        self._car.set_relative_translation_target(
            float(value),
            0.0,
            max_speed_cmd=max_speed_cmd,
        )

    def play_set_position_y(self, value, max_speed_cmd=None) -> None:
        self._car.set_relative_translation_target(
            0.0,
            float(value),
            max_speed_cmd=max_speed_cmd,
        )

    def play_set_angle(self, value) -> None:
        target_heading_deg = float(value)
        self._car.set_heading_transition_target(target_heading_deg)

    def play_write_velocity_y(self, value) -> None:
        self._car.handle_velocity_packet(
            0.0,
            float(value),
            0.0,
            None,
            False,
        )

    def play_motion_done(self) -> bool:
        return not bool(getattr(self._car, "command_lock", False))

    def play_yellow_line_ready(self) -> bool:
        return bool(self._line_ok)

    def play_clear_yellow_line_ready(self) -> None:
        self._line_ok = False

    def play_enable_yellow_line_ready_gate(self) -> None:
        self._gate = (LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON, False)

    def play_disable_yellow_line_ready_gate(self) -> None:
        self._gate = (LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF, False)

    def _write_zero_velocity(self) -> None:
        self._car.handle_velocity_packet(
            0.0,
            0.0,
            0.0,
            None,
            True,
        )

    def _enter_approach_object_state(self, packet) -> None:
        self._last_approach_arg = int(packet[AS_ARG])
        self._obj_id = unpack_task_arg_object_id(packet[AS_ARG])
        self._obj_th = tuple(packet[AS_TH])
        self._found_done = False
        self._p_report = None
        self._clear_motion_inputs()
        self._write_zero_velocity()
        self._p_local = (
            int(packet[AS_STATE]),
            int(packet[AS_TARGET]),
            int(packet[AS_ARG]),
            self._obj_th,
            False,
        )

    def _enter_orbit_state(self) -> None:
        self._found_done = False
        self._p_report = None
        self._clear_motion_inputs()
        self._obj_id = unpack_task_arg_object_id(self._sm.arg)
        self._p_local = (
            ASSISTANT_STATE_ORBIT,
            ASSISTANT_TARGET_OBJECT,
            pack_task_arg(
                _ASSISTANT_ORBIT_OBJECT_CONFIG_ID,
                self._obj_id,
            ),
            self._obj_th,
            False,
        )
        orbit_target = float(_ASSISTANT_ORBIT_TARGET_DEG)
        self._av_orbit = (
            bool(_TRANSPORT_AVOIDANCE_DEMO_ENABLED)
            and int(unpack_task_arg_config(self._sm.arg)) == 0
        )
        if self._av_orbit:
            orbit_target = heading_with_offset(
                push_heading_for_edge(target_edge_for_object(self._obj_id)),
                -float(_TRANSPORT_AVOIDANCE_ORBIT_OFFSET_DEG),
            )
        self._align_heading = float(orbit_target)
        self._car.set_orbit_target(
            orbit_target,
            float(_ASSISTANT_ORBIT_RADIUS_SCALE),
        )

    def _handle_local_target_found(self, value: int) -> None:
        self._found_done = True
        self._u6v = None
        self._write_zero_velocity()
        self._p_report = (_TARGET_FOUND_EVENT, int(value), False)

    def _handle_local_aligned(self, value: int) -> None:
        self._found_done = True
        self._u6v = None
        self._write_zero_velocity()
        self._p_report = (_ALIGNED_EVENT, int(value), False)

    def _enter_transport_state(self, packet) -> None:
        self._obj_id = unpack_task_arg_object_id(packet[AS_ARG])
        self._obj_th = tuple(packet[AS_TH])
        self._found_done = False
        self._p_report = None
        self._realign = False
        self._clear_done = False
        self._clear_motion_inputs()
        self._write_zero_velocity()
        if self._av_shift:
            self._shift_done = False
            self._shift_x = float(self._car.odometry.x)
            self._shift_y = float(self._car.odometry.y)
        self._p_local = (
            ASSISTANT_STATE_TRANSPORT_OBJECT,
            int(packet[AS_TARGET]),
            pack_task_arg(
                _ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
                self._obj_id,
            ),
            self._obj_th,
            False,
        )

    def _enter_clear_object_state(self) -> None:
        self._found_done = False
        self._p_local = None
        self._p_report = None
        self._realign = False
        self._clear_done = False
        self._clear_ticks = 0
        self._clear_motion_inputs()
        self._car.calibrate_pose_to_field_edge(
            target_edge_for_object(self._obj_id)
        )
        clear_phase = int(self._sm.arg)
        if clear_phase == CLEAR_PHASE_RETREAT:
            self._car.set_relative_translation_target(
                0.0,
                -float(_TRANSPORT_CLEAR_STEP_DISTANCE_M) * 0.5,
            )
            return
        if clear_phase == CLEAR_PHASE_FORWARD:
            self._car.set_relative_translation_target(
                0.0,
                float(_TRANSPORT_CLEAR_STEP_DISTANCE_M),
            )

    def _resume_approach_after_orbit(self) -> None:
        if self._sm.state != ASSISTANT_STATE_ORBIT:
            return
        if bool(getattr(self._car, "command_lock", False)):
            return
        if self._realign:
            return
        av_orbit = self._av_orbit
        if av_orbit:
            self._av_orbit = False
            self._av_shift = True
        if not av_orbit and self._last_approach_arg <= 0:
            return
        self._sm.apply_master_state(
            ASSISTANT_STATE_APPROACH_OBJECT,
            ASSISTANT_TARGET_OBJECT,
            pack_task_arg(
                _ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
                self._obj_id,
            ),
        )
        self._enter_approach_object_state(
            (
                ASSISTANT_STATE_APPROACH_OBJECT,
                ASSISTANT_TARGET_OBJECT,
                pack_task_arg(
                    _ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
                    self._obj_id,
                ),
                self._obj_th,
            )
        )
        self._realign = True

    def _finish_clear_if_needed(self) -> None:
        if self._sm.state != ASSISTANT_STATE_CLEAR_OBJECT:
            self._clear_ticks = 0
            return
        if self._clear_done:
            self._clear_ticks = 0
            return
        if bool(getattr(self._car, "command_lock", False)):
            self._clear_ticks = 0
            return
        if not self._are_all_wheels_near_stop():
            self._clear_ticks = 0
            return
        self._clear_ticks += 1
        if self._clear_ticks < int(MOTION_STOP_CONFIRM_TICKS):
            return
        self._clear_ticks = 0
        self._clear_done = True
        self._write_zero_velocity()
        self._p_report = (
            _CLEARED_EVENT,
            int(self._sm.arg),
            False,
        )

    def _finish_shift_if_needed(self) -> None:
        if self._sm.state != ASSISTANT_STATE_TRANSPORT_OBJECT:
            return
        if not self._av_shift:
            return
        if self._shift_done:
            return
        if self._p_report is not None:
            return
        dx = float(self._car.odometry.x) - float(self._shift_x)
        dy = float(self._car.odometry.y) - float(self._shift_y)
        target = float(_TRANSPORT_AVOIDANCE_SHIFT_DISTANCE_M)
        if dx * dx + dy * dy < target * target:
            return
        self._shift_done = True
        self._write_zero_velocity()
        self._p_report = (_CLEARED_EVENT, 0, False)

    def _are_all_wheels_near_stop(self) -> bool:
        return bool(self._car.wheel_stop_confirmed(MOTION_STOP_SPEED_THRESHOLD))

    def _queue_pending_local_vision_sync(self) -> None:
        pending = self._p_local
        if pending is None or pending[_L_QUEUED]:
            return
        body = encode_assistant_vision_task_sync_body(
            pending[_L_STATE],
            pending[_L_TARGET],
            pending[_L_ARG],
            pending[_L_THRESHOLD],
        )
        status = self._ts.tcp_write(UART6, TOPIC_ASSISTANT_VISION_TASK_SYNC, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            self._p_local = (
                pending[_L_STATE],
                pending[_L_TARGET],
                pending[_L_ARG],
                pending[_L_THRESHOLD],
                True,
            )

    def _queue_return_line_gate_action(self) -> None:
        pending = self._gate
        if pending is None or pending[_G_QUEUED]:
            return
        body = encode_local_vision_control_body(pending[_G_ACTION])
        status = self._ts.tcp_write(UART6, TOPIC_LOCAL_VISION_CONTROL, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            self._gate = (pending[_G_ACTION], True)

    def _queue_pending_report(self) -> None:
        pending = self._p_report
        if pending is None or pending[_R_QUEUED]:
            return
        body = encode_assistant_event_report_body(
            pending[_R_EVENT],
            pending[_R_VALUE],
        )
        status = self._ts.tcp_write(UART8, TOPIC_ASSISTANT_EVENT_REPORT, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            self._p_report = (pending[_R_EVENT], pending[_R_VALUE], True)

    def _record_error_text(self, text: str, exc: Exception) -> None:
        if self._err != text:
            log_exception("assistant_error", text, exc)
        self._err = text
        self._car.last_exception_text = text


def create_transport_car() -> AssistantFollowRuntime:
    """创建辅车角色运行时对象."""

    return AssistantFollowRuntime()
