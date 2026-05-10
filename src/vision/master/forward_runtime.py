"""主车角色运行时主体

@file src/vision/master/forward_runtime.py
"""

from config import params as _params
from hardware.uart_bus import create_uart6
from protocol.link import default_now_ms, should_resend, write_reliable_line
from protocol.packet import (
    format_ack_packet,
    format_state_sync_packet,
    format_velocity_packet,
    parse_short_packet,
)
from vision.clear_phase import CLEAR_PHASE_RETREAT, CLEAR_PHASE_TRANSLATE
from vision.master.uart8_packet import parse_short_packet as parse_uart8_short_packet
from vision.master.state_machine import MasterStateMachine
from vision.master.state_machine import (
    ASSISTANT_CLEAR_SYNC_STATE,
    ASSISTANT_CLEAR_SYNC_TARGET,
    ASSISTANT_FOLLOW_SYNC_STATE,
    ASSISTANT_FOLLOW_SYNC_TARGET,
    ASSISTANT_IDLE_SYNC_STATE,
    ASSISTANT_IDLE_SYNC_TARGET,
    ASSISTANT_TRANSPORT_SYNC_STATE,
    ASSISTANT_TRANSPORT_SYNC_TARGET,
    EVENT_ALIGNED,
    EVENT_ARRIVED,
    EVENT_CLEARED,
    EVENT_TARGET_FOUND,
    STATE_IDLE,
    STATE_CLEAR_OBJECT,
    STATE_ORBITING,
    STATE_SEARCH_OBJECT,
    STATE_STOP,
    STATE_TRANSPORT_OBJECT,
    TARGET_EDGE_LINE,
)


_UART6_INPUT_LIMIT = 128
_UART3_INPUT_LIMIT = 128
_UART8_INPUT_LIMIT = 128
MASTER_SEARCH_HOOK_CONFIG_ID = getattr(_params, "MASTER_SEARCH_HOOK_CONFIG_ID")
ASSISTANT_APPROACH_OBJECT_CONFIG_ID = getattr(_params, "ASSISTANT_APPROACH_OBJECT_CONFIG_ID")
ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID = getattr(_params, "ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID")
MASTER_TRANSPORT_HOOK_CONFIG_ID = getattr(_params, "MASTER_TRANSPORT_HOOK_CONFIG_ID")
MASTER_TRANSPORT_FINISH_HOOK_CONFIG_ID = getattr(_params, "MASTER_TRANSPORT_FINISH_HOOK_CONFIG_ID")
MASTER_ORBIT_TARGET_DEG = getattr(_params, "MASTER_ORBIT_TARGET_DEG")
MASTER_ORBIT_RADIUS_SCALE = getattr(_params, "MASTER_ORBIT_RADIUS_SCALE")
RELIABLE_RESEND_INTERVAL_MS = getattr(_params, "RELIABLE_RESEND_INTERVAL_MS")
TRANSPORT_FORWARD_SPEED = getattr(_params, "TRANSPORT_FORWARD_SPEED")
TRANSPORT_CLEAR_STEP_DISTANCE_M = getattr(_params, "TRANSPORT_CLEAR_STEP_DISTANCE_M")
TRANSPORT_CLEAR_RETREAT_DISTANCE_M = getattr(_params, "TRANSPORT_CLEAR_RETREAT_DISTANCE_M")
TRANSPORT_CLEAR_RETREAT_MAX_SPEED = getattr(
    _params,
    "TRANSPORT_CLEAR_RETREAT_MAX_SPEED",
)
MOTION_STOP_SPEED_THRESHOLD = getattr(_params, "MOTION_STOP_SPEED_THRESHOLD")
MOTION_STOP_CONFIRM_TICKS = getattr(_params, "MOTION_STOP_CONFIRM_TICKS")
MASTER_TURN_BACK_DELTA_DEG = getattr(_params, "MASTER_TURN_BACK_DELTA_DEG")


