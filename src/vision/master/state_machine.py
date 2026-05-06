"""主车单车状态机

@file src/vision/master/state_machine.py
"""

ASSISTANT_IDLE_SYNC_STATE = 0
ASSISTANT_IDLE_SYNC_TARGET = 0
ASSISTANT_OBJECT_SYNC_STATE = 2
ASSISTANT_OBJECT_SYNC_TARGET = 1
ASSISTANT_ORBIT_SYNC_STATE = 3
ASSISTANT_ORBIT_SYNC_TARGET = 1
ASSISTANT_TRANSPORT_SYNC_STATE = 4
ASSISTANT_TRANSPORT_SYNC_TARGET = 1

# 主车全局状态编号
STATE_IDLE = 0
STATE_SEARCH_OBJECT = 1
STATE_ORBITING = 2
STATE_STOP = 3
STATE_TRANSPORT_OBJECT = 4

# 主车目标编号
TARGET_NONE = 0
TARGET_OBJECT = 1

# 主车视觉事件编号
EVENT_TARGET_FOUND = 6
EVENT_ALIGNED = 7


class MasterStateMachine:
    """维护主车单车寻找与绕行状态"""

    def __init__(
        self,
        hook_arg,
        boot_heading_deg,
        orbit_delta_deg,
        assistant_object_arg=1,
        assistant_transport_arg=1,
        transport_hook_arg=2,
        initial_context_id=0,
    ):
        self.state = STATE_IDLE
        self._hook_arg = int(hook_arg)
        self._boot_heading_deg = float(boot_heading_deg)
        self._orbit_delta_deg = float(orbit_delta_deg)
        self._assistant_object_arg = int(assistant_object_arg)
        self._assistant_transport_arg = int(assistant_transport_arg)
        self._transport_hook_arg = int(transport_hook_arg)
        self._current_context_id = int(initial_context_id) % 256
        self._pending_hook_request = None
        self._pending_assistant_request = None
        self._pending_orbit_command = None
        self._search_started = False
        self._orbit_completed = False
        self._waiting_assistant_idle_ack = False
        self._assistant_object_request_emitted = False
        self._assistant_orbit_request_emitted = False
        self._assistant_transport_request_emitted = False
        self._master_aligned = False
        self._assistant_aligned = False
        self._transport_ready = False

    def step(self, orbit_finished):
        """推进单拍状态机"""

        if not self._search_started and self.state == STATE_IDLE:
            self._search_started = True
            self.state = STATE_SEARCH_OBJECT
            self._current_context_id = (self._current_context_id + 1) % 256
            self._pending_hook_request = {
                "context_id": self._current_context_id,
                "state": STATE_SEARCH_OBJECT,
                "target": TARGET_OBJECT,
                "arg": self._hook_arg,
            }
            return

        if self.state == STATE_ORBITING and orbit_finished:
            self.state = STATE_SEARCH_OBJECT
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
        if self.state != STATE_SEARCH_OBJECT:
            return
        if self._waiting_assistant_idle_ack:
            return
        if int(context_id) != self._current_context_id:
            return
        event = int(event)
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

    def mark_assistant_idle_acknowledged(self):
        """标记辅车 idle 同步已确认"""

        if not self._waiting_assistant_idle_ack:
            return
        self._waiting_assistant_idle_ack = False
        self.state = STATE_ORBITING
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
        self.state = STATE_TRANSPORT_OBJECT

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
        if self._master_aligned:
            return False
        if self._assistant_transport_request_emitted and not self._transport_ready:
            return False
        return True
