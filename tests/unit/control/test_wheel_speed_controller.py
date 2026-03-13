"""WheelSpeedController 单元测试."""

import pytest

from control.wheel_speed_controller import WheelSpeedController


pytestmark = pytest.mark.unit


class FakeKinematics:
    """测试运动学假对象."""

    def inverse_kinematics(self, vx, vy, omega):
        return (9.0, 12.0, -6.0)


class FakeFilter:
    """记录输入输出的滤波器假对象."""

    def __init__(self, offset):
        self.offset = offset
        self.calls = []

    def update(self, value):
        self.calls.append(value)
        return value + self.offset


class FakeDualFilter:
    """测试双窗滤波假对象."""

    def __init__(self):
        self.calls = []

    def update(self, value):
        self.calls.append(value)
        return (value + 3.0, 0.0, 0.0)


class FakePid:
    """测试速度环假对象."""

    def __init__(self):
        self.calls = []

    def update(self, target, now, dt_s):
        self.calls.append((target, now, dt_s))
        return target - now

    def reset(self):
        self.calls.append(("reset",))


class FakeMotor:
    """测试电机假对象."""

    def __init__(self):
        self.values = []

    def duty(self, value):
        self.values.append(value)


def _build_wheel_state(name, raw_value):
    return {
        "name": name,
        "encoder": type("E", (), {"get": lambda self: raw_value})(),
        "input_lpf": FakeFilter(1.0),
        "diff_filter": FakeFilter(2.0),
        "dual_filter": FakeDualFilter(),
        "output_lpf": FakeFilter(4.0),
        "controller": FakePid(),
        "motor": FakeMotor(),
        "filtered_speed": 0.0,
        "duty": 0.0,
    }


def test_wheel_speed_controller_applies_filter_chain_in_order() -> None:
    controller = WheelSpeedController(kinematics=FakeKinematics())
    wheel_state = _build_wheel_state("m", 5.0)

    controller.update_wheel_speeds([wheel_state])

    assert wheel_state["raw_speed"] == 5.0
    assert wheel_state["input_lpf"].calls == [5.0]
    assert wheel_state["diff_filter"].calls == [6.0]
    assert wheel_state["dual_filter"].calls == [8.0]
    assert wheel_state["output_lpf"].calls == [11.0]
    assert wheel_state["filtered_speed"] == 15.0


def test_wheel_speed_controller_preserves_rear_only_distribution() -> None:
    controller = WheelSpeedController(kinematics=FakeKinematics())
    wheel_states = [
        _build_wheel_state("m", 0.0),
        _build_wheel_state("l", 0.0),
        _build_wheel_state("r", 0.0),
    ]
    target_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
    for state in wheel_states:
        state["filtered_speed"] = 1.0

    controller.apply_target_speeds(
        wheel_states=wheel_states,
        target_speeds=target_speeds,
        target_vx_cmd=1.0,
        target_vy_cmd=2.0,
        omega_cmd=3.0,
        dt_s=0.01,
        rear_only_mode=True,
    )

    assert target_speeds == {"m": 3.0, "l": 0.0, "r": 0.0}
    assert wheel_states[0]["controller"].calls[-1] == (3.0, 1.0, 0.01)
    assert wheel_states[1]["controller"].calls[-1] == (0.0, 1.0, 0.01)
    assert wheel_states[2]["controller"].calls[-1] == (0.0, 1.0, 0.01)
    assert wheel_states[0]["motor"].values[-1] == 2
    assert wheel_states[1]["motor"].values[-1] == -1
    assert wheel_states[2]["motor"].values[-1] == -1


def test_wheel_speed_controller_clamps_omni_distribution() -> None:
    controller = WheelSpeedController(kinematics=FakeKinematics())
    wheel_states = [
        _build_wheel_state("m", 0.0),
        _build_wheel_state("l", 0.0),
        _build_wheel_state("r", 0.0),
    ]
    target_speeds = {"m": 0.0, "l": 0.0, "r": 0.0}
    for state in wheel_states:
        state["filtered_speed"] = 0.0

    controller.apply_target_speeds(
        wheel_states=wheel_states,
        target_speeds=target_speeds,
        target_vx_cmd=1.0,
        target_vy_cmd=2.0,
        omega_cmd=3.0,
        dt_s=0.01,
        rear_only_mode=False,
    )

    assert target_speeds == {"m": 9.0, "l": 12.0, "r": -6.0}
    assert wheel_states[0]["motor"].values[-1] == 9
    assert wheel_states[1]["motor"].values[-1] == 12
    assert wheel_states[2]["motor"].values[-1] == -6


def test_wheel_speed_controller_resets_inactive_wheel() -> None:
    controller = WheelSpeedController(kinematics=FakeKinematics())
    inactive = _build_wheel_state("x", 0.0)
    inactive["duty"] = 99.0

    controller.apply_target_speeds(
        wheel_states=[inactive],
        target_speeds={"x": 5.0},
        target_vx_cmd=0.0,
        target_vy_cmd=0.0,
        omega_cmd=0.0,
        dt_s=0.01,
        rear_only_mode=False,
    )

    assert inactive["controller"].calls[-1] == ("reset",)
    assert inactive["duty"] == 0.0
    assert inactive["motor"].values[-1] == 0
