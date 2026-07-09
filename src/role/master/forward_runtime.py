"""主车角色运行时主体

@file src/role/master/forward_runtime.py
"""

import time

from utils.startup_log import log_exception

from config import motion as motion_params
from config import vision as vision_params

from protocol.codec import (
    AE_EVENT,
    AE_VALUE,
    CTL_ACTION,
    LOCAL_VISION_CONTROL_PAUSE,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_OFF,
    LOCAL_VISION_CONTROL_RETURN_LINE_GATE_ON,
    LOCAL_VISION_CONTROL_RESUME,
    ME_CTX,
    ME_EVENT,
    ME_TH,
    ME_VALUE,
    VEL_HAS_W,
    VEL_X,
    VEL_Y,
    decode_assistant_event_report_body,
    decode_local_vision_control_body,
    decode_master_vision_event_report_body,
    decode_velocity_body_into,
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

from role.clear_phase import CLEAR_PHASE_FORWARD, CLEAR_PHASE_RETREAT
from role.master.state_machine import MasterStateMachine
from role.master.state_machine import (
    EVENT_ALIGNED,
    EVENT_ARRIVED,
    EVENT_CLEARED,
    EVENT_RETURN_LINE_ALIGNED,
    EVENT_TARGET_FOUND,
    RQ_ARG,
    RQ_CONTEXT,
    RQ_KIND,
    RQ_STATE,
    RQ_TARGET,
    RK_A_CLEAR,
    RK_A_FINISHED,
    RK_A_FOLLOW,
    RK_A_OBJ,
    RK_A_ORBIT,
    RK_A_RETURN,
    RK_A_START,
    RK_A_TRANSPORT,
    RK_NONE,
    RK_T_FINISH,
    RK_T_ORBIT,
    RK_T_RETURN,
    RK_T_TRANSPORT,
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

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value


_P_KIND = const(0)
_P_CTX = const(1)
_P_STATE = const(2)
_P_TARGET = const(3)
_P_ARG = const(4)
_P_QUEUED = const(5)

_S_KIND = const(0)
_S_STATE = const(1)
_S_TARGET = const(2)
_S_ARG = const(3)
_S_THRESHOLD = const(4)
_S_QUEUED = const(5)

_G_ACTION = const(0)
_G_QUEUED = const(1)


MASTER_SEARCH_TASK_CONFIG_ID = vision_params.MASTER_SEARCH_TASK_CONFIG_ID
ASSISTANT_APPROACH_OBJECT_CONFIG_ID = vision_params.ASSISTANT_APPROACH_OBJECT_CONFIG_ID
ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID = vision_params.ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID
MASTER_TRANSPORT_TASK_CONFIG_ID = vision_params.MASTER_TRANSPORT_TASK_CONFIG_ID
MASTER_TRANSPORT_FINISH_TASK_CONFIG_ID = vision_params.MASTER_TRANSPORT_FINISH_TASK_CONFIG_ID
MASTER_ORBIT_TASK_CONFIG_ID = vision_params.MASTER_ORBIT_TASK_CONFIG_ID
MASTER_RETURN_GARAGE_LINE_TASK_CONFIG_ID = (
    vision_params.MASTER_RETURN_GARAGE_LINE_TASK_CONFIG_ID
)
TRANSPORT_OBJECT_TOTAL_COUNT = vision_params.TRANSPORT_OBJECT_TOTAL_COUNT
ORBIT_VISION_CORRECTION_ENABLED = bool(vision_params.ORBIT_VISION_CORRECTION_ENABLED)
MASTER_ORBIT_TARGET_DEG = motion_params.MASTER_ORBIT_TARGET_DEG
MASTER_ORBIT_RADIUS_SCALE = motion_params.MASTER_ORBIT_RADIUS_SCALE
TRANSPORT_AVOIDANCE_DEMO_ENABLED = bool(motion_params.TRANSPORT_AVOIDANCE_DEMO_ENABLED)
TRANSPORT_AVOIDANCE_ORBIT_OFFSET_DEG = motion_params.TRANSPORT_AVOIDANCE_ORBIT_OFFSET_DEG
TRANSPORT_FORWARD_SPEED = motion_params.TRANSPORT_FORWARD_SPEED
TRANSPORT_CLEAR_STEP_DISTANCE_M = motion_params.TRANSPORT_CLEAR_STEP_DISTANCE_M
TRANSPORT_CLEAR_RETREAT_DISTANCE_M = motion_params.TRANSPORT_CLEAR_RETREAT_DISTANCE_M
TRANSPORT_CLEAR_RETREAT_MAX_SPEED = motion_params.TRANSPORT_CLEAR_RETREAT_MAX_SPEED
MOTION_STOP_SPEED_THRESHOLD = motion_params.MOTION_STOP_SPEED_THRESHOLD
MOTION_STOP_CONFIRM_TICKS = motion_params.MOTION_STOP_CONFIRM_TICKS
MASTER_TURN_BACK_DELTA_DEG = motion_params.MASTER_TURN_BACK_DELTA_DEG
MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG = motion_params.MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG


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
        # 主路径长期 owner 使用短字段：_car 是底盘，_sm 是主车状态机。
        self._car = car
        self.wheel_encoders = car.wheel_encoders
        self.imu = car.imu
        self._now_ms = now_ms or _default_now_ms
        self._ts = transport or create_transport(
            ROLE_MASTER,
            now_ms=self._now_ms,
        )
        seed_value = int(self._now_ms()) % 256
        self._sm = MasterStateMachine(
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
            avoidance_enabled=TRANSPORT_AVOIDANCE_DEMO_ENABLED,
            avoidance_orbit_offset_deg=TRANSPORT_AVOIDANCE_ORBIT_OFFSET_DEG,
        )
        self._err = "none"
        # UART6 视觉速度缓存：_u6v 是当前速度槽，_u6_ver 是丢弃旧包的版本线。
        self._u6v = None
        self._u6_pkt = [0.0, 0.0, 0.0, False]
        self._u6_ver = 0
        self._u6_has_w = False
        # 主车可靠链路状态：act 是当前上下文，p_* 是等待确认的通信请求。
        self._act_ctx = None
        self._p_task = None
        self._p_event = None
        self._obj_th = (0, 0, 0, 0, 0, 0)
        self._p_sync = None
        self._p_ast = None
        self._orb_act = False
        # play_* 是轻量动作脚本的运行游标，由 play.sequence 读写。
        self.play_kind = 0
        self.play_step = 0
        self.play_entered = False
        # transport/clear/turn-back 阶段状态：tr/clr/tb 分别对应运输、清障、回正。
        self._tr_sync_ack = False
        self._tr_task_ack = False
        self._tr_ticks = 0
        self._tr_unlock = False
        self._clr_sync_ack = False
        self._clr_move = False
        self._clr_done_phase = None
        self._clr_ticks = 0
        self._tb_rot = False
        self._tb_ticks = 0
        self._tb_heading = None
        self._task_status = None
        # 复用发送缓冲，避免每次组包都创建新的 bytes 对象。
        self._vel_body = bytearray(7)
        self._ctrl_body = bytearray(1)
        self._task_body = bytearray(10)
        self._ast_body = bytearray(3)
        # 本地视觉门控与返回线状态，gate 保存待切换动作和是否已下发。
        self._lv_pause = False
        self._last_state = int(self._sm.state)
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
            self._record_error("master motion input failed: %s" % exc, exc)
        return True

    def step_role(self) -> bool:
        try:
            self._run_role_cycle()
        except Exception as exc:
            self._record_error("master role cycle failed: %s" % exc, exc)
        return True

    def step(self) -> bool:
        keep_running = self.step_role()
        if keep_running:
            keep_running = self.step_motion_input()
        return bool(self._car.step()) and keep_running

    def request_state_sync(self, state: int, target: int, arg: int) -> int:
        self._p_sync = (
            RK_NONE,
            int(state),
            int(target),
            int(arg),
            (0, 0, 0, 0, 0, 0),
            False,
        )
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
        self._consume_uart6_reliable_inputs()
        self._consume_uart8_inputs()
        self._check_transport_deliveries()
        self._sync_role_state_transition()
        self._drain_state_machine_outputs()
        self._queue_transport_outputs()

    def _run_motion_input_cycle(self) -> None:
        """执行视觉速度输入和底盘目标写入."""
        self._sync_role_state_transition()
        self._consume_uart6_velocity_input()
        self._apply_motion_outputs()
        self._run_clear_phase()
        self._sync_role_state_transition()
        self._run_turn_back_phase()
        self._sync_role_state_transition()
        self._drain_state_machine_outputs()
        self._queue_feedforward_velocity()

    def _sync_role_state_transition(self) -> None:
        current_state = int(self._sm.state)
        if current_state == int(self._last_state):
            return
        self._clear_local_vision_pause_residue()
        self._line_ok = False
        if current_state != STATE_RETURN_GARAGE_RETREAT and current_state != STATE_STARTUP_MOVE:
            self._gate = None
            from play import sequence as play_sequence

            play_sequence.clear(self)
        if current_state == STATE_TRANSPORT_OBJECT:
            self._tr_ticks = 0
            self._tr_unlock = False
        self._last_state = current_state

    def _clear_local_vision_pause_residue(self) -> None:
        self._lv_pause = False
        self._u6v = None
        self._u6_has_w = False
        self._u6_ver = self._ts.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )

    def _consume_uart6_reliable_inputs(self) -> None:
        """消费本车视觉链路上的 TCP 控制与事件."""
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
            self._ts.tcp_read(
                UART6,
                TOPIC_MASTER_VISION_EVENT_REPORT, self._task_body
            )
            == "ok"
        ):
            packet = decode_master_vision_event_report_body(self._task_body)
            self._handle_task_event(packet)

    def _consume_uart6_velocity_input(self) -> None:
        """消费本车视觉链路上的 UDP 速度."""
        if (
            self._ts.udp_read(
                UART6,
                TOPIC_LOCAL_VISION_VELOCITY, self._vel_body
            )
            == "ok"
        ):
            version = self._ts.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            if version > self._u6_ver and not self._lv_pause:
                packet = decode_velocity_body_into(
                    self._vel_body, self._u6_pkt
                )
                if (
                    self._sm.allows_search_velocity()
                    or self._sm.state == STATE_TRANSPORT_OBJECT
                    or (
                        self._sm.state == STATE_ORBITING
                        and self._p_task is None
                    )
                ):
                    self._u6v = packet
                    self._u6_has_w = bool(packet[VEL_HAS_W])

    def _handle_local_vision_control(self, packet) -> None:
        """处理 OpenART 慢帧前后的可靠暂停控制."""

        action = int(packet[CTL_ACTION])
        if action == LOCAL_VISION_CONTROL_PAUSE and not self._allows_local_vision_control():
            self._lv_pause = False
            return
        self._u6v = None
        self._u6_has_w = False
        self._u6_ver = self._ts.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )
        if action == LOCAL_VISION_CONTROL_PAUSE:
            self._lv_pause = True
            if not bool(getattr(self._car, "command_lock", False)):
                self._car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    None,
                    True,
                )
            return
        if action == LOCAL_VISION_CONTROL_RESUME:
            self._lv_pause = False

    def _allows_local_vision_control(self) -> bool:
        return int(self._sm.state) == int(STATE_SEARCH_OBJECT)

    def _consume_uart8_inputs(self) -> None:
        """消费辅车回报的可靠事件."""
        if (
            self._ts.tcp_read(
                UART8,
                TOPIC_ASSISTANT_EVENT_REPORT, self._ast_body
            )
            == "ok"
        ):
            packet = decode_assistant_event_report_body(self._ast_body)
            self._clear_local_velocity_for_reliable_event()
            if int(packet[AE_EVENT]) == EVENT_TARGET_FOUND:
                self._sm.handle_assistant_target_found(packet[AE_VALUE])
            elif int(packet[AE_EVENT]) == EVENT_ALIGNED:
                self._sm.handle_assistant_aligned(packet[AE_VALUE])
            elif int(packet[AE_EVENT]) == EVENT_CLEARED:
                self._sm.handle_assistant_cleared(packet[AE_VALUE])

    def _handle_task_event(self, packet) -> None:
        context_id = int(packet[ME_CTX])
        if self._act_ctx == context_id:
            self._clear_local_velocity_for_reliable_event()
            self._remember_task_event_threshold(packet)
            if (
                self._sm.state == STATE_RETURN_GARAGE_RETREAT
                and int(packet[ME_EVENT]) == int(EVENT_RETURN_LINE_ALIGNED)
            ):
                self._line_ok = True
            self._sm.handle_event(
                context_id,
                packet[ME_EVENT],
                packet[ME_VALUE],
            )
            if int(packet[ME_EVENT]) == int(EVENT_ARRIVED):
                if self._sm.state != STATE_TRANSPORT_OBJECT:
                    self._act_ctx = None
                    self._u6v = None
                    self._u6_has_w = False
                    self._u6_ver = self._ts.get_udp_version(
                        UART6, TOPIC_LOCAL_VISION_VELOCITY
                    )
            return
        if self._p_task is not None and context_id == int(self._p_task[_P_CTX]):
            self._clear_local_velocity_for_reliable_event()
            self._p_event = (
                int(context_id),
                int(packet[ME_EVENT]),
                int(packet[ME_VALUE]),
                tuple(packet[ME_TH]),
            )
            return

    def _remember_task_event_threshold(self, packet) -> None:
        threshold = tuple(packet[ME_TH])
        if self._threshold_has_value(threshold):
            self._obj_th = threshold

    def _threshold_has_value(self, threshold: tuple) -> bool:
        for value in threshold:
            if int(value) != 0:
                return True
        return False

    def _clear_local_velocity_for_reliable_event(self) -> None:
        """可靠业务事件到达时, 丢弃旧 UDP 速度并按需写入零速度语义."""

        self._u6v = None
        self._u6_has_w = False
        self._u6_ver = self._ts.get_udp_version(
            UART6, TOPIC_LOCAL_VISION_VELOCITY
        )
        if bool(getattr(self._car, "command_lock", False)):
            return
        self._car.handle_velocity_packet(
            0.0,
            0.0,
            0.0,
            None,
            True,
        )

    def _check_transport_deliveries(self) -> None:
        """把通信层的交付结果映射回角色状态机."""
        pending = self._p_task
        if pending is not None and pending[_P_QUEUED]:
            if (
                self._ts.tcp_delivery(UART6, TOPIC_MASTER_VISION_TASK_SYNC)
                == DELIVERY_DELIVERED
            ):
                self._act_ctx = int(pending[_P_CTX])
                if pending[_P_KIND] == RK_T_TRANSPORT:
                    self._tr_task_ack = True
                    if self._tr_sync_ack:
                        self._sm.mark_transport_ready()
                elif self._sm.state == STATE_SEARCH_OBJECT:
                    self._sm.mark_restart_search_task_acknowledged()
                self._p_task = None
                self._drain_pending_task_event()
        pending_gate = self._gate
        if pending_gate is not None and pending_gate[_G_QUEUED]:
            if (
                self._ts.tcp_delivery(UART6, TOPIC_LOCAL_VISION_CONTROL)
                == DELIVERY_DELIVERED
            ):
                self._gate = None

        pending = self._p_ast
        if pending is not None and pending[_S_QUEUED]:
            if (
                self._ts.tcp_delivery(UART8, TOPIC_ASSISTANT_STATE_SYNC)
                == DELIVERY_DELIVERED
            ):
                if pending[_S_KIND] == RK_A_OBJ:
                    self._sm.mark_assistant_object_acknowledged()
                elif pending[_S_KIND] == RK_A_START:
                    self._sm.mark_startup_sync_acknowledged()
                elif pending[_S_KIND] == RK_A_FOLLOW:
                    self._sm.mark_assistant_follow_acknowledged()
                elif pending[_S_KIND] == RK_A_TRANSPORT:
                    self._tr_sync_ack = True
                    if self._tr_task_ack:
                        self._sm.mark_transport_ready()
                elif pending[_S_KIND] == RK_A_CLEAR:
                    self._clr_sync_ack = True
                elif pending[_S_KIND] == RK_A_FINISHED:
                    pass
                self._p_ast = None

        pending = self._p_sync
        if pending is not None and pending[_S_QUEUED]:
            if (
                self._ts.tcp_delivery(UART8, TOPIC_ASSISTANT_STATE_SYNC)
                == DELIVERY_DELIVERED
            ):
                self._p_sync = None

    def _apply_motion_outputs(self) -> None:
        if self._lv_pause:
            if not bool(getattr(self._car, "command_lock", False)):
                self._car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    None,
                    True,
                )
            return
        if self._sm.state == STATE_TRANSPORT_OBJECT:
            if not self._is_transport_finish_task_ready():
                self._tr_ticks = 0
                self._tr_unlock = False
                self._car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    None,
                    True,
                )
                return
            if not self._is_transport_push_unlocked():
                self._car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    None,
                    True,
                )
                return
            self._apply_transport_velocity()
            return
        if self._sm.state == STATE_ORBITING:
            self._apply_orbit_velocity_correction()
            return
        if self._sm.state == STATE_CLEAR_OBJECT:
            if not self._clr_move:
                self._car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    None,
                    True,
                )
            return
        if self._sm.state == STATE_RETURN_GARAGE_RETREAT:
            self._run_return_play()
            return
        if self._sm.state == STATE_STARTUP_MOVE:
            self._run_startup_move_play()
            return
        if self._sm.state == STATE_FINISHED:
            self._car.handle_velocity_packet(
                0.0,
                0.0,
                0.0,
                None,
                True,
            )
            return
        if self._sm.state == STATE_SEARCH_OBJECT and getattr(
            self._sm, "_m_aligned", False
        ):
            self._car.handle_velocity_packet(
                0.0,
                0.0,
                0.0,
                None,
                True,
            )
            return
        if self._sm.allows_search_velocity():
            self._apply_latest_uart6_velocity()

    def _is_transport_finish_task_ready(self) -> bool:
        return self._act_ctx == int(self._sm._ctx)

    def _run_return_play(self) -> None:
        from play import sequence as play_sequence

        play_sequence.start(self, play_sequence.PLAY_MASTER_RETURN)
        play_sequence.tick(self)

    def _run_startup_move_play(self) -> None:
        from play import sequence as play_sequence

        play_sequence.start(self, play_sequence.PLAY_STARTUP)
        if play_sequence.tick(self):
            self._sm.mark_startup_move_completed()

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
        target_heading_deg = float(getattr(self._car, "heading_est", 0.0)) + float(value)
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

    def _apply_latest_uart6_velocity(self) -> None:
        packet = self._u6v
        if packet is None:
            return
        self._car.handle_velocity_packet(
            float(packet[VEL_X]),
            float(packet[VEL_Y]),
            0.0,
            None,
            False,
        )
        if self._sm.state == STATE_SEARCH_OBJECT and getattr(
            self._sm, "_orbit_done", False
        ):
            target_heading_deg = self._sm.get_push_heading_deg()
            self._car.set_heading_target(target_heading_deg)

    def _apply_orbit_velocity_correction(self) -> None:
        if not ORBIT_VISION_CORRECTION_ENABLED:
            return
        if not bool(getattr(self._car, "orbit_mode", False)):
            return
        packet = self._u6v
        if packet is None:
            return
        self._car.set_orbit_velocity_correction(
            float(packet[VEL_X]),
            float(packet[VEL_Y]),
        )

    def _apply_transport_velocity(self) -> None:
        packet = self._u6v
        vx = 0.0
        vy = float(TRANSPORT_FORWARD_SPEED)
        if packet is not None:
            vy += float(packet[VEL_Y])
        self._car.handle_velocity_packet(
            vx,
            vy,
            0.0,
            None,
            False,
        )

    def _queue_transport_outputs(self) -> None:
        """提交本拍要发送的 task 和状态同步."""
        self._queue_pending_task_sync()
        self._queue_return_line_gate_action()
        self._queue_pending_sync()

    def _queue_pending_task_sync(self) -> None:
        pending = self._p_task
        if pending is None or pending[_P_QUEUED]:
            return
        body = encode_master_vision_task_sync_body(
            pending[_P_CTX],
            pending[_P_STATE],
            pending[_P_TARGET],
            pending[_P_ARG],
        )
        status = self._ts.tcp_write(UART6, TOPIC_MASTER_VISION_TASK_SYNC, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            self._task_status = None
            self._p_task = (
                pending[_P_KIND],
                pending[_P_CTX],
                pending[_P_STATE],
                pending[_P_TARGET],
                pending[_P_ARG],
                True,
            )
            return
        if self._task_status == status:
            return
        self._task_status = status

    def _queue_pending_sync(self) -> None:
        pending = self._p_ast
        if pending is None:
            pending = self._p_sync
        if pending is None or pending[_S_QUEUED]:
            return
        body = encode_assistant_state_sync_body(
            pending[_S_STATE],
            pending[_S_TARGET],
            pending[_S_ARG],
            self._threshold_for_assistant_sync(pending),
        )
        status = self._ts.tcp_write(UART8, TOPIC_ASSISTANT_STATE_SYNC, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            if pending is self._p_ast:
                self._p_ast = (
                    pending[_S_KIND],
                    pending[_S_STATE],
                    pending[_S_TARGET],
                    pending[_S_ARG],
                    pending[_S_THRESHOLD],
                    True,
                )
            else:
                self._p_sync = (
                    pending[_S_KIND],
                    pending[_S_STATE],
                    pending[_S_TARGET],
                    pending[_S_ARG],
                    pending[_S_THRESHOLD],
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

    def _queue_feedforward_velocity(self) -> None:
        """提交主车当前底盘速度前馈.

        @details 是否真正写出由 transport 的统一仲裁决定, 主车角色层不额外做发送互斥
        """
        if self._p_ast is not None or self._p_sync is not None:
            return
        if (
            self._sm.state == STATE_TRANSPORT_OBJECT
            and not self._is_transport_finish_task_ready()
        ):
            return
        if not self._sm.allows_assistant_velocity_forward():
            return
        if self._sm.needs_assistant_report_turn():
            return
        car = self._car
        has_omega = bool(self._u6_has_w)
        omega = float(getattr(car, "control_omega", 0.0)) if has_omega else 0.0
        body = encode_velocity_body(
            getattr(car, "control_vx", 0.0),
            getattr(car, "control_vy", 0.0),
            omega,
            has_omega,
        )
        self._ts.udp_write(
            UART8,
            TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
            body,
        )

    def _advance_state_machine(self) -> None:
        orbit_finished = False
        if self._orb_act:
            orbit_finished = not bool(getattr(self._car, "command_lock", False))
            if orbit_finished:
                self._car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    None,
                    True,
                )
        self._sm.step(orbit_finished)
        if self._sm.state != STATE_ORBITING:
            self._orb_act = False

    def _drain_state_machine_outputs(self) -> None:
        """消费状态机一次性输出并刷新本拍业务意图."""
        task_request = self._sm.poll_task_request()
        if task_request is not None:
            self._act_ctx = None
            self._u6v = None
            self._u6_has_w = False
            self._u6_ver = self._ts.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            self._p_event = None
            self._tr_task_ack = False
            self._p_task = (
                task_request[RQ_KIND],
                task_request[RQ_CONTEXT],
                task_request[RQ_STATE],
                task_request[RQ_TARGET],
                task_request[RQ_ARG],
                False,
            )
        assistant_request = self._sm.poll_assistant_request()
        if assistant_request is not None:
            request_kind = int(assistant_request[RQ_KIND])
            if request_kind == RK_A_OBJ:
                self._u6v = None
                self._u6_has_w = False
                self._u6_ver = self._ts.get_udp_version(
                    UART6, TOPIC_LOCAL_VISION_VELOCITY
                )
            elif request_kind == RK_A_FOLLOW:
                self._u6v = None
                self._u6_has_w = False
                self._u6_ver = self._ts.get_udp_version(
                    UART6, TOPIC_LOCAL_VISION_VELOCITY
                )
            elif request_kind == RK_A_TRANSPORT:
                self._u6v = None
                self._u6_has_w = False
                self._u6_ver = self._ts.get_udp_version(
                    UART6, TOPIC_LOCAL_VISION_VELOCITY
                )
                self._p_event = None
                self._tr_sync_ack = False
                self._tr_task_ack = bool(self._sm._av_shift)
                self._tr_ticks = 0
                self._tr_unlock = False
                self._car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    None,
                    True,
                )
                if not self._sm._av_shift:
                    self._act_ctx = None
                    self._p_task = (
                        RK_T_TRANSPORT,
                        int(self._sm._ctx),
                        STATE_SEARCH_OBJECT,
                        int(assistant_request[RQ_TARGET]),
                        int(MASTER_TRANSPORT_TASK_CONFIG_ID),
                        False,
                    )
            elif request_kind == RK_A_CLEAR:
                self._u6v = None
                self._u6_has_w = False
                self._u6_ver = self._ts.get_udp_version(
                    UART6, TOPIC_LOCAL_VISION_VELOCITY
                )
                self._clr_sync_ack = False
                self._clr_move = False
                self._clr_done_phase = None
                self._clr_ticks = 0
                self._car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    None,
                    True,
                )
            self._p_ast = (
                request_kind,
                int(assistant_request[RQ_STATE]),
                int(assistant_request[RQ_TARGET]),
                int(assistant_request[RQ_ARG]),
                self._threshold_for_assistant_request(assistant_request),
                False,
            )

        orbit_command = self._sm.poll_orbit_command()
        if orbit_command is not None:
            self._act_ctx = None
            self._u6v = None
            self._u6_has_w = False
            self._u6_ver = self._ts.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )
            self._p_event = None
            self._p_task = (
                RK_T_ORBIT,
                int(self._sm._ctx),
                STATE_ORBITING,
                TARGET_OBJECT,
                int(MASTER_ORBIT_TASK_CONFIG_ID),
                False,
            )
            self._car.set_orbit_target(
                float(orbit_command),
                float(MASTER_ORBIT_RADIUS_SCALE),
            )
            self._orb_act = True

    def _run_clear_phase(self) -> None:
        if self._sm.state != STATE_CLEAR_OBJECT:
            self._clr_move = False
            self._clr_done_phase = None
            self._clr_ticks = 0
            self._tb_heading = None
            return
        clear_phase = int(self._sm.get_clear_phase())
        if clear_phase != CLEAR_PHASE_RETREAT and clear_phase != CLEAR_PHASE_FORWARD:
            self._clr_move = False
            self._clr_ticks = 0
            return
        if self._clr_move:
            if bool(getattr(self._car, "command_lock", False)):
                self._clr_ticks = 0
                return
            if not self._are_all_wheels_near_stop():
                self._clr_ticks = 0
                return
            self._clr_ticks += 1
            if self._clr_ticks < int(MOTION_STOP_CONFIRM_TICKS):
                return
            self._clr_move = False
            self._clr_done_phase = clear_phase
            self._clr_ticks = 0
            self._sm.mark_master_cleared()
            return
        if not self._clr_sync_ack:
            return
        if self._clr_done_phase == clear_phase:
            return
        if clear_phase == CLEAR_PHASE_RETREAT:
            self._car.set_relative_translation_target(
                0.0,
                -float(TRANSPORT_CLEAR_RETREAT_DISTANCE_M),
                None,
                float(TRANSPORT_CLEAR_RETREAT_MAX_SPEED),
            )
        else:
            self._car.set_relative_translation_target(
                0.0,
                float(TRANSPORT_CLEAR_STEP_DISTANCE_M),
                self._tb_heading,
            )
        self._clr_move = True
        self._clr_ticks = 0

    def _run_turn_back_phase(self) -> None:
        if not self._sm.is_post_clear_turn_back_pending():
            self._tb_rot = False
            self._tb_ticks = 0
            return
        if self._tb_rot:
            if bool(getattr(self._car, "command_lock", False)):
                if self._is_turn_back_within_unlock_tolerance():
                    self._car.handle_velocity_packet(
                        0.0,
                        0.0,
                        0.0,
                        None,
                        True,
                    )
                    self._tb_rot = False
                    self._tb_ticks = 0
                    self._sm.mark_turn_back_completed()
                    return
                self._tb_ticks = 0
                return
            self._tb_rot = False
            self._tb_ticks = 0
            self._sm.mark_turn_back_completed()
            return
        if not self._sm.can_start_turn_back_rotation():
            return
        target_heading_deg = (
            float(getattr(self._car, "heading_est", 0.0))
            + float(MASTER_TURN_BACK_DELTA_DEG)
        )
        self._tb_heading = target_heading_deg
        self._car.set_heading_transition_target(target_heading_deg)
        self._tb_rot = True
        self._tb_ticks = 0

    def _is_turn_back_within_unlock_tolerance(self) -> bool:
        target_deg = self._tb_heading
        if target_deg is None:
            return False
        err_deg = float(target_deg) - float(
            getattr(self._car, "heading_est", 0.0)
        )
        while err_deg >= 180.0:
            err_deg -= 360.0
        while err_deg < -180.0:
            err_deg += 360.0
        return abs(err_deg) <= float(MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG)

    def _are_all_wheels_near_stop(self) -> bool:
        return bool(self._car.wheel_stop_confirmed(MOTION_STOP_SPEED_THRESHOLD))

    def _is_transport_push_unlocked(self) -> bool:
        if self._tr_unlock:
            return True
        if not self._are_all_wheels_near_stop():
            self._tr_ticks = 0
            return False
        self._tr_ticks += 1
        if self._tr_ticks < int(MOTION_STOP_CONFIRM_TICKS):
            return False
        self._tr_unlock = True
        return True

    def _drain_pending_task_event(self) -> None:
        pending_event = self._p_event
        if pending_event is None:
            return
        self._p_event = None
        context_id, event, value, threshold = pending_event
        if self._threshold_has_value(threshold):
            self._obj_th = threshold
        self._sm.handle_event(
            context_id,
            event,
            value,
        )
        if (
            int(event) == int(EVENT_ARRIVED)
            and self._sm.state != STATE_TRANSPORT_OBJECT
        ):
            self._act_ctx = None
            self._u6v = None
            self._u6_has_w = False
            self._u6_ver = self._ts.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )

    def _threshold_for_assistant_request(self, assistant_request: tuple) -> tuple:
        if int(assistant_request[RQ_TARGET]) == TARGET_OBJECT:
            return tuple(self._obj_th)
        return (0, 0, 0, 0, 0, 0)

    def _threshold_for_assistant_sync(self, pending: tuple) -> tuple:
        if int(pending[_S_TARGET]) == TARGET_OBJECT:
            return tuple(self._obj_th)
        return tuple(pending[_S_THRESHOLD])

    def _record_error(self, text: str, exc: Exception) -> None:
        if self._err != text:
            log_exception("master_error", text, exc)
        self._err = text
        self._car.last_exception_text = text
