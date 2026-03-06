"""Unit tests for filters.lowpass_filter."""

import math

import pytest

from filters.lowpass_filter import LowPassFilter


pytestmark = pytest.mark.unit


def test_lowpass_uses_first_sample_as_initial_state():
    f = LowPassFilter(alpha=0.3, initial=None)
    out = f.update(10.0)
    assert out == 10.0


def test_lowpass_recursive_update():
    f = LowPassFilter(alpha=0.5, initial=0.0)
    out1 = f.update(10.0)
    out2 = f.update(10.0)
    assert math.isclose(out1, 5.0)
    assert math.isclose(out2, 7.5)


def test_lowpass_reset():
    f = LowPassFilter(alpha=0.5, initial=1.0)
    f.reset(None)
    assert f.state is None
