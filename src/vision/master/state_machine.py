"""
@file src/vision/master/state_machine.py
@brief 主车搜索状态机纯逻辑
"""

IDLE = 0
SEARCH_OBJECT = 1
OBJECT_FOUND = 2

TARGET_NONE = 0
TARGET_OBJECT = 1

EVENT_TARGET_FOUND = 6


class MasterSearchStateMachine:
    """
    @brief 维护主车物体搜索状态

    @details 负责搜索上下文、可靠序号和事件触发
    """

    def __init__(self, hook_config_id) -> None:
        """
        @brief 初始化主车搜索状态机

        @param hook_config_id 下发给视觉端的 hook 配置编号
        """

        self.state = IDLE
        self.hook_config_id = int(hook_config_id)
        self.context_id = 0
        self.reliable_seq = 0
        self.search_sync = None
        self.transition_count = 0
        self.last_event = None

    def enter_search(self):
        """
        @brief 进入搜索态并创建 hook 同步包字段

        @return hook 同步字段字典, 已找到物体时返回 None
        """

        if self.state == SEARCH_OBJECT:
            return self.search_sync
        if self.state == OBJECT_FOUND:
            return None
        self.state = SEARCH_OBJECT
        self.context_id = (self.context_id + 1) % 256
        self.reliable_seq = (self.reliable_seq + 1) % 256
        self.search_sync = {
            "reliable_seq": self.reliable_seq,
            "context_id": self.context_id,
            "state": SEARCH_OBJECT,
            "target": TARGET_OBJECT,
            "arg": self.hook_config_id,
        }
        return self.search_sync

    def handle_event(self, packet):
        """
        @brief 处理视觉事件并返回是否发生状态迁移

        @param packet 解析后的视觉事件短包
        @return 是否由本次事件触发状态迁移
        """

        if self.state != SEARCH_OBJECT:
            return False
        if int(packet["context_id"]) != int(self.context_id):
            return False
        self.last_event = packet
        if int(packet["event"]) != EVENT_TARGET_FOUND:
            return False

        self.state = OBJECT_FOUND
        self.transition_count += 1
        return True
