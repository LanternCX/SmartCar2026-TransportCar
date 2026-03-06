"""Unit tests for utils.quaternion."""

import math

import pytest

from utils.quaternion import Quaternion


pytestmark = pytest.mark.unit


def test_normalize_keeps_unit_quaternion():
    q = Quaternion(1.0, 0.0, 0.0, 0.0)
    q.normalize()
    assert q.w == 1.0
    assert q.x == 0.0
    assert q.y == 0.0
    assert q.z == 0.0


def test_update_with_zero_gyro_keeps_identity():
    q = Quaternion()
    q.update(0.0, 0.0, 0.0, 0.1)
    assert q.w == pytest.approx(1.0)
    assert q.x == pytest.approx(0.0)
    assert q.y == pytest.approx(0.0)
    assert q.z == pytest.approx(0.0)


def test_from_euler_and_to_euler_yaw():
    q = Quaternion()
    q.from_euler(0.0, 0.0, math.pi / 3.0)
    yaw = q.to_euler_yaw()
    assert yaw == pytest.approx(math.pi / 3.0, rel=1e-6)


def test_rotate_and_rotate_inv_are_inverse():
    q = Quaternion()
    q.from_euler(0.0, 0.0, math.pi / 2.0)
    v = (1.0, 0.0, 0.0)
    rotated = q.rotate(v)
    recovered = q.rotate_inv(rotated)
    assert recovered[0] == pytest.approx(v[0], abs=1e-6)
    assert recovered[1] == pytest.approx(v[1], abs=1e-6)
    assert recovered[2] == pytest.approx(v[2], abs=1e-6)


def test_to_euler_angles_roundtrip():
    roll = 0.2
    pitch = -0.3
    yaw = 0.4
    q = Quaternion()
    q.from_euler(roll, pitch, yaw)
    out_roll, out_pitch, out_yaw = q.to_euler_angles()
    assert out_roll == pytest.approx(roll, rel=1e-6)
    assert out_pitch == pytest.approx(pitch, rel=1e-6)
    assert out_yaw == pytest.approx(yaw, rel=1e-6)
