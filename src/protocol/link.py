"""
@file src/protocol/link.py
@brief 可靠短包写出辅助
"""

from config import params as _params


def _sleep_reliable_send_delay(sleep_fn):
    """
    @brief 执行可靠短包发送保护延时

    @param sleep_fn 测试注入的毫秒延时函数, 为 None 时使用运行时默认时间模块
    """

    delay_ms = _params.RELIABLE_PACKET_SEND_DELAY_MS
    if sleep_fn is not None:
        sleep_fn(delay_ms)
        return

    import time

    sleep_ms = getattr(time, "sleep_ms", None)
    if sleep_ms is not None:
        sleep_ms(delay_ms)
        return
    time.sleep(delay_ms / 1000.0)


def default_now_ms():
    """
    @brief 读取毫秒时间戳

    @return 当前毫秒时间戳
    """

    import time

    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return int(ticks_ms())
    return int(time.time() * 1000)


def write_reliable_line(uart, line, sleep_fn=None):
    """
    @brief 写出可靠短包, 并在写出前后执行固定延时

    @param uart 目标串口对象
    @param line 不含行尾的短包文本
    @param sleep_fn 测试注入的毫秒延时函数
    @return 是否完整写出整行短包
    """

    _sleep_reliable_send_delay(sleep_fn)
    wrote_all = _write_line(uart, line)
    _sleep_reliable_send_delay(sleep_fn)
    return wrote_all


def write_data_line(uart, line):
    """
    @brief 写出普通数据短包

    @param uart 目标串口对象
    @param line 不含行尾的短包文本
    @return 是否完整写出整行短包
    """

    return _write_line(uart, line)


def _write_line(uart, line):
    """
    @brief 写出一行短包文本

    @param uart 目标串口对象
    @param line 不含行尾的短包文本
    @return 是否完整写出整行短包
    """

    remaining = "%s\r\n" % line
    while remaining:
        written = uart.write(remaining)
        if written is None:
            written = len(remaining)
        written = int(written)
        if written <= 0:
            return False
        remaining = remaining[written:]
    return True


def should_resend(now_ms, last_sent_ms, interval_ms):
    """
    @brief 判断待确认可靠包是否到达重发时间

    @param now_ms 当前毫秒时间戳
    @param last_sent_ms 上次发送毫秒时间戳, None 表示尚未发送
    @param interval_ms 重发间隔, 单位毫秒
    @return 是否应该发送或重发
    """

    if last_sent_ms is None:
        return True
    interval_ms = int(interval_ms)
    if interval_ms <= 0:
        return True
    now_ms = int(now_ms)
    last_sent_ms = int(last_sent_ms)
    if now_ms < last_sent_ms:
        return True
    return now_ms - last_sent_ms >= interval_ms
