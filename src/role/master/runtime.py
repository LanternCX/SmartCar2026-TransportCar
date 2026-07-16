"""主车角色运行入口

@file src/role/master/runtime.py
"""

# from utils.startup_log import log_memory


def create_transport_car():
    """创建主车角色运行时对象

    @return 主车专用运行时实例
    """

    # log_memory("ri0")
    from config.motion import IS_FINAL_ROUND
    from role.master.forward_runtime import MasterForwardRuntime

    # log_memory("ri1")
    obstacle_slots = ()
    if IS_FINAL_ROUND:
        from config.motion import FIELD_SIZE_M
        from config.storage import OBSTACLE_CONFIG_FILE
        from storage.param_manager import load_obstacle_slots

        obstacle_slots = load_obstacle_slots(OBSTACLE_CONFIG_FILE, FIELD_SIZE_M)
    return MasterForwardRuntime(obstacle_slots=obstacle_slots)
