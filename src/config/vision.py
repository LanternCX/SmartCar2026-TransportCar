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
# 辅车搬运阶段使用的视觉配置编号
ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID = 2
# 辅车搬运态对主车 UART8 前馈的缩放系数, 范围 0.0 ~ 1.0
ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE = 0.8
