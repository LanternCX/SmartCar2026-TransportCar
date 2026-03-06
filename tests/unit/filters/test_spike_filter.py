"""Unit tests for filters.spike_filter."""

import pytest

from filters.spike_filter import SpikeMedianFilter


pytestmark = pytest.mark.unit


def test_even_window_becomes_odd_and_at_least_three():
    f = SpikeMedianFilter(window=2)
    assert f.window == 3


def test_spike_filter_returns_median():
    f = SpikeMedianFilter(window=3)
    f.update(1.0)
    f.update(100.0)
    out = f.update(2.0)
    assert out == 2.0


def test_spike_filter_keeps_buffer_size():
    f = SpikeMedianFilter(window=3)
    for value in [1, 2, 3, 4, 5]:
        f.update(value)
    assert len(f.buf) == 3


def test_spike_filter_reset_with_value():
    f = SpikeMedianFilter(window=5)
    f.reset(7)
    assert f.buf == [7, 7, 7, 7, 7]
