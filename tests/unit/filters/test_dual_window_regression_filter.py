"""Unit tests for filters.dual_window_regression_filter."""

import pytest

from filters.dual_window_regression_filter import DualWindowRegressionFilter


pytestmark = pytest.mark.unit


def test_update_returns_speed_accel_slope_tuple():
    filt = DualWindowRegressionFilter(tick_ms=10, long_window=5, short_window=3)
    out = filt.update(1.0)
    assert isinstance(out, tuple)
    assert len(out) == 3


def test_filter_tracks_ramp_signal_positive_slope():
    filt = DualWindowRegressionFilter(tick_ms=10, long_window=8, short_window=4)
    for value in [0, 1, 2, 3, 4, 5, 6]:
        fused_speed, accel, slope = filt.update(float(value))
    assert fused_speed > 0.0
    assert accel > 0.0
    assert slope > 0.0


def test_reset_clears_counters():
    filt = DualWindowRegressionFilter()
    filt.update(1.0)
    filt.reset()
    assert filt.sample_idx == 0
    assert filt.count == 0
    assert filt.s_count == 0
