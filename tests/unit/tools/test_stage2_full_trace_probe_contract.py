"""Stage 2 full trace 探针契约测试."""

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def _read_probe_text() -> str:
    return Path("tools/stage2_full_trace_probe.py").read_text(encoding="utf-8")


def test_stage2_full_trace_probe_reports_required_memory_stages() -> None:
    text = _read_probe_text()

    assert '_print_mem("after_import_transport_car")' in text
    assert '_print_mem("after_core_init")' in text
    assert '_print_mem("after_feature_init")' in text
    assert '_print_mem("runtime_idle")' in text
