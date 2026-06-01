"""主车单车状态机

@file src/vision/master/state_machine.py
"""

from vision.clear_phase import CLEAR_PHASE_FORWARD, CLEAR_PHASE_NONE, CLEAR_PHASE_RETREAT
from utils.startup_log import log

ASSISTANT_IDLE_SYNC_STATE = 0
ASSISTANT_IDLE_SYNC_TARGET = 0
ASSISTANT_FOLLOW_SYNC_STATE = 1
ASSISTANT_FOLLOW_SYNC_TARGET = 0
ASSISTANT_OBJECT_SYNC_STATE = 2
ASSISTANT_OBJECT_SYNC_TARGET = 1
ASSISTANT_ORBIT_SYNC_STATE = 3
ASSISTANT_ORBIT_SYNC_TARGET = 1
ASSISTANT_TRANSPORT_SYNC_STATE = 4
ASSISTANT_TRANSPORT_SYNC_TARGET = 1
ASSISTANT_CLEAR_SYNC_STATE = 5
ASSISTANT_CLEAR_SYNC_TARGET = 1
ASSISTANT_RETURN_FOLLOW_SYNC_STATE = 6
ASSISTANT_RETURN_FOLLOW_SYNC_TARGET = 0

# 主车全局状态编号
STATE_IDLE = 0
STATE_SEARCH_OBJECT = 1
STATE_ORBITING = 2
STATE_STOP = 3
STATE_TRANSPORT_OBJECT = 4
STATE_CLEAR_OBJECT = 5
STATE_RETURN_GARAGE_RETREAT = 6
STATE_RETURN_GARAGE_LINE = 7
STATE_FINISHED = 8
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
)

# 主车目标编号
TARGET_NONE = 0
TARGET_OBJECT = 1
TARGET_EDGE_LINE = 3

# 主车视觉事件编号
EVENT_TARGET_FOUND = 6
EVENT_ALIGNED = 7
EVENT_ARRIVED = 8
EVENT_CLEARED = 9
EVENT_RETURN_LINE_ALIGNED = 10
EVENT_RETURN_GARAGE_FINISHED = 12

_CLEAR_STAGE_TURN_BACK = 3


