"""无线串口发送竞争测试脚本

@file src/script/test/wireless_contention.py
@brief 主辅车上电后持续向 UART8 发送短包, 用于观察发送竞争稳定性

@details 两台车同时运行此脚本时, 会在主辅通信链路上形成持续发送竞争
"""


# 发送竞争测试包长度, 固定内容用于减少循环内分配
CONTENTION_PACKET_BYTES = 32
# 发送竞争测试包, 末尾保留换行便于偶发抓包观察
CONTENTION_PACKET = ("C" * (CONTENTION_PACKET_BYTES - 2)) + "\r\n"
# 发送间隔, 单位毫秒; 0 表示尽量连续发送
SEND_INTERVAL_MS = 0
# 每轮主动连续发送包数
ACTIVE_SENDS_PER_ROUND = 4
# 收到数据后立即连续回发包数
REPLY_SENDS_PER_RECEIVE = 4
# 状态灯翻转间隔, 单位毫秒
STATUS_LED_INTERVAL_MS = 500
# 状态灯引脚, 用于现场确认脚本仍在运行
STATUS_LED_PIN = "C4"
# 单轮最多读取字节数, 只用于触发回发, 不解析内容
MAX_RX_BYTES = 64
# 低内存模拟目标空闲字节数
MEMORY_PRESSURE_TARGET_FREE_BYTES = 0
# 低内存模拟每次保留的块大小
MEMORY_PRESSURE_BLOCK_BYTES = 1024


_memory_pressure_blocks = []


def create_uart8():
    """创建主辅通信 UART8 链路.

    @return 已初始化的 UART8 对象
    """

    from hardware.uart_bus import create_uart8 as _create_uart8

    return _create_uart8()


def create_status_led():
    """创建 C4 状态灯.

    @return 已初始化的状态灯对象
    """

    from machine import Pin

    return Pin(STATUS_LED_PIN, Pin.OUT, value=True)


def _sleep_ms(delay_ms):
    """按毫秒延时, 兼容 MicroPython 与本地测试环境.

    @param delay_ms 延时时间, 单位毫秒
    """

    import time

    sleep_ms = getattr(time, "sleep_ms", None)
    if sleep_ms is not None:
        sleep_ms(int(delay_ms))
        return
    time.sleep(float(delay_ms) / 1000.0)


def _collect():
    """触发一次垃圾回收, 降低长时间测试中的内存扰动."""

    import gc

    gc.collect()


def _read_memory_usage():
    """读取当前内存占用信息."""

    import gc

    return (getattr(gc, "mem_free")(), getattr(gc, "mem_alloc")())


def create_memory_pressure(
    target_free_bytes=MEMORY_PRESSURE_TARGET_FREE_BYTES,
    block_bytes=MEMORY_PRESSURE_BLOCK_BYTES,
    read_memory=_read_memory_usage,
    allocate=bytearray,
    collect=_collect,
    log=print,
):
    """保留内存块, 将板端空闲内存压到目标值附近."""

    blocks = []
    while True:
        collect()
        mem_free, _mem_alloc = read_memory()
        if mem_free <= target_free_bytes:
            break
        try:
            blocks.append(allocate(block_bytes))
        except MemoryError:
            break
    collect()
    mem_free, _mem_alloc = read_memory()
    log(
        "memory_pressure blocks=%d target_free=%d mem_free=%s"
        % (len(blocks), target_free_bytes, mem_free)
    )
    return blocks


def _ticks_ms():
    """读取单调毫秒计数, 兼容 MicroPython 与本地测试环境.

    @return 当前毫秒计数
    """

    import time

    ticks_ms = getattr(time, "ticks_ms", None)
    if ticks_ms is not None:
        return ticks_ms()
    return int(time.time() * 1000)


def _ticks_diff(current, previous):
    """计算毫秒计数差值, 兼容 MicroPython 计数回绕.

    @param current 当前毫秒计数
    @param previous 上一次毫秒计数
    @return 间隔毫秒数
    """

    import time

    ticks_diff = getattr(time, "ticks_diff", None)
    if ticks_diff is not None:
        return ticks_diff(current, previous)
    return current - previous


def _read_pending_uart8(uart8):
    """读取 UART8 当前待收数据, 仅用于触发回发."""

    pending = uart8.any()
    if not pending:
        return None
    if pending > MAX_RX_BYTES:
        pending = MAX_RX_BYTES
    return uart8.read(pending)


def _write_contention_packets(uart8, count):
    """连续写入指定数量的竞争测试包."""

    for _ in range(int(count)):
        uart8.write(CONTENTION_PACKET)


def run_contention_loop(
    uart8,
    toggle_status=None,
    sleep_ms=_sleep_ms,
    collect=_collect,
    now_ms=_ticks_ms,
    ticks_diff=_ticks_diff,
    read_memory=_read_memory_usage,
    print_memory=print,
    max_rounds=None,
):
    """持续向 UART8 写入固定短包.

    @param uart8 UART8 串口对象
    @param toggle_status 状态灯翻转函数
    @param sleep_ms 毫秒延时函数
    @param collect 垃圾回收函数
    @param now_ms 毫秒计数读取函数
    @param ticks_diff 毫秒计数差值函数
    @param read_memory 内存占用读取函数
    @param print_memory 内存占用输出函数
    @param max_rounds 最大发送轮数, None 表示无限循环
    """

    rounds = 0
    last_status_ms = now_ms()
    while max_rounds is None or rounds < max_rounds:
        _write_contention_packets(uart8, ACTIVE_SENDS_PER_ROUND)
        received = _read_pending_uart8(uart8)
        if received:
            _write_contention_packets(uart8, REPLY_SENDS_PER_RECEIVE)
        collect()
        current_ms = now_ms()
        if (
            toggle_status is not None
            and ticks_diff(current_ms, last_status_ms) >= STATUS_LED_INTERVAL_MS
        ):
            toggle_status()
            mem_free, mem_alloc = read_memory()
            print_memory("mem_free=%s mem_alloc=%s" % (mem_free, mem_alloc))
            last_status_ms = current_ms
        sleep_ms(SEND_INTERVAL_MS)
        rounds += 1


def main(max_rounds=None):
    """板端测试入口.

    @param max_rounds 最大发送轮数, 本地测试使用; 板端默认无限循环
    """

    uart8 = create_uart8()
    led = create_status_led()
    global _memory_pressure_blocks
    _memory_pressure_blocks = create_memory_pressure()
    run_contention_loop(
        uart8,
        toggle_status=led.toggle,
        sleep_ms=_sleep_ms,
        collect=_collect,
        now_ms=_ticks_ms,
        ticks_diff=_ticks_diff,
        max_rounds=max_rounds,
    )


if __name__ == "__main__" and globals().get("__spec__") is None:
    main()
