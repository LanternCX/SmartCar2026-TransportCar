"""命令分词函数单元测试."""

import pytest

from services.commanding.router import tokenize


pytestmark = pytest.mark.unit


def test_tokenize_empty_input_returns_empty_list():
    assert tokenize("") == []
    assert tokenize("   ") == []


def test_tokenize_bare_reset():
    assert tokenize("reset") == [("reset", "1")]


def test_tokenize_parses_key_values_and_ignores_invalid_parts():
    cmd = "vx=10, nope, vy=5, x = 1.2"
    assert tokenize(cmd) == [("vx", "10"), ("vy", "5"), ("x", "1.2")]


def test_tokenize_normalizes_key_case_and_preserves_value_text():
    cmd = "VX= 10 , Print=Hello World"
    assert tokenize(cmd) == [("vx", "10"), ("print", "Hello World")]
