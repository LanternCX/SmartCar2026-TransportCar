"""`TransportCar` 控制流测试."""

from math import isclose

from tests.unit.core.runtime_support import DummyMotor, RecordingController, make_minimal_transport_car


class YawPidSpy:
    """记录姿态 PID 输入并返回预设值."""

    def __init__(self, return_value, integral=0.0) -> None:
        self.return_value = return_value
        self.integral = integral
        self.update_calls = []
        self.reset_count = 0

    def update(self, target, current, dt_s):
        self.update_calls.append((target, current, dt_s))
        return self.return_value

    def reset(self) -> None:
        self.reset_count += 1


def test_transport_car_compute_omega_cmd_uses_angle_mode_pid() -> None:
    """角度模式按目标角度输出限幅后的角速度."""
    yaw_pid = YawPidSpy(return_value=99.0, integral=1.5)
    transport_car, car = make_minimal_transport_car(
        last_cmd={"angle": 45.0},
        heading_target=0.0,
        heading_est=10.0,
        yaw_pid=yaw_pid,
        _yaw_rate=0.0,
        yaw_integral=0.0,
    )

    omega_cmd = car._compute_omega_cmd(0.02)

    assert omega_cmd == transport_car.AUTO_OMEGA_MAX
    assert car.heading_target == 45.0
    assert len(yaw_pid.update_calls) == 1
    assert car.yaw_integral == 1.5


def test_transport_car_compute_omega_cmd_keeps_rate_command_and_updates_heading_target() -> None:
    """非零角速度命令继续直通输出, 并把保持目标同步到当前朝向."""
    yaw_pid = YawPidSpy(return_value=0.0, integral=2.0)
    _transport_car, car = make_minimal_transport_car(
        last_cmd={"omega": 3.0},
        heading_target=1.0,
        heading_est=12.0,
        yaw_pid=yaw_pid,
        _yaw_rate=0.0,
        yaw_integral=2.0,
    )

    omega_cmd = car._compute_omega_cmd(0.02)

    assert omega_cmd == 3.0
    assert car.heading_target == 12.0
    assert yaw_pid.reset_count == 1


def test_transport_car_compute_omega_cmd_holds_heading_when_rate_command_is_small() -> None:
    """极小角速度命令继续走保持模式 PID."""
    yaw_pid = YawPidSpy(return_value=4.0, integral=0.7)
    _transport_car, car = make_minimal_transport_car(
        last_cmd={"omega": 0.0},
        heading_target=15.0,
        heading_est=9.0,
        yaw_pid=yaw_pid,
        _yaw_rate=0.0,
        yaw_integral=0.0,
    )

    omega_cmd = car._compute_omega_cmd(0.01)

    assert omega_cmd == 4.0
    assert yaw_pid.update_calls == [(15.0, 9.0, 0.01)]
    assert yaw_pid.reset_count == 0
    assert car.heading_target == 15.0


def test_transport_car_compute_omega_cmd_holds_heading_without_angle_or_rate_command() -> None:
    """没有角度和角速度命令时继续按保持模式输出."""
    yaw_pid = YawPidSpy(return_value=2.5, integral=0.4)
    _transport_car, car = make_minimal_transport_car(
        last_cmd={},
        heading_target=20.0,
        heading_est=18.0,
        yaw_pid=yaw_pid,
        _yaw_rate=0.0,
        yaw_integral=0.0,
    )

    omega_cmd = car._compute_omega_cmd(0.01)

    assert omega_cmd == 2.5
    assert len(yaw_pid.update_calls) == 1
    assert yaw_pid.reset_count == 0
    assert car.heading_target == 20.0


def test_transport_car_compute_planar_targets_switches_between_position_and_velocity_modes() -> None:
    """平面目标在位置模式和速度模式之间按命令切换."""
    class KinematicsSpy:
        def velocity_m_s_to_pulses(self, value, _dt_s) -> float:
            return value

    odometry = type("Odometry", (), {"x": 1.0, "y": 1.0})()
    transport_car, car = make_minimal_transport_car(
        last_cmd={"x": 4.0, "y": 5.0},
        odometry=odometry,
        heading_est=0.0,
        kinematics=KinematicsSpy(),
    )

    pos_targets = car._compute_planar_targets(0.05)
    car.last_cmd = {"vx": 7.0, "vy": -2.0}
    vel_targets = car._compute_planar_targets(0.05)

    expected_scale = transport_car.POS_MAX_SPEED / 5.0
    assert isclose(pos_targets[0], 9.0 * expected_scale)
    assert isclose(pos_targets[1], 12.0 * expected_scale)
    assert vel_targets == (7.0, -2.0)


def test_transport_car_inverse_kinematics_scales_outputs_under_speed_limit() -> None:
    """逆运动学超限时按比例缩放到最大目标速度内."""
    transport_car, car = make_minimal_transport_car()

    vm, vl, vr = car._inverse_kinematics(300.0, 0.0, 0.0)

    assert max(abs(vm), abs(vl), abs(vr)) == transport_car.TARGET_SPEED_MAX
    assert isclose(vm, -transport_car.TARGET_SPEED_MAX)
    assert isclose(vl, transport_car.TARGET_SPEED_MAX / 2.0)
    assert isclose(vr, transport_car.TARGET_SPEED_MAX / 2.0)


def test_transport_car_apply_target_speeds_updates_targets_and_clears_disabled_wheels() -> None:
    """目标分配保持后轮模式约束并清零未启用轮."""
    controllers = {
        "m": RecordingController(return_value=11.0),
        "l": RecordingController(return_value=22.0),
        "r": RecordingController(return_value=33.0),
        "x": RecordingController(return_value=44.0),
    }
    motors = {name: DummyMotor() for name in controllers}
    wheel_states = [
        {
            "name": name,
            "controller": controllers[name],
            "motor": motors[name],
            "filtered_speed": 1.0,
        }
        for name in ("m", "l", "r", "x")
    ]
    _transport_car, car = make_minimal_transport_car(
        rear_only_mode=True,
        target_speeds={"m": 0.0, "l": 0.0, "r": 0.0, "x": 0.0},
        wheel_states=wheel_states,
    )

    car._apply_target_speeds(30.0, 0.0, 0.0, 0.05)

    assert isclose(car.target_speeds["m"], -20.0 / 3.0)
    assert car.target_speeds["l"] == 0.0
    assert car.target_speeds["r"] == 0.0
    assert len(controllers["m"].update_calls) == 1
    assert len(controllers["l"].update_calls) == 1
    assert len(controllers["r"].update_calls) == 1
    assert controllers["x"].reset_count == 1
    assert motors["m"].duties
    assert motors["l"].duties
    assert motors["r"].duties
    assert motors["x"].duties == [0]