class MasterForwardRuntime:
    """基于共享底盘装配主车角色运行时外观

    @brief 在共享底盘外层接管 UART3 与本车 UART6, 并把当前底盘速度转发到 UART8
    """

    def __init__(self, now_ms=None) -> None:
        from core.runtime import TransportCar

        car = TransportCar()
        seed_value = int((now_ms or default_now_ms)()) % 256
        self._transport_car = car
        self.wheel_states = car.wheel_states
        self.imu = car.imu
        self._now_ms = now_ms or default_now_ms
        self._uart6 = create_uart6()
        self._rx_buf3 = ""
        self._rx_buf6 = ""
        self._rx_buf8 = ""
        self._latest_uart6_velocity = None
        self._uart3_velocity_received_this_tick = False
        self._last_error_text = "none"
        self._hook_seq = seed_value
        self._active_hook_context_id = None
        self._pending_hook = None
        self._pending_hook_event = None
        self._generic_sync_seq = seed_value & 0xFE
        self._assistant_sync_seq = (seed_value + 1) & 0xFF
        if (self._assistant_sync_seq % 2) == 0:
            self._assistant_sync_seq = (self._assistant_sync_seq + 1) & 0xFF
        self._pending_sync = None
        self._pending_assistant_sync = None
        self._assistant_target_found_report = None
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
        self._state_machine = MasterStateMachine(
            hook_arg=MASTER_SEARCH_HOOK_CONFIG_ID,
            boot_heading_deg=float(getattr(car, "heading_est", 0.0)),
            orbit_delta_deg=MASTER_ORBIT_TARGET_DEG,
            assistant_object_arg=ASSISTANT_APPROACH_OBJECT_CONFIG_ID,
            assistant_transport_arg=ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID,
            transport_hook_arg=MASTER_TRANSPORT_HOOK_CONFIG_ID,
            finish_hook_arg=MASTER_TRANSPORT_FINISH_HOOK_CONFIG_ID,
            initial_context_id=seed_value,
        )
        self.last_report = None

        if getattr(car, "_process_uart", None) is not None:
            car._process_uart = self._noop_transport_uart
        self._write_uart3_boot_start()


    def _write_uart3_boot_start(self) -> None:
        """向 UART3 输出启动标记"""

        try:
            self._transport_car.uart3.write("start\r\n")
        except Exception:
            self._record_error("uart3 start write failed")

    def _write_uart3_turn_heading_debug(self) -> None:
        """在主车转身阶段向 UART3 输出当前角度调试信息"""

        try:
            self._transport_car.uart3.write(
                "turn_heading,%.2f\r\n"
                % float(getattr(self._transport_car, "heading_est", 0.0))
            )
        except Exception:
            self._record_error("uart3 turn debug write failed")

    def mark_tick(self, tick=None) -> None:
        """转发 ticker 中断标记

        @param tick 节拍值
        """

        self._transport_car.mark_tick(tick)

    def set_ticker(self, ticker_obj: object) -> None:
        """转发 ticker 对象

        @param ticker_obj ticker 对象
        """

        self._transport_car.set_ticker(ticker_obj)

    def step(self) -> bool:
        """执行一拍主车角色运行时

        @return 是否继续运行
        """

        try:
            self._run_role_cycle()
        except Exception:
            self._record_error("master role cycle failed")
        return self._transport_car.step()

    def request_state_sync(self, state: int, target: int, arg: int) -> int:
        """创建一条待确认状态同步请求

        @param state 状态编号
        @param target 目标编号
        @param arg 状态参数
        @return 本次同步序号
        """

        seq = self._generic_sync_seq
        self._pending_sync = {
            "kind": "generic",
            "seq": seq,
            "state": int(state),
            "target": int(target),
            "arg": int(arg),
            "last_sent_ms": None,
            "sent_once": False,
        }
        self._generic_sync_seq = (self._generic_sync_seq + 2) % 256
        return seq

    def _run_role_cycle(self) -> None:
        """执行角色层单拍流程"""

        self._advance_state_machine()
        self._drain_state_machine_outputs()
        self._uart3_velocity_received_this_tick = False
        self._process_uart3()
        self._process_uart6()
        self._drain_state_machine_outputs()
        transport_applied_this_tick = False
        if self._state_machine.state == STATE_TRANSPORT_OBJECT:
            self._apply_transport_velocity()
            transport_applied_this_tick = True
        elif self._state_machine.state == STATE_SEARCH_OBJECT and getattr(self._state_machine, "_master_aligned", False):
            self._transport_car.handle_velocity_packet(
                0.0,
                0.0,
                0.0,
                source="master_aligned_hold",
                has_omega=True,
            )
        elif not self._uart3_velocity_received_this_tick and self._state_machine.allows_search_velocity():
            self._apply_latest_uart6_velocity()
        self._process_uart8()
        self._drain_state_machine_outputs()
        self._run_clear_phase()
        self._drain_state_machine_outputs()
        self._run_turn_back_phase()
        self._drain_state_machine_outputs()
        if self._state_machine.state == STATE_TRANSPORT_OBJECT and not transport_applied_this_tick:
            self._apply_transport_velocity()
        self._send_pending_hook()
        self._send_pending_sync()
        self._forward_current_chassis_velocity()

    def _process_uart3(self) -> None:
        """接管 UART3 按行读取并处理短包输入"""

        self._read_uart_lines(
            self._transport_car.uart3,
            "_rx_buf3",
            self._handle_uart3_line,
            overflow_error_text="invalid uart3 input",
            input_limit=_UART3_INPUT_LIMIT,
        )

    def _process_uart6(self) -> None:
        """接管 UART6 按行读取本车视觉速度输入"""

        self._read_uart_lines(
            self._uart6,
            "_rx_buf6",
            self._handle_uart6_line,
            read_error_text="uart6 read failed",
            overflow_error_text="invalid uart6 input",
            input_limit=_UART6_INPUT_LIMIT,
        )

    def _process_uart8(self) -> None:
        """接管 UART8 按行读取确认与回报短包"""

        uart8 = self._transport_car.uart8
        if getattr(uart8, "any", None) is None:
            return
        self._read_uart_lines(
            uart8,
            "_rx_buf8",
            self._handle_uart8_line,
            overflow_error_text="invalid uart8 input",
            input_limit=_UART8_INPUT_LIMIT,
        )

    def _read_uart_lines(
        self,
        uart,
        buffer_name: str,
        handler,
        read_error_text: str = "uart read failed",
        overflow_error_text=None,
        input_limit=None,
    ) -> None:
        while True:
            buf_len = uart.any()
            if not buf_len:
                return
            input_overflow = input_limit is not None and buf_len > input_limit
            if input_overflow:
                buf_len = input_limit
            try:
                chunk = uart.read(buf_len).decode()
            except Exception:
                self._record_error(read_error_text)
                return
            setattr(self, buffer_name, getattr(self, buffer_name) + chunk)
            if input_overflow:
                setattr(self, buffer_name, "")
                if overflow_error_text is not None:
                    self._record_error(overflow_error_text)
                return
            if self._drain_uart_lines(buffer_name, handler, overflow_error_text, input_limit):
                return

    def _drain_uart_lines(self, buffer_name: str, handler, overflow_error_text, input_limit) -> bool:
        while True:
            buffer = getattr(self, buffer_name)
            if input_limit is not None and len(buffer) > input_limit:
                setattr(self, buffer_name, "")
                if overflow_error_text is not None:
                    self._record_error(overflow_error_text)
                return True
            idx = buffer.find("\n")
            if idx == -1:
                return False
            if input_limit is not None and idx > input_limit:
                setattr(self, buffer_name, buffer[idx + 1 :])
                if overflow_error_text is not None:
                    self._record_error(overflow_error_text)
                continue
            line = buffer[:idx].rstrip("\r").strip()
            setattr(self, buffer_name, buffer[idx + 1 :])
            handler(line)

    def _handle_uart3_line(self, line: str) -> None:
        """处理单条 UART3 短包输入行

        @param line 原始输入行
        """

        if not line:
            return
        if self._state_machine.state == STATE_ORBITING:
            return
        if self._state_machine.state == STATE_TRANSPORT_OBJECT:
            return
        if self._state_machine.state == STATE_CLEAR_OBJECT:
            return
        if self._state_machine.state == STATE_STOP:
            return
        if self._state_machine.is_waiting_assistant_idle_ack():
            return
        packet = parse_short_packet(line)
        if packet is not None and packet.get("type") == "v":
            self._apply_velocity_packet(packet, source="uart3")
            self._uart3_velocity_received_this_tick = True
            return
        if line.lower().startswith("v,"):
            self._record_error("invalid velocity packet")

    def _handle_uart6_line(self, line: str) -> None:
        """处理单条 UART6 视觉速度输入行

        @param line 原始输入行
        """

        if not line:
            return
        packet = parse_short_packet(line)
        if packet is not None and packet.get("type") == "v":
            if self._state_machine.allows_search_velocity() or self._state_machine.state == STATE_TRANSPORT_OBJECT:
                self._latest_uart6_velocity = packet
            return
        if packet is not None and packet.get("type") == "a":
            pending = self._pending_hook
            if (
                pending is not None
                and pending.get("sent_once")
                and int(packet["reliable_seq"]) == int(pending["reliable_seq"])
            ):
                self._active_hook_context_id = int(pending["context_id"])
                if pending.get("kind") == "transport_hook":
                    self._transport_hook_acknowledged = True
                    if self._transport_sync_acknowledged:
                        self._state_machine.mark_transport_ready()
                elif self._state_machine.state == STATE_SEARCH_OBJECT:
                    self._state_machine.mark_restart_search_hook_acknowledged()
                self._pending_hook = None
                self._drain_pending_hook_event()
            return
        if packet is not None and packet.get("type") == "r":
            self._write_uart6_reliable_line(format_ack_packet(packet["reliable_seq"]))
            if self._active_hook_context_id == int(packet["context_id"]):
                self._state_machine.handle_event(
                    context_id=packet["context_id"],
                    event=packet["event"],
                    value=packet["value"],
                )
            elif (
                self._pending_hook is not None
                and self._pending_hook.get("sent_once")
                and int(packet["context_id"]) == int(self._pending_hook["context_id"])
            ):
                self._pending_hook_event = {
                    "context_id": int(packet["context_id"]),
                    "event": int(packet["event"]),
                    "value": int(packet["value"]),
                }
            return
        if line.lower().startswith("v,"):
            self._record_error("invalid uart6 velocity packet")

    def _handle_uart8_line(self, line: str) -> None:
        """处理 UART8 回传短包

        @param line 原始输入行
        """

        packet = parse_uart8_short_packet(line)
        if packet is None:
            return
        if packet.get("type") == "a":
            seq = int(packet["seq"])
            pending = self._pending_assistant_sync
            if (
                pending is not None
                and pending.get("sent_once")
                and seq == int(pending["seq"])
            ):
                if pending.get("kind") == "assistant_idle":
                    self._state_machine.mark_assistant_idle_acknowledged()
                elif pending.get("kind") == "assistant_follow":
                    self._state_machine.mark_assistant_follow_acknowledged()
                elif pending.get("kind") == "assistant_transport":
                    self._transport_sync_acknowledged = True
                    if self._transport_hook_acknowledged:
                        self._state_machine.mark_transport_ready()
                elif pending.get("kind") == "assistant_clear":
                    self._clear_sync_acknowledged = True
                self._pending_assistant_sync = None
                return
            pending = self._pending_sync
            if (
                pending is not None
                and pending.get("sent_once")
                and seq == int(pending["seq"])
            ):
                self._pending_sync = None
        elif packet.get("type") == "r":
            self._write_forward_reliable_line(format_ack_packet(packet["seq"]))
            self.last_report = packet
            if int(packet["event"]) == EVENT_TARGET_FOUND:
                self._assistant_target_found_report = dict(packet)
                self._state_machine.handle_assistant_target_found(packet["value"])
            elif int(packet["event"]) == EVENT_ALIGNED:
                self._state_machine.handle_assistant_aligned(packet["value"])
            elif int(packet["event"]) == EVENT_CLEARED:
                self._state_machine.handle_assistant_cleared(packet["value"])

    def _apply_latest_uart6_velocity(self) -> None:
        packet = self._latest_uart6_velocity
        if packet is not None:
            self._apply_velocity_packet(packet, source="uart6", force_no_omega=True)
            if self._state_machine.state == STATE_SEARCH_OBJECT and getattr(
                self._state_machine, "_orbit_completed", False
            ):
                target_heading_deg = (
                    float(self._state_machine._boot_heading_deg)
                    + float(MASTER_ORBIT_TARGET_DEG)
                )
                self._transport_car.set_heading_target(target_heading_deg)

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
            source="master_transport",
            has_omega=False,
        )

    def _forward_current_chassis_velocity(self) -> None:
        if not self._state_machine.allows_assistant_velocity_forward():
            return
        if self._pending_assistant_sync is not None or self._pending_sync is not None:
            return
        state = self._transport_car.control_state
        omega = state.get("omega")
        if omega is None:
            line = format_velocity_packet(state.get("vx", 0.0), state.get("vy", 0.0))
        else:
            line = format_velocity_packet(state.get("vx", 0.0), state.get("vy", 0.0), omega)
        self._write_forward_line(line)

    def _apply_velocity_packet(self, packet: dict, source: str, force_no_omega: bool = False) -> None:
        omega = 0.0 if force_no_omega else float(packet.get("omega", 0.0))
        self._transport_car.handle_velocity_packet(
            float(packet["vx"]),
            float(packet["vy"]),
            omega,
            source=source,
            has_omega=False if force_no_omega else bool(packet.get("has_omega")),
        )

    def _send_pending_sync(self) -> None:
        pending = self._select_active_pending_sync()
        if pending is None:
            return
        now_ms = self._now_ms()
        if not should_resend(now_ms, pending.get("last_sent_ms"), RELIABLE_RESEND_INTERVAL_MS):
            return
        wrote_all = self._write_forward_reliable_line(
            "s,%d,%d,%d,%d"
            % (pending["seq"], pending["state"], pending["target"], pending["arg"])
        )
        if wrote_all:
            pending["last_sent_ms"] = now_ms
            pending["sent_once"] = True

    def _select_active_pending_sync(self):
        """选择当前应该发送或重发的 UART8 可靠同步请求"""

        if self._pending_assistant_sync is not None:
            return self._pending_assistant_sync
        if self._pending_sync is not None:
            return self._pending_sync
        return self._pending_sync

    def _write_forward_line(self, line: str) -> None:
        """把短包写到 UART8 主辅通信链路

        @param line 要转发的短包文本
        """

        try:
            self._transport_car.uart8.write("%s\r\n" % line)
        except Exception:
            self._record_error("uart8 forward write failed")

    def _write_forward_reliable_line(self, line: str) -> bool:
        """把可靠短包写到 UART8 主辅通信链路"""

        try:
            return bool(write_reliable_line(self._transport_car.uart8, line))
        except Exception:
            self._record_error("uart8 forward write failed")
            return False

    def _write_uart6_data_line(self, line: str) -> None:
        """把短包写到本车 UART6 视觉链路

        @param line 要写出的短包文本
        """

        try:
            self._uart6.write("%s\r\n" % line)
        except Exception:
            self._record_error("uart6 write failed")

    def _write_uart6_reliable_line(self, line: str) -> bool:
        """把可靠短包写到本车 UART6 视觉链路"""

        try:
            return bool(write_reliable_line(self._uart6, line))
        except Exception:
            self._record_error("uart6 write failed")
            return False

    def _advance_state_machine(self) -> None:
        """按当前底盘执行状态推进主车状态机"""

        orbit_finished = False
        if self._orbit_command_active:
            orbit_finished = not bool(getattr(self._transport_car, "command_lock", False))
        self._state_machine.step(orbit_finished=orbit_finished)
        if self._state_machine.state != STATE_ORBITING:
            self._orbit_command_active = False

    def _drain_state_machine_outputs(self) -> None:
        """消费主车状态机的一次性输出"""

        hook_request = self._state_machine.poll_hook_request()
        if hook_request is not None:
            self._hook_seq = (self._hook_seq + 1) % 256
            self._active_hook_context_id = None
            self._latest_uart6_velocity = None
            self._pending_hook_event = None
            self._rx_buf6 = ""
            self._transport_hook_acknowledged = False
            self._pending_hook = {
                "kind": hook_request.get("kind"),
                "reliable_seq": self._hook_seq,
                "context_id": int(hook_request["context_id"]),
                "state": int(hook_request["state"]),
                "target": int(hook_request["target"]),
                "arg": int(hook_request["arg"]),
                "last_sent_ms": None,
                "sent_once": False,
            }

        assistant_request = self._state_machine.poll_assistant_request()
        if assistant_request is not None:
            request_kind = assistant_request.get("kind")
            if request_kind == "assistant_idle":
                stop_source = "master_wait_assistant_idle"
                if self._state_machine.state == STATE_STOP:
                    stop_source = "master_transport_finish_stop"
                self._latest_uart6_velocity = None
                self._transport_car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    source=stop_source,
                    has_omega=True,
                )
            elif request_kind == "assistant_follow":
                self._latest_uart6_velocity = None
            elif request_kind == "assistant_transport":
                self._hook_seq = (self._hook_seq + 1) % 256
                self._active_hook_context_id = None
                self._latest_uart6_velocity = None
                self._pending_hook_event = None
                self._rx_buf6 = ""
                self._transport_sync_acknowledged = False
                self._transport_hook_acknowledged = False
                self._transport_car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    source="master_wait_transport_ready",
                    has_omega=True,
                )
                self._pending_hook = {
                    "kind": "transport_hook",
                    "reliable_seq": self._hook_seq,
                    "context_id": int(self._state_machine._current_context_id),
                    "state": STATE_SEARCH_OBJECT,
                    "target": int(assistant_request["target"]),
                    "arg": int(MASTER_TRANSPORT_HOOK_CONFIG_ID),
                    "last_sent_ms": None,
                    "sent_once": False,
                }
            elif request_kind == "assistant_clear":
                self._latest_uart6_velocity = None
                self._clear_sync_acknowledged = False
                self._clear_motion_started = False
                self._clear_master_completed_phase = None
                self._clear_motion_stop_ticks = 0
                self._transport_car.handle_velocity_packet(
                    0.0,
                    0.0,
                    0.0,
                    source="master_wait_clear_ready",
                    has_omega=True,
                )
            seq = self._assistant_sync_seq
            self._pending_assistant_sync = {
                "kind": request_kind,
                "seq": seq,
                "state": int(assistant_request["state"]),
                "target": int(assistant_request["target"]),
                "arg": int(assistant_request["arg"]),
                "last_sent_ms": None,
                "sent_once": False,
            }
            self._assistant_sync_seq = (self._assistant_sync_seq + 2) % 256

        orbit_command = self._state_machine.poll_orbit_command()
        if orbit_command is not None:
            self._transport_car.set_orbit_target(
                float(orbit_command["target_heading_deg"]),
                float(MASTER_ORBIT_RADIUS_SCALE),
            )
            self._orbit_command_active = True

    def _run_clear_phase(self) -> None:
        """在搬运结束后驱动主车收尾位置动作并等待辅车完成"""

        if self._state_machine.state != STATE_CLEAR_OBJECT:
            self._clear_motion_started = False
            self._clear_master_completed_phase = None
            self._clear_motion_stop_ticks = 0
            self._turn_back_target_heading_deg = None
            return
        clear_phase = int(self._state_machine.get_clear_phase())
        if clear_phase != CLEAR_PHASE_RETREAT and clear_phase != CLEAR_PHASE_TRANSLATE:
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
                max_speed_cmd=float(TRANSPORT_CLEAR_RETREAT_MAX_SPEED),
            )
        else:
            self._transport_car.set_relative_translation_target(
                -float(TRANSPORT_CLEAR_STEP_DISTANCE_M),
                0.0,
                hold_heading_deg=self._turn_back_target_heading_deg,
            )
        self._clear_motion_started = True
        self._clear_motion_stop_ticks = 0

    def _run_turn_back_phase(self) -> None:
        """在后退完成后执行主车回身"""

        if not self._state_machine.is_post_clear_turn_back_pending():
            self._turn_back_rotation_started = False
            self._turn_back_stop_ticks = 0
            return
        if self._turn_back_rotation_started:
            self._write_uart3_turn_heading_debug()
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
        """判断三轮实际轮速是否都已进入静止范围"""

        wheel_states = getattr(self._transport_car, "wheel_states", ())
        if len(wheel_states) < 3:
            return False
        threshold = float(MOTION_STOP_SPEED_THRESHOLD)
        for state in wheel_states:
            if abs(float(state.get("filtered_speed", 0.0))) > threshold:
                return False
        return True

    def _send_pending_hook(self) -> None:
        """重复发送待确认的视觉 hook 同步包"""

        pending = self._pending_hook
        if pending is None:
            return
        now_ms = self._now_ms()
        if not should_resend(now_ms, pending.get("last_sent_ms"), RELIABLE_RESEND_INTERVAL_MS):
            return
        wrote_all = self._write_uart6_reliable_line(
            format_state_sync_packet(
                pending["reliable_seq"],
                pending["context_id"],
                pending["state"],
                pending["target"],
                pending["arg"],
            )
        )
        if wrote_all:
            pending["last_sent_ms"] = now_ms
            pending["sent_once"] = True

    def _drain_pending_hook_event(self) -> None:
        """在 hook 建立后补发此前暂存的命中事件"""

        pending_event = self._pending_hook_event
        if pending_event is None:
            return
        self._pending_hook_event = None
        self._state_machine.handle_event(
            context_id=pending_event["context_id"],
            event=pending_event["event"],
            value=pending_event["value"],
        )

    def _record_error(self, text: str) -> None:
        """记录最小错误文本供联调使用

        @param text 错误描述
        """

        self._last_error_text = text
        self._transport_car.last_exception_text = text

    @staticmethod
    def _noop_transport_uart() -> None:
        """屏蔽共享底盘自己的 UART3 消费入口"""

        return None