class MasterStateMachine:
    """维护主车单车寻找、搬运与回身状态"""

    def __init__(
        self,
        hook_arg,
        boot_heading_deg,
        orbit_delta_deg,
        assistant_object_arg=1,
        assistant_transport_arg=1,
        transport_hook_arg=2,
        finish_hook_arg=3,
        return_line_hook_arg=5,
        total_object_count=999,
        initial_context_id=0,
    ):
        self.state = STATE_IDLE
        self._hook_arg = int(hook_arg)
        self._boot_heading_deg = float(boot_heading_deg)
        self._orbit_delta_deg = float(orbit_delta_deg)
        self._assistant_object_arg = int(assistant_object_arg)
        self._assistant_transport_arg = int(assistant_transport_arg)
        self._transport_hook_arg = int(transport_hook_arg)
        self._finish_hook_arg = int(finish_hook_arg)
        self._return_line_hook_arg = int(return_line_hook_arg)
        self._required_object_count = int(total_object_count)
        self.completed_object_count = 0
        self._current_context_id = int(initial_context_id) % 256
        self._pending_hook_request = None
        self._pending_assistant_request = None
        self._pending_orbit_command = None
        self._search_started = False
        self._orbit_completed = False
        self._waiting_assistant_idle_ack = False
        self._waiting_assistant_follow_ack = False
        self._waiting_restart_search_hook_ack = False
        self._assistant_object_request_emitted = False
        self._assistant_orbit_request_emitted = False
        self._assistant_transport_request_emitted = False
        self._master_aligned = False
        self._assistant_aligned = False
        self._transport_ready = False
        self._clear_phase = CLEAR_PHASE_NONE
        self._master_cleared = False
        self._assistant_cleared = False

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
            self._enter_search_with_hook(self._hook_arg)
            return

        if self.state == STATE_ORBITING and orbit_finished:
            self._enter_state(STATE_SEARCH_OBJECT)
            self._orbit_completed = True
            self._master_aligned = False
            self._assistant_aligned = False
            self._current_context_id = (self._current_context_id + 1) % 256
            self._pending_hook_request = {
                "context_id": self._current_context_id,
                "state": STATE_SEARCH_OBJECT,
                "target": TARGET_OBJECT,
                "arg": self._transport_hook_arg,
            }
            if not self._assistant_object_request_emitted:
                self._assistant_object_request_emitted = True
                self._pending_assistant_request = {
                    "kind": "assistant_object",
                    "state": ASSISTANT_OBJECT_SYNC_STATE,
                    "target": ASSISTANT_OBJECT_SYNC_TARGET,
                    "arg": self._assistant_object_arg,
                }

    def handle_event(self, context_id, event, value):
        """消费视觉事件"""

        _ = value
        if int(context_id) != self._current_context_id:
            return
        event = int(event)
        if self.state == STATE_SEARCH_OBJECT:
            if (
                self._waiting_assistant_idle_ack
                or self._waiting_assistant_follow_ack
                or self._waiting_restart_search_hook_ack
            ):
                return
            if event == EVENT_TARGET_FOUND:
                if self._orbit_completed:
                    return
                self._waiting_assistant_idle_ack = True
                self._pending_assistant_request = {
                    "kind": "assistant_idle",
                    "state": ASSISTANT_IDLE_SYNC_STATE,
                    "target": ASSISTANT_IDLE_SYNC_TARGET,
                    "arg": 0,
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
            if event == EVENT_RETURN_LINE_ALIGNED:
                self._enter_return_line()
            return
        if self.state == STATE_RETURN_GARAGE_LINE:
            if event == EVENT_RETURN_GARAGE_FINISHED:
                self._enter_finished()
            return

    def mark_assistant_idle_acknowledged(self):
        """标记辅车 idle 同步已确认"""

        if self._waiting_assistant_idle_ack:
            self._waiting_assistant_idle_ack = False
            self._current_context_id = (self._current_context_id + 1) % 256
            self._enter_state(STATE_ORBITING)
            self._pending_orbit_command = {
                "target_heading_deg": self._boot_heading_deg + self._orbit_delta_deg,
            }

    def handle_assistant_target_found(self, value):
        """消费辅车目标命中回报"""

        _ = value
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
            "arg": 0,
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
            "arg": self._assistant_transport_arg,
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
        self._pending_hook_request = {
            "kind": "finish_hook",
            "context_id": self._current_context_id,
            "state": STATE_TRANSPORT_OBJECT,
            "target": TARGET_EDGE_LINE,
            "arg": self._finish_hook_arg,
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
            self._clear_phase = _CLEAR_STAGE_TURN_BACK
            self._master_cleared = False
            self._assistant_cleared = False
            if self.completed_object_count + 1 >= self._required_object_count:
                self._pending_assistant_request = {
                    "kind": "assistant_return_line",
                    "state": ASSISTANT_RETURN_FOLLOW_SYNC_STATE,
                    "target": ASSISTANT_RETURN_FOLLOW_SYNC_TARGET,
                    "arg": 0,
                }
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
        self._waiting_assistant_idle_ack = False
        self._waiting_assistant_follow_ack = True
        self._waiting_restart_search_hook_ack = True
        self._assistant_object_request_emitted = False
        self._assistant_orbit_request_emitted = False
        self._assistant_transport_request_emitted = False
        self._master_aligned = False
        self._assistant_aligned = False
        self._transport_ready = False
        self._clear_phase = CLEAR_PHASE_NONE
        self._master_cleared = False
        self._assistant_cleared = False
        self._enter_state(STATE_SEARCH_OBJECT)
        self._enter_search_with_hook(self._hook_arg)
        self._pending_assistant_request = {
            "kind": "assistant_follow",
            "state": ASSISTANT_FOLLOW_SYNC_STATE,
            "target": ASSISTANT_FOLLOW_SYNC_TARGET,
            "arg": 0,
        }

    def _reset_round_flags(self):
        """清理单轮找物体、搬运和收尾阶段标记"""

        self._orbit_completed = False
        self._waiting_assistant_idle_ack = False
        self._waiting_assistant_follow_ack = False
        self._waiting_restart_search_hook_ack = False
        self._assistant_object_request_emitted = False
        self._assistant_orbit_request_emitted = False
        self._assistant_transport_request_emitted = False
        self._master_aligned = False
        self._assistant_aligned = False
        self._transport_ready = False
        self._clear_phase = CLEAR_PHASE_NONE
        self._master_cleared = False
        self._assistant_cleared = False

    def _enter_return_retreat(self):
        """进入主车回库后退找黄线段"""

        self._reset_round_flags()
        self._enter_state(STATE_RETURN_GARAGE_RETREAT)
        self._current_context_id = (self._current_context_id + 1) % 256
        self._pending_hook_request = {
            "kind": "return_line_hook",
            "context_id": self._current_context_id,
            "state": STATE_RETURN_GARAGE_RETREAT,
            "target": TARGET_EDGE_LINE,
            "arg": self._return_line_hook_arg,
        }

    def _enter_return_line(self):
        """进入主车回库黄线平移段"""

        self._enter_state(STATE_RETURN_GARAGE_LINE)
        self._current_context_id = (self._current_context_id + 1) % 256
        self._pending_hook_request = {
            "kind": "return_line_hook",
            "context_id": self._current_context_id,
            "state": STATE_RETURN_GARAGE_LINE,
            "target": TARGET_EDGE_LINE,
            "arg": self._return_line_hook_arg,
        }

    def _enter_finished(self):
        """进入全部任务完成态"""

        self._enter_state(STATE_FINISHED)

    def mark_assistant_follow_acknowledged(self):
        """标记辅车 follow 同步已确认"""

        self._waiting_assistant_follow_ack = False

    def mark_restart_search_hook_acknowledged(self):
        """标记回身后主车本车视觉搜索 hook 已确认"""

        self._waiting_restart_search_hook_ack = False

    def is_post_clear_turn_back_pending(self):
        """当前是否处于收尾阶段中的主车转身段"""

        return self.state == STATE_CLEAR_OBJECT and self._clear_phase == _CLEAR_STAGE_TURN_BACK

    def get_clear_phase(self):
        """返回当前搬运收尾阶段编号"""

        return self._clear_phase

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

    def _enter_search_with_hook(self, hook_arg):
        """创建新一轮主车找物体 hook 上下文"""

        self._enter_state(STATE_SEARCH_OBJECT)
        self._current_context_id = (self._current_context_id + 1) % 256
        self._pending_hook_request = {
            "context_id": self._current_context_id,
            "state": STATE_SEARCH_OBJECT,
            "target": TARGET_OBJECT,
            "arg": int(hook_arg),
        }

    def poll_hook_request(self):
        """取出一次性 hook 请求"""

        pending = self._pending_hook_request
        self._pending_hook_request = None
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

    def is_waiting_assistant_idle_ack(self):
        """当前是否正在等待辅车 idle 确认"""

        return self._waiting_assistant_idle_ack

    def allows_search_velocity(self):
        """当前状态是否允许主车视觉搜索速度生效"""

        if self.state != STATE_SEARCH_OBJECT:
            return False
        if self._waiting_assistant_idle_ack:
            return False
        if self._waiting_assistant_follow_ack:
            return False
        if self._waiting_restart_search_hook_ack:
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
