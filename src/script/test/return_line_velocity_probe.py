"""回库黄线速度调试脚本.

@file src/script/test/return_line_velocity_probe.py
@brief 仅同步视觉到主车回库黄线识别上下文, 打印视觉返回速度
"""

from config import vision as vision_params
from protocol.codec import decode_velocity_body, encode_master_vision_hook_sync_body
from protocol.topic import (
    ROLE_MASTER,
    TOPIC_LOCAL_VISION_VELOCITY,
    TOPIC_MASTER_VISION_HOOK_SYNC,
    UART6,
)
from protocol.transport import DELIVERY_DELIVERED, create_transport
from vision.master.state_machine import STATE_RETURN_GARAGE_RETREAT, TARGET_EDGE_LINE


MASTER_RETURN_GARAGE_LINE_HOOK_CONFIG_ID = getattr(
    vision_params,
    "MASTER_RETURN_GARAGE_LINE_HOOK_CONFIG_ID",
)

# 调试脚本固定使用一个独立上下文号, 只用于切换视觉端 hook。
PROBE_CONTEXT_ID = 1
# 调试循环间隔, 单位毫秒。
PROBE_POLL_INTERVAL_MS = 20


class _NullUart:
    """占位 UART, 避免调试脚本初始化无关链路."""

    def any(self) -> int:
        return 0

    def read(self, _size: int) -> bytes:
        return b""

    def write(self, data) -> int:
        return len(data)


def create_uart6():
    """创建本车视觉 UART6 链路."""

    from hardware.uart_bus import create_uart6 as _create_uart6

    return _create_uart6()


def _sleep_ms(delay_ms):
    """按毫秒延时, 兼容 MicroPython 与本地测试环境."""

    import time

    sleep_ms = getattr(time, "sleep_ms", None)
    if sleep_ms is not None:
        sleep_ms(int(delay_ms))
        return
    time.sleep(float(delay_ms) / 1000.0)


def _format_velocity_line(packet):
    """格式化视觉速度输出."""

    return "return_line_velocity vx=%.3f vy=%.3f omega=%.3f has_omega=%d" % (
        float(packet["vx"]),
        float(packet["vy"]),
        float(packet["omega"]),
        1 if bool(packet["has_omega"]) else 0,
    )


def _request_return_line_context(transport):
    """通过正式同步包请求视觉进入回库黄线识别上下文."""

    body = encode_master_vision_hook_sync_body(
        PROBE_CONTEXT_ID,
        STATE_RETURN_GARAGE_RETREAT,
        TARGET_EDGE_LINE,
        MASTER_RETURN_GARAGE_LINE_HOOK_CONFIG_ID,
    )
    return transport.tcp(UART6).write(TOPIC_MASTER_VISION_HOOK_SYNC, body)


def run_probe_loop(
    uart6,
    sleep_ms=_sleep_ms,
    log=print,
    max_rounds=None,
):
    """运行回库黄线速度调试循环.

    @param uart6 本车视觉 UART6 对象
    @param sleep_ms 毫秒延时函数
    @param log 输出函数
    @param max_rounds 最大轮数, None 表示持续运行
    @return 本地测试时返回最后一次收到的速度包
    """

    transport = create_transport(
        ROLE_MASTER,
        uart6=uart6,
        uart8=_NullUart(),
    )
    status = _request_return_line_context(transport)
    log("return_line_probe sync=%s" % status)
    velocity_body = bytearray(7)
    rounds = 0
    last_packet = None
    while max_rounds is None or rounds < int(max_rounds):
        transport.poll_rx()
        delivery = transport.tcp(UART6).delivery(TOPIC_MASTER_VISION_HOOK_SYNC)
        if delivery != DELIVERY_DELIVERED:
            transport.poll_tx()
        if transport.udp(UART6).read(TOPIC_LOCAL_VISION_VELOCITY, velocity_body) == "ok":
            last_packet = decode_velocity_body(velocity_body)
            log(_format_velocity_line(last_packet))
        sleep_ms(PROBE_POLL_INTERVAL_MS)
        rounds += 1
    return last_packet


def main(max_rounds=None):
    """板端测试入口."""

    return run_probe_loop(create_uart6(), max_rounds=max_rounds)


if __name__ == "__main__" and globals().get("__spec__") is None:
    main()
