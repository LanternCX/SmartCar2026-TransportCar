"""Unit tests for control.pid_math."""

import math

import pytest

from control.pid_math import clamp, compute_pi_from_id, hardness_factor, reset_pi_state


pytestmark = pytest.mark.unit


class DummyController:
    """Controller fake for reset_pi_state."""

    def __init__(self):
        self.reset_called = False

    def reset(self):
        self.reset_called = True


def test_hardness_factor_known_values():
    assert hardness_factor("soft") == 4.0
    assert hardness_factor("hard") == 1.0
    assert hardness_factor("hard2") == 0.5
    assert hardness_factor("hard3") == 0.05


def test_hardness_factor_default_value():
    assert hardness_factor("unknown") == 2.0


def test_clamp_applies_lower_and_upper_bounds():
    assert clamp(-5, -2, 3) == -2
    assert clamp(9, -2, 3) == 3
    assert clamp(1, -2, 3) == 1


def test_compute_pi_from_id_calculation():
    kp, ki = compute_pi_from_id(
        gain=2.0,
        tau=4.0,
        hardness_name="hard",
        kp_max=10.0,
        ki_max=10.0,
        gain_boost=1.0,
    )
    assert math.isclose(kp, 0.5)
    assert math.isclose(ki, 0.125)


def test_compute_pi_from_id_respects_caps():
    kp, ki = compute_pi_from_id(
        gain=0.2,
        tau=2.0,
        hardness_name="hard3",
        kp_max=1.0,
        ki_max=0.6,
        gain_boost=5.0,
    )
    assert kp == 1.0
    assert ki == 0.6


def test_reset_pi_state_resets_controller_and_duty():
    c1 = DummyController()
    c2 = DummyController()
    states = [
        {"controller": c1, "duty": 10.0},
        {"controller": c2, "duty": -2.0},
        {"duty": 3.0},
    ]
    reset_pi_state(states)
    assert c1.reset_called is True
    assert c2.reset_called is True
    assert all(state["duty"] == 0.0 for state in states)
