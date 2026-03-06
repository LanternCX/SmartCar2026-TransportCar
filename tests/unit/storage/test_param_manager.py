"""Unit tests for storage.param_manager."""

import pytest

from storage.param_manager import load_gyro_offsets, load_ident_lookup


pytestmark = pytest.mark.unit


def test_load_ident_lookup_reads_gain_tau_and_logs(tmp_path):
    path = tmp_path / "ident_params.txt"
    path.write_text("m 1.1 0.2\nl 2.2 0.3\n", encoding="utf-8")

    logs = []
    result = load_ident_lookup(str(path), logger=logs.append)

    assert result == {"m": (1.1, 0.2), "l": (2.2, 0.3)}
    assert len(logs) == 1
    assert logs[0].startswith("Loaded ident params")


def test_load_gyro_offsets_new_format(tmp_path):
    path = tmp_path / "gyro_offset.txt"
    path.write_text("1,2,3,4,5,6", encoding="utf-8")
    result = load_gyro_offsets(str(path))
    assert result == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_load_gyro_offsets_legacy_single_value(tmp_path):
    path = tmp_path / "gyro_offset_legacy.txt"
    path.write_text("7.5", encoding="utf-8")
    result = load_gyro_offsets(str(path))
    assert result == [0.0, 0.0, 0.0, 0.0, 0.0, 7.5]


def test_load_gyro_offsets_invalid_returns_zero_and_logs(tmp_path):
    path = tmp_path / "gyro_offset_invalid.txt"
    path.write_text("bad,data", encoding="utf-8")
    logs = []
    result = load_gyro_offsets(str(path), logger=logs.append)
    assert result == [0.0] * 6
    assert logs == ["Gyro Offset file not found or invalid, using 0.0"]
