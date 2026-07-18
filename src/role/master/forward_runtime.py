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
    ME_CTX,
    ME_EVENT,
    ME_VALUE,
    VEL_HAS_W,
    VEL_X,
    VEL_Y,
    decode_assistant_event_report_body,
    decode_master_vision_event_report_body,
    decode_velocity_body_into,
    encode_assistant_state_sync_body,
    encode_master_vision_task_sync_body,
    encode_velocity_body,
)

from protocol.topic import (
    ROLE_MASTER,
    TOPIC_ASSISTANT_EVENT_REPORT,
    TOPIC_ASSISTANT_FEEDFORWARD_VELOCITY,
    TOPIC_ASSISTANT_STATE_SYNC,
    TOPIC_LOCAL_VISION_VELOCITY,
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
from role.master.state_machine import (
    EVENT_ALIGNED,
    EVENT_ARRIVED,
    EVENT_CLEARED,
    EVENT_ORBIT_FINISHED,
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
    RK_T_ORBIT,
    RK_T_TRANSPORT,
    STATE_CLEAR_OBJECT,
    STATE_FINISHED,
    STATE_ORBITING,
    STATE_RETURN_GARAGE_RETREAT,
    STATE_SEARCH_OBJECT,
    STATE_STARTUP_MOVE,
    STATE_STOP,
    STATE_TRANSPORT_OBJECT,
    TARGET_OBJECT,
    MasterStateMachine,
)
from role.transport_plan import (
    limit_planar_velocity_step,
    plan_return_garage,
    plan_startup_target_y,
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
_S_QUEUED = const(4)

MASTER_SEARCH_TASK_CONFIG_ID = vision_params.MASTER_SEARCH_TASK_CONFIG_ID
ASSISTANT_APPROACH_OBJECT_CONFIG_ID = vision_params.ASSISTANT_APPROACH_OBJECT_CONFIG_ID
ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID = vision_params.ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID
MASTER_TRANSPORT_TASK_CONFIG_ID = vision_params.MASTER_TRANSPORT_TASK_CONFIG_ID
MASTER_ORBIT_TASK_CONFIG_ID = vision_params.MASTER_ORBIT_TASK_CONFIG_ID
TRANSPORT_OBJECT_TOTAL_COUNT = vision_params.TRANSPORT_OBJECT_TOTAL_COUNT
ORBIT_VISION_CORRECTION_ENABLED = bool(vision_params.ORBIT_VISION_CORRECTION_ENABLED)
MASTER_ORBIT_RADIUS_SCALE = motion_params.MASTER_ORBIT_RADIUS_SCALE
MASTER_ORBIT_AVOID_TRIGGER_DEG = motion_params.MASTER_ORBIT_AVOID_TRIGGER_DEG
MASTER_ORBIT_AVOID_HEADING_DEG = motion_params.MASTER_ORBIT_AVOID_HEADING_DEG
MASTER_ORBIT_AVOID_PUSH_DISTANCE_M = (
    motion_params.MASTER_ORBIT_AVOID_PUSH_DISTANCE_M
)
TRANSPORT_OBSTACLE_MARGIN_M = motion_params.TRANSPORT_OBSTACLE_MARGIN_M
RETURN_GARAGE_OBSTACLE_DEPTH_M = motion_params.RETURN_GARAGE_OBSTACLE_DEPTH_M
MASTER_RETURN_GARAGE_EXTRA_RETREAT_M = (
    motion_params.MASTER_RETURN_GARAGE_EXTRA_RETREAT_M
)
TRANSPORT_FORWARD_SPEED = motion_params.TRANSPORT_FORWARD_SPEED
MASTER_TRANSPORT_ACCEL_TIME_S = motion_params.MASTER_TRANSPORT_ACCEL_TIME_S
MOTION_INPUT_STEP_MS = motion_params.MOTION_INPUT_STEP_MS
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

    def __init__(self, obstacle_slots, now_ms=None, transport=None) -> None:
        from core.runtime import TransportCar

        car = TransportCar(vehicle_role=ROLE_MASTER)
        obstacle_slots = tuple(obstacle_slots)
        # 主路径长期 owner 使用短字段：_car 是底盘，_sm 是主车状态机。
        self._car = car
        self.wheel_encoders = car.wheel_encoders
        self.imu = car.imu
        self._now_ms = now_ms or _default_now_ms
        self._ts = transport or create_transport(
            ROLE_MASTER,
            now_ms=self._now_ms,
        )
        self._obstacles = obstacle_slots
        seed_value = int(self._now_ms()) % 256
        self._sm = MasterStateMachine(
            search_task_arg=MASTER_SEARCH_TASK_CONFIG_ID,
            boot_heading_deg=float(getattr(car, "heading_est", 0.0)),
            obstacle_slots=obstacle_slots,
            obstacle_margin_m=TRANSPORT_OBSTACLE_MARGIN_M,
            orbit_avoid_trigger_deg=MASTER_ORBIT_AVOID_TRIGGER_DEG,
            orbit_avoid_heading_deg=MASTER_ORBIT_AVOID_HEADING_DEG,
            orbit_avoid_push_distance_m=MASTER_ORBIT_AVOID_PUSH_DISTANCE_M,
            assistant_object_arg=ASSISTANT_APPROACH_OBJECT_CONFIG_ID,
            assistant_transport_arg=ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
            transport_task_arg=MASTER_TRANSPORT_TASK_CONFIG_ID,
            total_object_count=TRANSPORT_OBJECT_TOTAL_COUNT,
            initial_context_id=seed_value,
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
        self._p_sync = None
        self._p_ast = None
        self._orb_act = False
        self._push_act = False
        # play_* 是轻量动作脚本的运行游标，由 play.sequence 读写。
        self.play_kind = 0
        self.play_step = 0
        self.play_entered = False
        self.play_params = None
        # transport/clear/turn-back 阶段状态：tr/clr/tb 分别对应运输、清障、回正。
        self._tr_sync_ack = False
        self._tr_task_ack = False
        self._tr_ticks = 0
        self._tr_unlock = False
        self._tr_delta = (
            float(TRANSPORT_FORWARD_SPEED)
            * float(MOTION_INPUT_STEP_MS)
            / 1000.0
            / float(MASTER_TRANSPORT_ACCEL_TIME_S)
        )
        self._tr_vx = 0.0
        self._tr_vy = 0.0
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
        self._task_body = bytearray(4)
        self._ast_body = bytearray(3)
        # 回库灰度线状态和运输阶段灰度边沿锁存
        self._last_state = int(self._sm.state)
        self._line_ok = False
        self._gray_seen = False

    def prepare_runtime(self) -> None:
        from play import sequence as play_sequence

        self._ts.wait_local_vision_ready()
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
        self._consume_grayscale_edge()
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
        previous_state = int(self._last_state)
        if (
            previous_state == STATE_TRANSPORT_OBJECT
            and current_state != STATE_TRANSPORT_OBJECT
        ):
            self._car.set_position_integration_enabled(True)
        self._clear_local_vision_velocity_residue()
        self._tr_vx = 0.0
        self._tr_vy = 0.0
        self._line_ok = False
        if current_state != STATE_RETURN_GARAGE_RETREAT and current_state != STATE_STARTUP_MOVE:
            from play import sequence as play_sequence

            play_sequence.clear(self)
        if current_state == STATE_TRANSPORT_OBJECT:
            self._tr_ticks = 0
            self._tr_unlock = False
            self._gray_seen = False
        self._last_state = current_state

    def _clear_local_vision_velocity_residue(self) -> None:
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
            if version > self._u6_ver:
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
            elif int(packet[AE_EVENT]) == EVENT_ORBIT_FINISHED:
                self._sm.handle_assistant_orbit_finished(packet[AE_VALUE])

    def _handle_task_event(self, packet) -> None:
        context_id = int(packet[ME_CTX])
        if int(packet[ME_EVENT]) not in (int(EVENT_TARGET_FOUND), int(EVENT_ALIGNED)):
            return
        if self._act_ctx == context_id:
            self._clear_local_velocity_for_reliable_event()
            self._apply_transport_arrival_pose(packet[ME_EVENT])
            self._sm.handle_event(
                context_id,
                packet[ME_EVENT],
                packet[ME_VALUE],
            )
            return
        if self._p_task is not None and context_id == int(self._p_task[_P_CTX]):
            self._clear_local_velocity_for_reliable_event()
            self._p_event = (
                int(context_id),
                int(packet[ME_EVENT]),
                int(packet[ME_VALUE]),
            )
            return

    def _clear_local_velocity_for_reliable_event(self) -> None:
        """可靠业务事件到达时, 丢弃旧 UDP 速度并按需写入零速度语义."""

        self._u6v = None
        self._u6_has_w = False
        self._tr_vx = 0.0
        self._tr_vy = 0.0
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
        pending = self._p_ast
        if pending is not None and pending[_S_QUEUED]:
            if (
                self._ts.tcp_delivery(UART8, TOPIC_ASSISTANT_STATE_SYNC)
                == DELIVERY_DELIVERED
            ):
                if pending[_S_KIND] == RK_A_OBJ:
                    self._sm.mark_assistant_object_acknowledged(
                        self._car.odometry.x,
                        self._car.odometry.y,
                        self._car.heading_est,
                    )
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
        if self._sm.state == STATE_TRANSPORT_OBJECT:
            if not self._is_transport_push_unlocked():
                self._tr_vx = 0.0
                self._tr_vy = 0.0
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

    def _consume_grayscale_edge(self) -> None:
        edge = int(self._car.read_grayscale_edge())
        if self._sm.state == STATE_RETURN_GARAGE_RETREAT:
            if edge > 0:
                self._line_ok = True
            return
        if self._sm.state != STATE_TRANSPORT_OBJECT or not self._tr_unlock:
            return
        if edge > 0:
            self._gray_seen = True
            return
        if edge >= 0 or not self._gray_seen:
            return
        self._gray_seen = False
        self._apply_transport_arrival_pose(EVENT_ARRIVED)
        self._sm.handle_event(self._sm._ctx, EVENT_ARRIVED, 0)
        if self._sm.state != STATE_TRANSPORT_OBJECT:
            self._act_ctx = None
            self._u6v = None
            self._u6_has_w = False
            self._u6_ver = self._ts.get_udp_version(
                UART6, TOPIC_LOCAL_VISION_VELOCITY
            )

    def _run_return_play(self) -> None:
        from play import sequence as play_sequence

        if self._sm.uses_preliminary_fast_return():
            if int(self.play_kind) != int(play_sequence.PLAY_MASTER_FAST_RETURN):
                play_sequence.start(self, play_sequence.PLAY_MASTER_FAST_RETURN)
            play_sequence.tick(self)
            return
        if int(self.play_kind) != int(play_sequence.PLAY_MASTER_RETURN):
            relative_y_m, heading_deg = plan_return_garage(
                self._car.odometry.x,
                self._car.odometry.y,
                self._car.heading_est,
                -1,
                self._obstacles,
                TRANSPORT_OBSTACLE_MARGIN_M,
                RETURN_GARAGE_OBSTACLE_DEPTH_M,
                MASTER_RETURN_GARAGE_EXTRA_RETREAT_M,
            )
            play_sequence.start(
                self,
                play_sequence.PLAY_MASTER_RETURN,
                (relative_y_m * 100.0, heading_deg),
            )
        play_sequence.tick(self)

    def _run_startup_move_play(self) -> None:
        from play import sequence as play_sequence

        if int(self.play_kind) != int(play_sequence.PLAY_STARTUP):
            target_y_m = plan_startup_target_y(
                self._obstacles,
                motion_params.STARTUP_TARGET_Y_M,
            )
            play_sequence.start(
                self,
                play_sequence.PLAY_STARTUP,
                (
                    (
                        motion_params.MASTER_START_POSITION_M[0] * 100.0,
                        target_y_m * 100.0,
                    ),
                ),
            )
        if play_sequence.tick(self):
            self._sm.mark_startup_move_completed()

    def play_set_position_x(self, value, max_speed_cmd=None) -> None:
        self._car.set_relative_translation_target(
            float(value),
            0.0,
            max_speed_cmd=max_speed_cmd,
        )

    def play_set_position_xy(self, x, y, max_speed_cmd=None) -> None:
        self._car.set_translation_target(
            float(x),
            float(y),
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

    def play_line_ready(self) -> bool:
        return bool(self._line_ok)

    def play_clear_line_ready(self) -> None:
        self._line_ok = False

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
        vx = 0.0
        vy = float(TRANSPORT_FORWARD_SPEED)
        if self._u6v is not None:
            vx = float(self._u6v[VEL_X])
        vx, vy = limit_planar_velocity_step(
            self._tr_vx,
            self._tr_vy,
            vx,
            vy,
            self._tr_delta,
        )
        self._tr_vx = vx
        self._tr_vy = vy
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
        )
        status = self._ts.tcp_write(UART8, TOPIC_ASSISTANT_STATE_SYNC, body)
        if status == WRITE_ACCEPTED or status == WRITE_OVERWRITTEN:
            if pending is self._p_ast:
                self._p_ast = (
                    pending[_S_KIND],
                    pending[_S_STATE],
                    pending[_S_TARGET],
                    pending[_S_ARG],
                    True,
                )
            else:
                self._p_sync = (
                    pending[_S_KIND],
                    pending[_S_STATE],
                    pending[_S_TARGET],
                    pending[_S_ARG],
                    True,
                )

    def _queue_feedforward_velocity(self) -> None:
        """提交主车当前底盘速度前馈.

        @details 是否真正写出由 transport 的统一仲裁决定, 主车角色层不额外做发送互斥
        """
        if self._p_ast is not None or self._p_sync is not None:
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
                self._orb_act = False
                self._car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    None,
                    True,
                )
        if self._push_act and not bool(getattr(self._car, "command_lock", False)):
            self._push_act = False
            self._sm.mark_avoid_push_completed()
        self._sm.step(orbit_finished)
        if self._sm.state != STATE_ORBITING:
            self._orb_act = False
            self._push_act = False

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
                self._tr_task_ack = False
                self._tr_ticks = 0
                self._tr_unlock = False
                self._car.set_position_integration_enabled(False)
                self._car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    None,
                    True,
                )
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

        push_command = self._sm.poll_avoid_push_command()
        if push_command is not None:
            self._car.set_relative_translation_target(
                0.0,
                float(push_command),
            )
            self._push_act = True

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
        context_id, event, value = pending_event
        self._sm.handle_event(
            context_id,
            event,
            value,
        )

    def _apply_transport_arrival_pose(self, event) -> None:
        """在正式推动到边事件进入状态机前完成位置校准"""

        if int(event) != int(EVENT_ARRIVED):
            return
        if self._sm.state != STATE_TRANSPORT_OBJECT:
            return
        self._car.calibrate_pose_to_field_edge(
            self._sm.get_target_edge(),
            self._sm.get_push_heading_deg(),
            0.0,
        )
        self._car.set_position_integration_enabled(True)

    def _record_error(self, text: str, exc: Exception) -> None:
        if self._err != text:
            log_exception("master_error", text, exc)
        self._err = text
        self._car.last_exception_text = text
