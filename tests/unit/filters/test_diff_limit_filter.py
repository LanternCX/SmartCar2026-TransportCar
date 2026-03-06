"""Unit tests for filters.diff_limit_filter."""

import pytest

from filters.diff_limit_filter import DiffLimitFilter


pytestmark = pytest.mark.unit


def test_first_value_passes_through():
    f = DiffLimitFilter(max_delta=2.0)
    assert f.update(10.0) == 10.0


def test_diff_limit_clamps_large_jump():
    f = DiffLimitFilter(max_delta=1.5)
    f.update(0.0)
    assert f.update(10.0) == 1.5
    assert f.update(-10.0) == 0.0


def test_diff_limit_no_limit_when_non_positive_delta():
    f = DiffLimitFilter(max_delta=0.0)
    f.update(1.0)
    assert f.update(100.0) == 100.0


def test_diff_limit_reset():
    f = DiffLimitFilter(max_delta=2.0)
    f.update(3.0)
    f.reset(5.0)
    assert f.prev == 5.0
