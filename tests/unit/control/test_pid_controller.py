"""Unit tests for control.pid_controller."""

import math

import pytest

from control.pid_controller import (
    IncrementalPIDController,
    PIDControllerBase,
    PositionalPIDController,
    SpeedPIDController,
)


pytestmark = pytest.mark.unit


def test_pid_base_set_gains_and_clamp():
    pid = PIDControllerBase(output_limit=2.0)
    pid.set_gains(1.0, 2.0, 3.0)
    assert pid.kp == 1.0
    assert pid.ki == 2.0
    assert pid.kd == 3.0
    assert pid.clamp_output(5.0) == 2.0
    assert pid.clamp_output(-5.0) == -2.0


def test_incremental_pid_basic_progression_and_reset():
    pid = IncrementalPIDController(output_limit=100.0)
    pid.set_gains(1.0, 0.0, 0.0)
    out1 = pid.update(target=10.0, now=0.0, dt_s=1.0)
    out2 = pid.update(target=10.0, now=5.0, dt_s=1.0)
    assert math.isclose(out1, 10.0)
    assert math.isclose(out2, 5.0)
    pid.reset()
    assert pid.output == 0.0
    assert pid.prev_error == 0.0
    assert pid.prev_prev_error == 0.0


def test_positional_pid_integral_limit_and_output_clamp():
    pid = PositionalPIDController(output_limit=1.0, integral_limit=0.5)
    pid.set_gains(kp=0.0, ki=10.0, kd=0.0)
    out = pid.update(target=1.0, now=0.0, dt_s=1.0)
    assert out == 1.0
    assert pid.integral == 0.5


def test_speed_pid_feedforward_without_feedback_terms():
    pid = SpeedPIDController(output_limit=100.0, plant_gain=2.0, plant_tau=1.0)
    pid.set_gains(kp=0.0, ki=0.0, ki2=0.0)
    out1 = pid.update(target=10.0, now=0.0, dt_s=1.0)
    out2 = pid.update(target=20.0, now=0.0, dt_s=1.0)
    assert math.isclose(out1, 10.0, rel_tol=1e-9)
    assert math.isclose(out2, 15.0, rel_tol=1e-9)


def test_speed_pid_i2_term_updates_output():
    pid = SpeedPIDController(output_limit=100.0)
    pid.set_gains(kp=0.0, ki=0.0, ki2=0.1)
    out = pid.update(target=3.0, now=0.0, dt_s=1.0)
    assert math.isclose(out, 0.9, rel_tol=1e-9)


def test_speed_pid_dt_zero_is_handled():
    pid = SpeedPIDController(output_limit=100.0)
    pid.set_gains(kp=1.0, ki=1.0, ki2=0.0)
    out = pid.update(target=1.0, now=0.0, dt_s=0.0)
    assert isinstance(out, float)


def test_speed_pid_reset():
    pid = SpeedPIDController(output_limit=100.0)
    pid.set_gains(kp=1.0, ki=0.5, ki2=0.2)
    pid.update(target=2.0, now=0.0, dt_s=1.0)
    pid.reset()
    assert pid.output == 0.0
    assert pid.prev_error == 0.0
    assert pid.prev_target == 0.0
