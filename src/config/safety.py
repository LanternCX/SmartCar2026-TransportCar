"""安全配置

@file src/config/safety.py
@brief 上电阈值、限幅和保护相关参数

@details 配置项按使用频率排序, 便于集中查看保护边界
"""

# 命令输入限幅, 用于限制来自上游的速度指令幅度
V_CMD_MAX = 1e3
# 轮速目标限幅, 单位为 Pulses/tick, 防止给速度环的目标值过大
TARGET_SPEED_MAX = 30.0
# 主车上电允许进入核心脚本的最低电池电压, 单位 V
MASTER_POWER_MIN_VOLTAGE_V = 11.5
# 辅车上电允许进入核心脚本的最低电池电压, 单位 V
ASSISTANT_POWER_MIN_VOLTAGE_V = 3.7
# 上电允许进入核心脚本的默认最低电池电压, 单位 V
POWER_MIN_VOLTAGE_V = ASSISTANT_POWER_MIN_VOLTAGE_V
# PWM 占空比上限, 范围 0 ~ 10000, 对应 0% ~ 100%
MAX_DUTY = 10000
