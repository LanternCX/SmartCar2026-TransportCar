"""通信配置

@file src/config/comm.py
@brief 串口端口、波特率、缓冲长度和可靠发送节奏

@details 配置项按使用频率排序, 便于集中查看通信链路参数
"""

# 串口统一波特率
UART_BAUDRATE = 115200
# 固定帧 BODY 槽位长度
TRANSPORT_FRAME_BODY_SIZE = 8
# 固定帧头
TRANSPORT_FRAME_HEAD = 0xA5
# 固定帧总长度
TRANSPORT_FRAME_SIZE = 13
# UDP 发送节奏, 单位毫秒
UDP_SEND_INTERVAL_MS = 20
# TCP 发送与重发节奏, 单位毫秒
TCP_SEND_INTERVAL_MS = 150
# 单次 RX 读取上限
TRANSPORT_RX_READ_LIMIT = 32
# 待确认可靠短包重发间隔, 单位毫秒
RELIABLE_RESEND_INTERVAL_MS = 20
# 辅车向本地视觉重发状态同步的间隔, 单位毫秒
ASSISTANT_LOCAL_VISION_SYNC_RESEND_INTERVAL_MS = 20
# 序号最小值
SEQ_MIN = 0
# 序号最大值
SEQ_MAX = 255
# 序号环长度
SEQ_RING_SIZE = 256
# 判定新序号的半环长度
SEQ_HALF_RING = 128
# UART3 在 machine.UART 中的 REPL 调试端口编号
UART3_PORT_ID = 2
# UART6 在 machine.UART 中的端口编号
UART6_PORT_ID = 5
# UART8 在 machine.UART 中的端口编号
UART8_PORT_ID = 7
