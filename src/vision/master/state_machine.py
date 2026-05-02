"""主车单车状态机

@file src/vision/master/state_machine.py
"""

from protocol.state import (
    EVENT_TARGET_FOUND,
    STATE_IDLE,
    STATE_ORBITING,
    STATE_SEARCH_OBJECT,
    TARGET_OBJECT,
)


class MasterStateMachine:
    """维护主车单车寻找与绕行状态"""

    def __init__(self, hook_arg, boot_heading_deg, orbit_delta_deg, initial_context_id=0):
        self.state = STATE_IDLE
        self._hook_arg = int(hook_arg)
        self._boot_heading_deg = float(boot_heading_deg)
        self._orbit_delta_deg = float(orbit_delta_deg)
        self._current_context_id = int(initial_context_id) % 256
        self._pending_hook_request = None
        self._pending_orbit_command = None
        self._search_started = False

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

    def handle_event(self, context_id, event, value):
        """消费视觉事件"""

        _ = value
        if self.state != STATE_SEARCH_OBJECT:
            return
        if int(context_id) != self._current_context_id:
            return
        if int(event) != EVENT_TARGET_FOUND:
            return
        self.state = STATE_ORBITING
        self._pending_orbit_command = {
            "target_heading_deg": self._boot_heading_deg + self._orbit_delta_deg,
        }

    def poll_hook_request(self):
        """取出一次性 hook 请求"""

        pending = self._pending_hook_request
        self._pending_hook_request = None
        return pending

    def poll_orbit_command(self):
        """取出一次性绕行命令"""

        pending = self._pending_orbit_command
        self._pending_orbit_command = None
        return pending

    def allows_search_velocity(self):
        """当前状态是否允许主车视觉搜索速度生效"""

        return self.state == STATE_SEARCH_OBJECT
