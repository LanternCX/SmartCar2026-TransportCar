"""无线串口发送竞争测试脚本约束.

@file tests/unit/script/test_wireless_contention_test.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = PROJECT_ROOT / "src" / "script" / "test" / "wireless_contention.py"


def load_test_script_module():
    """按文件路径加载无线串口发送竞争测试脚本."""

    spec = spec_from_file_location("wireless_contention_test_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # pyright: ignore[reportAttributeAccessIssue]
    return module


class _CaptureUart:
    """记录测试脚本写入 UART8 的内容."""

    def __init__(self, pending_reads=None) -> None:
        self.writes = []
        self.pending_reads = list(pending_reads or [])

    def write(self, text) -> int:
        self.writes.append(text)
        return len(text)

    def any(self) -> int:
        if not self.pending_reads:
            return 0
        return len(self.pending_reads[0])

    def read(self, length: int):
        if not self.pending_reads:
            return b""
        value = self.pending_reads.pop(0)
        return value[:length]


def test_contention_loop_writes_uart8_every_round(monkeypatch) -> None:
    """发送竞争测试每轮都必须主动向 UART8 连续写入压力包."""

    module = load_test_script_module()
    uart = _CaptureUart()
    delays = []
    collects = []

    module.run_contention_loop(
        uart,
        sleep_ms=lambda delay_ms: delays.append(delay_ms),
        collect=lambda: collects.append("gc"),
        max_rounds=3,
    )

    assert uart.writes == [module.CONTENTION_PACKET] * (
        module.ACTIVE_SENDS_PER_ROUND * 3
    )
    assert delays == [module.SEND_INTERVAL_MS] * 3
    assert collects == ["gc"] * 3


def test_contention_loop_replies_immediately_after_receive(monkeypatch) -> None:
    """主动发送后若收到 UART8 数据, 立即向对车额外连发压力包."""

    module = load_test_script_module()
    uart = _CaptureUart(pending_reads=[b"peer"])

    module.run_contention_loop(
        uart,
        sleep_ms=lambda _delay_ms: None,
        collect=lambda: None,
        max_rounds=1,
    )

    assert uart.writes == [module.CONTENTION_PACKET] * (
        module.ACTIVE_SENDS_PER_ROUND + module.REPLY_SENDS_PER_RECEIVE
    )


def test_contention_packet_uses_large_fixed_payload() -> None:
    """发送竞争测试使用固定小包保持高频竞争."""

    module = load_test_script_module()

    assert module.CONTENTION_PACKET_BYTES > len("\r\n")
    assert len(module.CONTENTION_PACKET) == module.CONTENTION_PACKET_BYTES
    assert module.CONTENTION_PACKET.endswith("\r\n")


def test_main_uses_uart8_bus_factory(monkeypatch) -> None:
    """板端主入口必须使用 UART8 主辅通信链路."""

    module = load_test_script_module()
    uart = _CaptureUart()
    led_toggles = []
    created = []

    monkeypatch.setattr(module, "create_uart8", lambda: created.append("uart8") or uart)
    monkeypatch.setattr(module, "create_memory_pressure", lambda: [])
    monkeypatch.setattr(
        module,
        "create_status_led",
        lambda: type("Led", (), {"toggle": lambda self: led_toggles.append("toggle")})(),
    )
    monkeypatch.setattr(module, "_sleep_ms", lambda _delay_ms: None)
    monkeypatch.setattr(module, "_collect", lambda: None)

    module.main(max_rounds=2)

    assert created == ["uart8"]
    assert uart.writes == [module.CONTENTION_PACKET] * (
        module.ACTIVE_SENDS_PER_ROUND * 2
    )


def test_contention_loop_toggles_status_led_every_500ms(monkeypatch) -> None:
    """发送竞争测试每 500ms 翻转一次 C4 状态灯."""

    module = load_test_script_module()
    uart = _CaptureUart()
    now_values = iter((0, 100, 500, 700, 1000))
    toggles = []

    module.run_contention_loop(
        uart,
        sleep_ms=lambda _delay_ms: None,
        collect=lambda: None,
        now_ms=lambda: next(now_values),
        toggle_status=lambda: toggles.append("toggle"),
        read_memory=lambda: (4096, 2048),
        print_memory=lambda _line: None,
        max_rounds=4,
    )

    assert toggles == ["toggle", "toggle"]


def test_contention_loop_prints_memory_usage_with_status_led(monkeypatch) -> None:
    """状态灯翻转时同步输出内存占用信息."""

    module = load_test_script_module()
    uart = _CaptureUart()
    now_values = iter((0, 100, 500))
    memory_lines = []

    module.run_contention_loop(
        uart,
        toggle_status=lambda: None,
        sleep_ms=lambda _delay_ms: None,
        collect=lambda: None,
        now_ms=lambda: next(now_values),
        read_memory=lambda: (4096, 2048),
        print_memory=lambda line: memory_lines.append(line),
        max_rounds=2,
    )

    assert memory_lines == ["mem_free=4096 mem_alloc=2048"]


def test_create_memory_pressure_keeps_allocations_until_target_free() -> None:
    """低内存模拟会持续保留分配块直到达到目标空闲内存."""

    module = load_test_script_module()
    free_values = iter((10000, 8000, 6000, 4000, 4000))
    allocations = []
    logs = []
    collects = []

    pressure = module.create_memory_pressure(
        target_free_bytes=5000,
        block_bytes=1024,
        read_memory=lambda: (next(free_values), 2048),
        allocate=lambda size: allocations.append(size) or bytearray(size),
        collect=lambda: collects.append("gc"),
        log=lambda text: logs.append(text),
    )

    assert allocations == [1024, 1024, 1024]
    assert collects == ["gc", "gc", "gc", "gc", "gc"]
    assert len(pressure) == 3
    assert logs[-1] == "memory_pressure blocks=3 target_free=5000 mem_free=4000"
