"""Unit tests for control.pid_store."""

from pathlib import Path

import pytest

from control.pid_store import (
    load_ident_params,
    load_pid_params,
    save_ident_params,
    save_pid_params,
)


pytestmark = pytest.mark.unit


def test_load_ident_params_missing_file_returns_empty_dict(tmp_path):
    path = tmp_path / "missing.txt"
    assert load_ident_params(str(path)) == {}


def test_save_and_load_ident_params_roundtrip(tmp_path):
    path = tmp_path / "ident.txt"
    states = [
        {"name": "m", "id_gain": 1.2, "id_tau": 0.3},
        {"name": "l", "id_gain": 2.1, "id_tau": 0.4},
        {"name": "r", "id_gain": None, "id_tau": 0.4},
    ]
    save_ident_params(str(path), states)
    loaded = load_ident_params(str(path))
    assert set(loaded.keys()) == {"m", "l"}
    assert loaded["m"]["gain"] == pytest.approx(1.2)
    assert loaded["m"]["tau"] == pytest.approx(0.3)


def test_load_ident_params_skips_invalid_lines(tmp_path):
    path = tmp_path / "ident_invalid.txt"
    path.write_text("m 1.0 0.2\ninvalid\nq bad 0.1\n", encoding="utf-8")
    loaded = load_ident_params(str(path))
    assert loaded == {"m": {"gain": 1.0, "tau": 0.2}}


def test_save_and_load_pid_params_roundtrip(tmp_path):
    path = tmp_path / "pid.txt"
    states = [
        {"name": "m", "id_gain": 1.0, "id_tau": 0.2, "kp": 10.0, "ki": 20.0},
        {"name": "l", "id_gain": 2.0, "id_tau": 0.3, "kp": 11.0, "ki": 21.0},
    ]
    save_pid_params(str(path), states, hardness="hard")
    loaded = load_pid_params(str(path))
    assert loaded["hardness"] == "hard"
    assert loaded["params"]["m"]["kp"] == pytest.approx(10.0)
    assert loaded["params"]["l"]["ki"] == pytest.approx(21.0)
