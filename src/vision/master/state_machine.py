"""主车单车状态机

@file src/vision/master/state_machine.py
"""

ASSISTANT_IDLE_SYNC_STATE = 0
ASSISTANT_IDLE_SYNC_TARGET = 0
ASSISTANT_OBJECT_SYNC_STATE = 2
ASSISTANT_OBJECT_SYNC_TARGET = 1
ASSISTANT_ORBIT_SYNC_STATE = 3
ASSISTANT_ORBIT_SYNC_TARGET = 1

# 主车全局状态编号
STATE_IDLE = 0
STATE_SEARCH_OBJECT = 1
STATE_ORBITING = 2
STATE_STOP = 3

# 主车目标编号
TARGET_NONE = 0
TARGET_OBJECT = 1

# 主车视觉事件编号
EVENT_TARGET_FOUND = 6


class MasterStateMachine:
    """维护主车单车寻找与绕行状态"""

    def __init__(
        self,
        hook_arg,
        boot_heading_deg,
        orbit_delta_deg,
        assistant_object_arg=1,
        initial_context_id=0,
    ):
        self.state = STATE_IDLE
        self._hook_arg = int(hook_arg)
        self._boot_heading_deg = float(boot_heading_deg)
        self._orbit_delta_deg = float(orbit_delta_deg)
        self._assistant_object_arg = int(assistant_object_arg)
        self._current_context_id = int(initial_context_id) % 256
        self._pending_hook_request = None
        self._pending_assistant_request = None
        self._pending_orbit_command = None
        self._search_started = False
        self._waiting_assistant_idle_ack = False
        self._assistant_object_request_emitted = False
        self._assistant_orbit_request_emitted = False

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
            self.state = STATE_IDLE
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
        if int(event) != EVENT_TARGET_FOUND:
            return
        self._waiting_assistant_idle_ack = True
        self._pending_assistant_request = {
            "kind": "assistant_idle",
            "state": ASSISTANT_IDLE_SYNC_STATE,
            "target": ASSISTANT_IDLE_SYNC_TARGET,
            "arg": 0,
        }

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
        if self.state != STATE_IDLE:
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

        return self.state == STATE_SEARCH_OBJECT and not self._waiting_assistant_idle_ack
