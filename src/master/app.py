"""主车应用编排入口

@file src/master/app.py
"""

from master.decision import decide_from_observation
from master.motion_runtime import MotionRuntime
from master.vision_ingress import VisionIngress


class MasterApp:
    """负责串联视觉输入、决策输出和运行时状态

    @brief 对外提供主车流程的单步推进入口
    """

    def __init__(self, active_uart="uart6", reserved_uarts=("uart8",)):
        # 当前版本只消费启用链路的数据, 预留链路配置仅用于保留装配边界
        self.ingress = VisionIngress(
            active_uart=active_uart,
            reserved_uarts=reserved_uarts,
        )

        # 运行时对象负责保存主车目标和辅车控制序号
        self.motion_runtime = MotionRuntime()

        # 最近一次辅车命令单独缓存, 便于状态查询复用
        self.last_assistant_command = ""

        # 输入无效时直接复用上一轮结果, 避免对外暴露残缺状态
        self.last_result = {
            "selected_target": "idle",
            "phase": "follow_idle",
            "active_uart": active_uart,
            "reserved_uarts": tuple(reserved_uarts),
            "self_target": {"kind": "hold"},
            "assistant_command": "",
        }

    def step(self, observation=None):
        """推进一次主车流程

        @brief 整理输入观测, 生成主车目标和辅车命令
        @param observation 当前观测字典
        @return dict
        """

        # 外部输入先统一整理为内部观测格式
        prepared_observation = self.ingress.prepare_observation(observation)
        if prepared_observation.get("source_status") != "active":
            # 无效输入不生成新结果, 直接沿用上一轮状态
            return dict(self.last_result)

        # 跟随控制使用递增序号, 便于辅车识别重复报文
        prepared_observation["control_seq"] = self.motion_runtime.next_control_seq()

        # 决策层根据观测生成本轮动作结果
        decision = decide_from_observation(prepared_observation)

        # 主车目标写回运行时, 供状态查询复用
        self_target = self.motion_runtime.apply_self_target(decision.self_target)

        # 辅车命令单独缓存, 供状态查询复用
        self.last_assistant_command = decision.assistant_command

        # 对外结果只保留主流程需要的字段
        self.last_result = {
            "selected_target": decision.selected_target,
            "phase": decision.phase,
            "active_uart": prepared_observation.get("active_uart"),
            "reserved_uarts": prepared_observation.get("reserved_uarts"),
            "self_target": self_target,
            "assistant_command": self.last_assistant_command,
        }
        return dict(self.last_result)
