"""视觉配置

@file src/config/vision.py
@brief hook 编号、视觉同步和前馈相关参数

@details 配置项按使用频率排序, 便于集中查看视觉联调参数
"""

# 主车搜索下发给视觉 hook 的配置编号
MASTER_SEARCH_HOOK_CONFIG_ID = 1
# 辅车找物体阶段使用的视觉配置编号
ASSISTANT_APPROACH_OBJECT_CONFIG_ID = 1
# 主车搬运阶段使用的视觉配置编号
MASTER_TRANSPORT_HOOK_CONFIG_ID = 2
# 主车搬运结束判定使用的视觉配置编号
MASTER_TRANSPORT_FINISH_HOOK_CONFIG_ID = 3
# 主车绕行阶段使用的视觉配置编号
MASTER_ORBIT_HOOK_CONFIG_ID = 4
# 主车回库黄线阶段使用的视觉配置编号
MASTER_RETURN_GARAGE_LINE_HOOK_CONFIG_ID = 5
# 主车回库色标阶段使用的视觉配置编号
MASTER_RETURN_GARAGE_MARKER_HOOK_CONFIG_ID = 6
# 单场需要完成搬运的物体总数
TRANSPORT_OBJECT_TOTAL_COUNT = 3
# 辅车搬运阶段使用的视觉配置编号
ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID = 2
# 辅车绕行阶段使用的视觉配置编号
ASSISTANT_ORBIT_OBJECT_CONFIG_ID = 3
# 是否应用绕行阶段本车视觉速度修正
ORBIT_VISION_CORRECTION_ENABLED = True
# 辅车搬运态对主车 UART8 前馈的缩放系数, 范围 0.0 ~ 1.0
ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE = 0.8
