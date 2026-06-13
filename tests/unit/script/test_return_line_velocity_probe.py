"""回库黄线速度调试入口测试.

@file tests/unit/script/test_return_line_velocity_probe.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = PROJECT_ROOT / "src" / "script" / "test" / "return_line_velocity_probe.py"
TEST_ENTRY_PATH = PROJECT_ROOT / "src" / "script" / "test.py"
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) in sys.path:
    sys.path.remove(str(SRC_ROOT))
sys.path.insert(0, str(SRC_ROOT))

from protocol.codec import (  # noqa: E402
    decode_master_vision_task_sync_body,
    encode_velocity_body,
)
from protocol.frame import decode_frame, encode_frame  # noqa: E402
from protocol.topic import (  # noqa: E402
    TOPIC_LOCAL_VISION_VELOCITY,
    TOPIC_MASTER_VISION_TASK_SYNC,
)


def load_probe_module():
    """按文件路径加载回库黄线速度调试脚本."""

    spec = spec_from_file_location("return_line_velocity_probe_test_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_test_entry_module():
    """按文件路径加载板端测试入口."""

    spec = spec_from_file_location("transport_test_entry", TEST_ENTRY_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeUart:
    """记录脚本写入 UART6 的帧, 并提供视觉回传帧."""

    def __init__(self, incoming=b"") -> None:
        self._incoming = bytearray(incoming)
        self.messages = []

    def any(self) -> int:
        return len(self._incoming)

    def read(self, size: int) -> bytes:
        chunk = bytes(self._incoming[:size])
        del self._incoming[:size]
        return chunk

    def write(self, data) -> int:
        payload = bytes(data)
        self.messages.append(payload)
        return len(payload)


def test_probe_is_registered_in_board_test_entry() -> None:
    """板端测试入口可以通过配置名启动回库黄线速度调试."""

    entry = load_test_entry_module()

    assert (
        entry.TEST_MODULES["return_line_velocity_probe"]
        == "script.test.return_line_velocity_probe"
    )


def test_probe_sends_return_line_task_sync_and_prints_visual_velocity() -> None:
    """调试入口只同步回库黄线任务并打印视觉速度."""

    module = load_probe_module()
    velocity_body = encode_velocity_body(1.25, -2.5, 0.0, False)
    uart6 = _FakeUart(
        incoming=encode_frame(0x01, TOPIC_LOCAL_VISION_VELOCITY, 0, velocity_body)
    )
    output_lines = []

    result = module.run_probe_loop(
        uart6=uart6,
        sleep_ms=lambda _delay_ms: None,
        log=lambda line: output_lines.append(line),
        max_rounds=1,
    )

    sync_frame = decode_frame(uart6.messages[0])
    assert sync_frame is not None
    assert sync_frame["topic"] == TOPIC_MASTER_VISION_TASK_SYNC
    sync_body = decode_master_vision_task_sync_body(sync_frame["body"][:5])
    assert sync_body["state"] == module.STATE_RETURN_GARAGE_RETREAT
    assert sync_body["target"] == module.TARGET_EDGE_LINE
    assert sync_body["arg"] == module.MASTER_RETURN_GARAGE_LINE_TASK_CONFIG_ID
    assert result == {"vx": 1.25, "vy": -2.5, "omega": 0.0, "has_omega": False}
    assert output_lines[-1] == (
        "return_line_velocity vx=1.250 vy=-2.500 omega=0.000 has_omega=0"
    )
