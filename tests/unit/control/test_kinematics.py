"""Unit tests for control.kinematics."""

import math

import pytest

from control.kinematics import Odometry, OmniKinematics


pytestmark = pytest.mark.unit


def test_pulses_to_meters_for_one_revolution():
    kin = OmniKinematics()
    meters = kin.pulses_to_m(kin.counts_per_rev)
    assert math.isclose(meters, kin.wheel_circumference, rel_tol=1e-9)


def test_meter_pulse_conversion_roundtrip():
    kin = OmniKinematics()
    value_m = 0.42
    pulses = kin.m_to_pulses(value_m)
    recovered = kin.pulses_to_m(pulses)
    assert math.isclose(recovered, value_m, rel_tol=1e-9)


def test_velocity_conversion_roundtrip():
    kin = OmniKinematics()
    speed = 1.25
    dt = 0.01
    pulses_per_tick = kin.velocity_m_s_to_pulses(speed, dt)
    recovered = kin.velocity_pulses_to_m_s(pulses_per_tick, dt)
    assert math.isclose(recovered, speed, rel_tol=1e-9)


def test_inverse_then_forward_kinematics_recovers_input():
    kin = OmniKinematics()
    vx, vy, omega = 1.2, -0.8, 0.5
    vm, vl, vr = kin.inverse_kinematics(vx, vy, omega)
    out_vx, out_vy, out_omega = kin.forward_kinematics(vm, vl, vr)
    assert math.isclose(out_vx, vx, rel_tol=1e-9)
    assert math.isclose(out_vy, vy, rel_tol=1e-9)
    assert math.isclose(out_omega, omega, rel_tol=1e-9)


def test_odometry_update_theta_zero():
    odom = Odometry()
    odom.update(vx_robot=1.0, vy_robot=0.5, theta_rad=0.0, dt=2.0)
    assert math.isclose(odom.x, 2.0)
    assert math.isclose(odom.y, 1.0)


def test_odometry_update_with_rotation():
    odom = Odometry()
    odom.update(vx_robot=1.0, vy_robot=0.0, theta_rad=math.pi / 2.0, dt=1.0)
    assert abs(odom.x) < 1e-9
    assert math.isclose(odom.y, 1.0, rel_tol=1e-9)


def test_odometry_reset():
    odom = Odometry()
    odom.x = 3.0
    odom.y = -4.0
    odom.reset(0.2, 0.3)
    assert odom.x == 0.2
    assert odom.y == 0.3
