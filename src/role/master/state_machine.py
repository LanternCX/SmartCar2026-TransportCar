"""主车单车状态机

@file src/role/master/state_machine.py
"""

from role.clear_phase import CLEAR_PHASE_FORWARD, CLEAR_PHASE_NONE, CLEAR_PHASE_RETREAT
from role.task_sync import pack_task_arg
from role.transport_plan import push_heading_for_edge, target_edge_for_object
from utils.startup_log import log

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value


ASSISTANT_FOLLOW_SYNC_STATE = const(1)
ASSISTANT_FOLLOW_SYNC_TARGET = const(0)
ASSISTANT_OBJECT_SYNC_STATE = const(2)
ASSISTANT_OBJECT_SYNC_TARGET = const(1)
ASSISTANT_ORBIT_SYNC_STATE = const(3)
ASSISTANT_ORBIT_SYNC_TARGET = const(1)
ASSISTANT_TRANSPORT_SYNC_STATE = const(4)
ASSISTANT_TRANSPORT_SYNC_TARGET = const(1)
ASSISTANT_CLEAR_SYNC_STATE = const(5)
ASSISTANT_CLEAR_SYNC_TARGET = const(1)
ASSISTANT_RETURN_FOLLOW_SYNC_STATE = const(6)
ASSISTANT_RETURN_FOLLOW_SYNC_TARGET = const(0)
ASSISTANT_STARTUP_SYNC_STATE = const(8)
ASSISTANT_STARTUP_SYNC_TARGET = const(0)

# 主车全局状态编号
STATE_IDLE = const(0)
STATE_SEARCH_OBJECT = const(1)
STATE_ORBITING = const(2)
# STATE_STOP: 暂不启用，详细原因见 docs/developer/vision.md。
STATE_STOP = const(3)
STATE_TRANSPORT_OBJECT = const(4)
STATE_CLEAR_OBJECT = const(5)
STATE_RETURN_GARAGE_RETREAT = const(6)
STATE_RETURN_GARAGE_LINE = const(7)
STATE_FINISHED = const(8)
STATE_STARTUP_MOVE = const(9)
STATE_STARTUP_SYNC = const(10)
_STATE_NAMES = (
    "IDLE",
    "SEARCH_OBJECT",
    "ORBITING",
    "STOP",
    "TRANSPORT_OBJECT",
    "CLEAR_OBJECT",
    "RETURN_GARAGE_RETREAT",
    "RETURN_GARAGE_LINE",
    "FINISHED",
    "STARTUP_MOVE",
    "STARTUP_SYNC",
)

# 主车目标编号
TARGET_NONE = const(0)
TARGET_OBJECT = const(1)
TARGET_EDGE_LINE = const(3)

# 主车视觉事件编号
EVENT_TARGET_FOUND = const(6)
EVENT_ALIGNED = const(7)
EVENT_ARRIVED = const(8)
EVENT_CLEARED = const(9)
EVENT_RETURN_LINE_ALIGNED = const(10)

_CLEAR_STAGE_TURN_BACK = const(3)


