"""通信配置

@file src/config/comm.py
@brief 串口端口、波特率、缓冲长度和可靠发送节奏

@details 配置项按使用频率排序, 便于集中查看通信链路参数
"""

# 串口统一波特率
UART_BAUDRATE = 115200
# 主车运行时 UART3 输入缓冲上限
MASTER_UART3_INPUT_LIMIT = 128
# 主车运行时 UART6 输入缓冲上限
MASTER_UART6_INPUT_LIMIT = 128
# 主车运行时 UART8 输入缓冲上限
MASTER_UART8_INPUT_LIMIT = 128
# 辅车运行时 UART6 与 UART8 输入缓冲上限
ASSISTANT_UART_INPUT_LIMIT = 32
# 待确认可靠短包重发间隔, 单位毫秒
RELIABLE_RESEND_INTERVAL_MS = 20
# 辅车向本地视觉重发状态同步的间隔, 单位毫秒
ASSISTANT_LOCAL_VISION_SYNC_RESEND_INTERVAL_MS = 20
# UART3 在 machine.UART 中的端口编号
UART3_PORT_ID = 2
# UART6 在 machine.UART 中的端口编号
UART6_PORT_ID = 5
# UART8 在 machine.UART 中的端口编号
UART8_PORT_ID = 7
