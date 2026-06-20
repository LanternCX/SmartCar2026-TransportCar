"""编码器计数探针脚本约束.

@file tests/unit/script/test_encoder_count_probe.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = PROJECT_ROOT / "src" / "script" / "test" / "encoder_count_probe.py"


def load_probe_module():
    """按文件路径加载编码器计数探针脚本."""

    spec = spec_from_file_location("encoder_count_probe_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeEncoder:
    """按顺序返回编码器增量."""

    def __init__(self, values) -> None:
        self.values = list(values)

    def get(self):
        if not self.values:
            return 0
        return self.values.pop(0)


def test_encoder_probe_accumulates_counts_once_per_tick_and_prints_report() -> None:
    """编码器探针每个采样周期只累计一次三轮增量并周期输出累计值."""

    module = load_probe_module()
    encoders = {
        "m": _FakeEncoder((1, 2)),
        "l": _FakeEncoder((3, 4)),
        "r": _FakeEncoder((-5, -6)),
    }
    tick_ready_values = [True, True]
    now_values = [0, 0, module.REPORT_INTERVAL_MS]
    reports = []
    clears = []

    module.run_encoder_count_probe(
        encoders,
        tick_ready=lambda: tick_ready_values.pop(0) if tick_ready_values else False,
        clear_tick=lambda: clears.append("clear"),
        now_ms=lambda: now_values.pop(0) if now_values else module.REPORT_INTERVAL_MS,
        sleep_ms=lambda _delay_ms: None,
        collect=lambda: None,
        print_fn=lambda text: reports.append(text),
        max_reports=1,
    )

    assert clears == ["clear", "clear"]
    assert reports == [
        "enc m=2 l=4 r=-6 total_m=3 total_l=7 total_r=-11"
    ]