class MasterStateMachine:
    """维护主车单车寻找、搬运与回身状态"""

    def __init__(
        self,
        search_task_arg,
        boot_heading_deg,
        orbit_delta_deg,
        assistant_object_arg=1,
        assistant_transport_arg=1,
        transport_task_arg=2,
        finish_task_arg=3,
        return_line_task_arg=5,
        total_object_count=999,
        initial_context_id=0,
    ):
        self.state = STATE_IDLE
        self._search_task_arg = int(search_task_arg)
        self._boot_heading_deg = float(boot_heading_deg)
        self._orbit_delta_deg = float(orbit_delta_deg)
        self._assistant_object_arg = int(assistant_object_arg)
        self._assistant_transport_arg = int(assistant_transport_arg)
        self._transport_task_arg = int(transport_task_arg)
        self._finish_task_arg = int(finish_task_arg)
        self._return_line_task_arg = int(return_line_task_arg)
        self._required_object_count = int(total_object_count)
        self.completed_object_count = 0
        self._current_context_id = int(initial_context_id) % 256
        self._pending_task_request = None
        self._pending_assistant_request = None
        self._pending_orbit_command = None
        self._search_started = False
        self._orbit_completed = False
        self._waiting_assistant_object_ack = False
        self._waiting_assistant_follow_ack = False
        self._waiting_restart_search_task_ack = False
        self._assistant_object_request_emitted = False
        self._assistant_target_found_pending = False
        self._assistant_orbit_request_emitted = False
        self._assistant_transport_request_emitted = False
        self._master_aligned = False
        self._assistant_aligned = False
        self._transport_ready = False
        self._clear_phase = CLEAR_PHASE_NONE
        self._master_cleared = False
        self._assistant_cleared = False
        self._current_object_id = 0
        self._current_target_edge = None

    def _enter_state(self, state):
        """进入主车全局状态并输出一次跳转日志"""

        state = int(state)
        if self.state == state:
            return
        self.state = state
        log("master_state", _STATE_NAMES[state])

    def step(self, orbit_finished):
        """推进单拍状态机"""

        if not self._search_started and self.state == STATE_IDLE:
            self._search_started = True
            self._enter_state(STATE_STARTUP_SYNC)
            self._pending_assistant_request = {
                "kind": "assistant_startup",
                "state": ASSISTANT_STARTUP_SYNC_STATE,
                "target": ASSISTANT_STARTUP_SYNC_TARGET,
                "arg": 0,
            }
            return

        if self.state == STATE_ORBITING and orbit_finished:
            self._enter_state(STATE_SEARCH_OBJECT)
            self._orbit_completed = True
            self._master_aligned = False
            self._assistant_aligned = False
            self._current_context_id = (self._current_context_id + 1) % 256
            self._pending_task_request = {
                "context_id": self._current_context_id,
                "state": STATE_SEARCH_OBJECT,
                "target": TARGET_OBJECT,
                "arg": self._transport_task_arg,
            }
            if self._assistant_target_found_pending and not self._assistant_orbit_request_emitted:
                self._assistant_target_found_pending = False
                self._assistant_orbit_request_emitted = True
                self._pending_assistant_request = {
                    "kind": "assistant_orbit",
                    "state": ASSISTANT_ORBIT_SYNC_STATE,
                    "target": ASSISTANT_ORBIT_SYNC_TARGET,
                    "arg": pack_task_arg(0, self._current_object_id),
                }

    def mark_startup_move_completed(self):
        """标记启动动作完成并进入找物体状态"""

        if self.state != STATE_STARTUP_MOVE:
            return
        self._enter_search_with_task(self._search_task_arg)

    def mark_startup_sync_acknowledged(self):
        """标记辅车启动同步已确认并进入启动动作状态"""

        if self.state != STATE_STARTUP_SYNC:
            return
        self._enter_state(STATE_STARTUP_MOVE)

    def handle_event(self, context_id, event, value):
        """消费视觉事件"""

        if int(context_id) != self._current_context_id:
            return
        event = int(event)
        if self.state == STATE_SEARCH_OBJECT:
            if (
                self._waiting_assistant_object_ack
                or self._waiting_assistant_follow_ack
                or self._waiting_restart_search_task_ack
            ):
                return
            if event == EVENT_TARGET_FOUND:
                if self._orbit_completed:
                    return
                self._current_object_id = int(value) & 0xFF
                self._current_target_edge = target_edge_for_object(self._current_object_id)
                self._waiting_assistant_object_ack = True
                self._assistant_object_request_emitted = True
                self._pending_assistant_request = {
                    "kind": "assistant_object",
                    "state": ASSISTANT_OBJECT_SYNC_STATE,
                    "target": ASSISTANT_OBJECT_SYNC_TARGET,
                    "arg": pack_task_arg(
                        self._assistant_object_arg,
                        self._current_object_id,
                    ),
                }
                return
            if event == EVENT_ALIGNED:
                if not self._orbit_completed:
                    return
                self._master_aligned = True
                self._try_enter_transport()
            return
        if self.state == STATE_TRANSPORT_OBJECT:
            if event != EVENT_ARRIVED:
                return
            self._enter_state(STATE_CLEAR_OBJECT)
            self._enter_clear_phase(CLEAR_PHASE_RETREAT)
            return
        if self.state == STATE_CLEAR_OBJECT:
            return
        if self.state == STATE_RETURN_GARAGE_RETREAT:
            return

    def mark_assistant_object_acknowledged(self):
        """标记辅车找物体同步已确认并开始主车绕行"""

        if self._waiting_assistant_object_ack:
            self._waiting_assistant_object_ack = False
            self._current_context_id = (self._current_context_id + 1) % 256
            self._enter_state(STATE_ORBITING)
            self._pending_orbit_command = {
                "target_heading_deg": push_heading_for_edge(self._current_target_edge),
            }

    def handle_assistant_target_found(self, value):
        """消费辅车目标命中回报"""

        _ = value
        if self.state == STATE_ORBITING:
            if self._assistant_object_request_emitted and not self._assistant_orbit_request_emitted:
                self._assistant_target_found_pending = True
            return
        if self.state != STATE_SEARCH_OBJECT:
            return
        if not self._assistant_object_request_emitted:
            return
        if self._assistant_orbit_request_emitted:
            return
        self._assistant_orbit_request_emitted = True
        self._pending_assistant_request = {
            "kind": "assistant_orbit",
            "state": ASSISTANT_ORBIT_SYNC_STATE,
            "target": ASSISTANT_ORBIT_SYNC_TARGET,
            "arg": pack_task_arg(0, self._current_object_id),
        }

    def handle_assistant_aligned(self, value):
        """消费辅车二次对正完成回报"""

        _ = value
        if self.state != STATE_SEARCH_OBJECT:
            return
        if not self._assistant_orbit_request_emitted:
            return
        self._assistant_aligned = True
        self._try_enter_transport()

    def _try_enter_transport(self):
        """在两侧都完成对正后切入搬运态"""

        if self.state != STATE_SEARCH_OBJECT:
            return
        if not self._orbit_completed:
            return
        if not self._assistant_orbit_request_emitted:
            return
        if not self._master_aligned or not self._assistant_aligned:
            return
        if self._assistant_transport_request_emitted:
            return
        self._assistant_transport_request_emitted = True
        self._pending_assistant_request = {
            "kind": "assistant_transport",
            "state": ASSISTANT_TRANSPORT_SYNC_STATE,
            "target": ASSISTANT_TRANSPORT_SYNC_TARGET,
            "arg": pack_task_arg(
                self._assistant_transport_arg,
                self._current_object_id,
            ),
        }

    def mark_transport_ready(self):
        """在运行时完成搬运入口同步后切入搬运态"""

        if self.state != STATE_SEARCH_OBJECT:
            return
        if not self._assistant_transport_request_emitted:
            return
        if not self._master_aligned or not self._assistant_aligned:
            return
        self._transport_ready = True
        self._enter_state(STATE_TRANSPORT_OBJECT)
        self._current_context_id = (self._current_context_id + 1) % 256
        self._pending_task_request = {
            "kind": "finish_task",
            "context_id": self._current_context_id,
            "state": STATE_TRANSPORT_OBJECT,
            "target": TARGET_EDGE_LINE,
            "arg": self._finish_task_arg,
        }

    def mark_master_cleared(self):
        """标记主车已完成搬运收尾当前段位置动作"""

        if self.state != STATE_CLEAR_OBJECT:
            return
        if self._clear_phase not in (
            CLEAR_PHASE_RETREAT,
            CLEAR_PHASE_FORWARD,
        ):
            return
        self._master_cleared = True
        self._try_advance_clear_phase()

    def handle_assistant_cleared(self, value):
        """消费辅车搬运后脱离完成回报"""

        if self.state != STATE_CLEAR_OBJECT:
            return
        if int(value) != int(self._clear_phase):
            return
        self._assistant_cleared = True
        self._try_advance_clear_phase()

    def _try_advance_clear_phase(self):
        """在当前收尾阶段完成后推进到下一阶段"""

        if self.state != STATE_CLEAR_OBJECT:
            return
        if not self._master_cleared or not self._assistant_cleared:
            return
        if self._clear_phase == CLEAR_PHASE_RETREAT:
            if self.completed_object_count + 1 >= self._required_object_count:
                self.completed_object_count += 1
                self._pending_assistant_request = {
                    "kind": "assistant_return_line",
                    "state": ASSISTANT_RETURN_FOLLOW_SYNC_STATE,
                    "target": ASSISTANT_RETURN_FOLLOW_SYNC_TARGET,
                    "arg": 0,
                }
                self._enter_return_retreat()
                return
            self._clear_phase = _CLEAR_STAGE_TURN_BACK
            self._master_cleared = False
            self._assistant_cleared = False
            return
        if self._clear_phase == CLEAR_PHASE_FORWARD:
            self._restart_search_after_clear()

    def can_start_turn_back_rotation(self):
        """判断回身阶段是否已经满足开始旋转条件"""

        return self.state == STATE_CLEAR_OBJECT and self._clear_phase == _CLEAR_STAGE_TURN_BACK

    def mark_turn_back_completed(self):
        """标记主车回身完成并推进下一阶段"""

        if self.state != STATE_CLEAR_OBJECT:
            return
        if self._clear_phase != _CLEAR_STAGE_TURN_BACK:
            return
        if self.completed_object_count + 1 >= self._required_object_count:
            self.completed_object_count += 1
            self._enter_return_retreat()
            return
        self._enter_clear_phase(CLEAR_PHASE_FORWARD)

    def _restart_search_after_clear(self):
        """在搬运收尾完成后重启寻找阶段"""

        self.completed_object_count += 1
        if self.completed_object_count >= self._required_object_count:
            self._enter_return_retreat()
            return
        self._orbit_completed = False
        self._waiting_assistant_object_ack = False
        self._waiting_assistant_follow_ack = True
        self._waiting_restart_search_task_ack = True
        self._assistant_object_request_emitted = False
        self._assistant_target_found_pending = False
        self._assistant_orbit_request_emitted = False
        self._assistant_transport_request_emitted = False
        self._master_aligned = False
        self._assistant_aligned = False
        self._transport_ready = False
        self._clear_phase = CLEAR_PHASE_NONE
        self._master_cleared = False
        self._assistant_cleared = False
        self._current_object_id = 0
        self._current_target_edge = None
        self._enter_state(STATE_SEARCH_OBJECT)
        self._enter_search_with_task(self._search_task_arg)
        self._pending_assistant_request = {
            "kind": "assistant_follow",
            "state": ASSISTANT_FOLLOW_SYNC_STATE,
            "target": ASSISTANT_FOLLOW_SYNC_TARGET,
            "arg": 0,
        }

    def _reset_round_flags(self):
        """清理单轮找物体、搬运和收尾阶段标记"""

        self._orbit_completed = False
        self._waiting_assistant_object_ack = False
        self._waiting_assistant_follow_ack = False
        self._waiting_restart_search_task_ack = False
        self._assistant_object_request_emitted = False
        self._assistant_target_found_pending = False
        self._assistant_orbit_request_emitted = False
        self._assistant_transport_request_emitted = False
        self._master_aligned = False
        self._assistant_aligned = False
        self._transport_ready = False
        self._clear_phase = CLEAR_PHASE_NONE
        self._master_cleared = False
        self._assistant_cleared = False
        self._current_object_id = 0
        self._current_target_edge = None

    def _enter_return_retreat(self):
        """进入主车回库后退找黄线段"""

        self._reset_round_flags()
        self._enter_state(STATE_RETURN_GARAGE_RETREAT)
        self._current_context_id = (self._current_context_id + 1) % 256
        self._pending_task_request = {
            "kind": "return_line_task",
            "context_id": self._current_context_id,
            "state": STATE_RETURN_GARAGE_RETREAT,
            "target": TARGET_EDGE_LINE,
            "arg": self._return_line_task_arg,
        }

    def _enter_return_line(self):
        """进入主车回库黄线平移段"""

        self._enter_state(STATE_RETURN_GARAGE_LINE)
        self._current_context_id = (self._current_context_id + 1) % 256
        self._pending_task_request = {
            "kind": "return_line_task",
            "context_id": self._current_context_id,
            "state": STATE_RETURN_GARAGE_LINE,
            "target": TARGET_EDGE_LINE,
            "arg": self._return_line_task_arg,
        }

    def _enter_finished(self):
        """进入全部任务完成态"""

        self._enter_state(STATE_FINISHED)

    def mark_assistant_follow_acknowledged(self):
        """标记辅车 follow 同步已确认"""

        self._waiting_assistant_follow_ack = False

    def mark_restart_search_task_acknowledged(self):
        """标记回身后主车本车视觉搜索 task 已确认"""

        self._waiting_restart_search_task_ack = False

    def is_post_clear_turn_back_pending(self):
        """当前是否处于收尾阶段中的主车转身段"""

        return self.state == STATE_CLEAR_OBJECT and self._clear_phase == _CLEAR_STAGE_TURN_BACK

    def get_clear_phase(self):
        """返回当前搬运收尾阶段编号"""

        return self._clear_phase

    def get_push_heading_deg(self):
        """返回当前物体目标边对应的推动朝向."""

        return push_heading_for_edge(self._current_target_edge)

    def _enter_clear_phase(self, clear_phase):
        """进入指定的搬运收尾阶段并按需同步辅车"""

        self._clear_phase = int(clear_phase)
        self._master_cleared = False
        self._assistant_cleared = False
        self._pending_assistant_request = {
            "kind": "assistant_clear",
            "state": ASSISTANT_CLEAR_SYNC_STATE,
            "target": ASSISTANT_CLEAR_SYNC_TARGET,
            "arg": int(clear_phase),
        }

    def _enter_search_with_task(self, task_arg):
        """创建新一轮主车找物体 task 上下文"""

        self._enter_state(STATE_SEARCH_OBJECT)
        self._current_context_id = (self._current_context_id + 1) % 256
        self._pending_task_request = {
            "context_id": self._current_context_id,
            "state": STATE_SEARCH_OBJECT,
            "target": TARGET_OBJECT,
            "arg": int(task_arg),
        }

    def poll_task_request(self):
        """取出一次性 task 请求"""

        pending = self._pending_task_request
        self._pending_task_request = None
        return pending

    def poll_assistant_request(self):
        """取出一次性辅车状态同步请求"""

        pending = self._pending_assistant_request
        self._pending_assistant_request = None
        return pending

    def poll_orbit_command(self):
        """取出一次性绕行命令"""

        pending = self._pending_orbit_command
        self._pending_orbit_command = None
        return pending

    def is_waiting_assistant_object_ack(self):
        """当前是否正在等待辅车找物体同步确认"""

        return self._waiting_assistant_object_ack

    def allows_search_velocity(self):
        """当前状态是否允许主车视觉搜索速度生效"""

        if self.state != STATE_SEARCH_OBJECT:
            return False
        if self._waiting_assistant_object_ack:
            return False
        if self._waiting_assistant_follow_ack:
            return False
        if self._waiting_restart_search_task_ack:
            return False
        if self._master_aligned:
            return False
        if self._assistant_transport_request_emitted and not self._transport_ready:
            return False
        return True

    def allows_assistant_velocity_forward(self):
        """当前状态是否允许向辅车转发速度前馈"""

        if self.state == STATE_TRANSPORT_OBJECT:
            return True
        return self.allows_search_velocity()

    def needs_assistant_report_turn(self):
        """当前是否需要给辅车可靠回报保留 UART8 回话窗口"""

        if self.state != STATE_SEARCH_OBJECT:
            return False
        if not self._orbit_completed:
            return False
        if not self._assistant_object_request_emitted:
            return False
        if self._assistant_transport_request_emitted:
            return False
        return not self._assistant_aligned
