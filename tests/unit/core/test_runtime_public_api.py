"""`TransportCar` 对外行为测试."""

import importlib.util
import inspect
import math
import sys
from pathlib import Path

import pytest

from config import comm as comm_params
from config import motion as motion_params
from config import safety as safety_params
from config import storage as storage_params
from config import vision as vision_params
from control.kinematics import Odometry, OmniKinematics
from tests.unit.core.runtime_support import (
    CaptureUart,
    DummyMotor,
    DummyTicker,
    RecordingController,
    import_transport_car_module,
    make_minimal_transport_car,
)


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"


class _ResettableWithArgs:
    """记录复位参数的最小桩."""

    def __init__(self) -> None:
        self.reset_calls = []

    def reset(self, *args) -> None:
        self.reset_calls.append(args)


class _Odom:
    """记录里程计复位的最小桩."""

    def __init__(self, x=1.0, y=2.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.reset_count = 0

    def reset(self, x=0.0, y=0.0) -> None:
        self.reset_count += 1
        self.x = float(x)
        self.y = float(y)

    def apply_orbit_displacement(
        self,
        start_x,
        start_y,
        start_heading_deg,
        end_heading_deg,
        radius_m,
    ) -> None:
        odometry = Odometry()
        odometry.apply_orbit_displacement(
            start_x,
            start_y,
            start_heading_deg,
            end_heading_deg,
            radius_m,
        )
        self.x = odometry.x
        self.y = odometry.y

    def apply_forward_displacement(self, distance_m, heading_deg) -> None:
        odometry = Odometry()
        odometry.reset(self.x, self.y)
        odometry.apply_forward_displacement(distance_m, heading_deg)
        self.x = odometry.x
        self.y = odometry.y


class _Quat:
    """最小四元数桩."""

    def __init__(self) -> None:
        self.w = 0.5
        self.x = 1.0
        self.y = 2.0
        self.z = 3.0


class _YawQuat:
    """返回可控偏航角的最小四元数桩."""

    def __init__(self, yaw_rad: float) -> None:
        self.yaw_rad = float(yaw_rad)

    def update(self, _gx, _gy, _gz, _dt_s) -> None:
        return None

    def to_euler_yaw(self) -> float:
        return self.yaw_rad


class _StaticImu:
    """返回静止六轴数据的最小 IMU 桩."""

    def get(self):
        return [0.0] * 6


class _PassFilter:
    """直接返回输入的最小滤波器桩."""

    def update(self, value):
        return value


def _make_control_car(**attrs):
    """构造可执行底盘控制入口的最小对象."""
    transport_car = import_transport_car_module()
    motors = [DummyMotor(), DummyMotor(), DummyMotor()]
    defaults = {
        "control_vx": 0.0,
        "control_vy": 0.0,
        "control_omega": 0.0,
        "control_omega_active": True,
        "control_x": 0.0,
        "control_y": 0.0,
        "control_angle": 0.0,
        "control_x_active": False,
        "control_y_active": False,
        "control_angle_active": False,
        "command_lock": False,
        "command_mode": "none",
        "lock_start_time": 0,
        "orbit_mode": False,
        "orbit_radius_scale": 1.0,
        "_orbit_pose_start": None,
        "_orbit_restore_integration": True,
        "_integrate_position": True,
        "_pending_dx": None,
        "_pending_dy": None,
        "_pending_d_angle": None,
        "_pending_lock": None,
        "heading_est": 0.0,
        "heading_target": 0.0,
        "_yaw_rate": 0.0,
        "yaw_integral": 0.0,
        "yaw_pid": RecordingController(return_value=0.0),
        "gyro_lpf": _ResettableWithArgs(),
        "q_est": _Quat(),
        "last_yaw_rad": 9.0,
        "odometry": _Odom(),
        "kinematics": transport_car.OmniKinematics(),
        "target_speed_m": 0.0,
        "target_speed_l": 0.0,
        "target_speed_r": 0.0,
        "wheel_encoders": (None, None, None),
        "w_mot": (motors[0], motors[1], motors[2]),
        "w_pid": [
            RecordingController(return_value=0.0),
            RecordingController(return_value=0.0),
            RecordingController(return_value=0.0),
        ],
        "w_filt": [0.0, 0.0, 0.0],
        "w_raw": [0.0, 0.0, 0.0],
        "w_duty": [7.0, 8.0, 9.0],
    }
    control_state = attrs.pop("control_state", None)
    target_speeds = attrs.pop("target_speeds", None)
    defaults.update(attrs)
    car = transport_car.TransportCar.__new__(transport_car.TransportCar)
    for key, value in defaults.items():
        setattr(car, key, value)
    if control_state is not None:
        _set_control_fields(car, control_state)
    if target_speeds is not None:
        car.target_speed_m = float(target_speeds.get("m", 0.0))
        car.target_speed_l = float(target_speeds.get("l", 0.0))
        car.target_speed_r = float(target_speeds.get("r", 0.0))
    return transport_car, car


def _set_control_fields(car, state) -> None:
    car.control_vx = float(state.get("vx", 0.0))
    car.control_vy = float(state.get("vy", 0.0))
    car.control_omega_active = "omega" in state
    car.control_omega = float(state.get("omega", 0.0))
    car.control_x_active = "x" in state
    car.control_x = float(state.get("x", 0.0))
    car.control_y_active = "y" in state
    car.control_y = float(state.get("y", 0.0))
    car.control_angle_active = "angle" in state
    car.control_angle = float(state.get("angle", 0.0))


def _load_real_positional_pid_controller():
    module_path = SRC / "control" / "pid_controller.py"
    spec = importlib.util.spec_from_file_location(
        "test_real_pid_controller_module", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load pid controller module")
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop("control.pid_math", None)
    spec.loader.exec_module(module)  # pyright: ignore[reportAttributeAccessIssue]
    return module.PositionalPIDController


@pytest.mark.parametrize(
    "param_name",
    ("MASTER_ORBIT_RADIUS_SCALE", "ASSISTANT_ORBIT_RADIUS_SCALE"),
)
def test_orbit_radius_scale_params_exist_and_are_positive(param_name: str) -> None:
    """主辅车绕行半径倍率参数存在且保持正数语义."""
    module = motion_params
    value = float(getattr(module, param_name))

    assert value > 0.0


def test_runtime_config_params_stay_in_explicit_ranges() -> None:
    """运行时配置中能从代码直接确定范围的参数保持在合法区间."""

    assert int(comm_params.UART_BAUDRATE) > 0
    assert int(comm_params.UART3_PORT_ID) >= 0
    assert int(comm_params.UART6_PORT_ID) >= 0
    assert int(comm_params.UART8_PORT_ID) >= 0
    assert int(comm_params.TRANSPORT_RX_READ_LIMIT) > 0
    assert int(comm_params.RELIABLE_RESEND_INTERVAL_MS) >= 0
    assert int(comm_params.ASSISTANT_LOCAL_VISION_SYNC_RESEND_INTERVAL_MS) >= 0
    seq_min = int(comm_params.SEQ_MIN)
    seq_max = int(comm_params.SEQ_MAX)
    seq_ring_size = int(comm_params.SEQ_RING_SIZE)
    seq_half_ring = int(comm_params.SEQ_HALF_RING)
    assert seq_min >= 0
    assert seq_max > seq_min
    assert seq_ring_size == seq_max - seq_min + 1
    assert seq_half_ring * 2 == seq_ring_size
    assert int(motion_params.TICK_MS) > 0
    assert not hasattr(comm_params, "RELIABLE_PACKET_SEND_DELAY_MS")
    assert 0 <= int(vision_params.MASTER_SEARCH_TASK_CONFIG_ID) <= 255
    assert 0 <= int(vision_params.MASTER_TRANSPORT_TASK_CONFIG_ID) <= 255
    assert 0 <= int(vision_params.MASTER_ORBIT_TASK_CONFIG_ID) <= 255
    assert 0 <= int(vision_params.ASSISTANT_APPROACH_OBJECT_CONFIG_ID) <= 255
    assert 0 <= int(vision_params.ASSISTANT_TRANSPORT_OBJECT_CONFIG_ID) <= 255
    assert 0 <= int(vision_params.ASSISTANT_ORBIT_OBJECT_CONFIG_ID) <= 255
    assert isinstance(vision_params.ORBIT_VISION_CORRECTION_ENABLED, bool)
    assert 0.0 <= float(vision_params.ASSISTANT_TRANSPORT_FEEDFORWARD_SCALE) <= 1.0
    assert float(motion_params.TRANSPORT_CLEAR_STEP_DISTANCE_M) >= 0.0
    assert float(motion_params.TRANSPORT_CLEAR_RETREAT_DISTANCE_M) > 0.0
    assert float(motion_params.TRANSPORT_CLEAR_RETREAT_MAX_SPEED) > 0.0
    assert float(motion_params.TRANSPORT_OBSTACLE_MARGIN_M) >= 0.0
    assert float(motion_params.MOTION_STOP_SPEED_THRESHOLD) >= 0.0
    assert int(motion_params.MOTION_STOP_CONFIRM_TICKS) > 0
    assert float(motion_params.WHEEL_DIAMETER_M) > 0.0
    assert len(motion_params.MASTER_ODOMETRY_DISTANCE_SCALE) == 2
    assert len(motion_params.ASSISTANT_ODOMETRY_DISTANCE_SCALE) == 2
    assert all(float(value) > 0.0 for value in motion_params.MASTER_ODOMETRY_DISTANCE_SCALE)
    assert all(
        float(value) > 0.0 for value in motion_params.ASSISTANT_ODOMETRY_DISTANCE_SCALE
    )
    assert float(motion_params.IN_PLACE_ROTATION_RADIUS_M) > 0.0
    assert len(motion_params.FIELD_SIZE_M) == 2
    assert len(motion_params.MASTER_START_POSITION_M) == 2
    assert len(motion_params.ASSISTANT_START_POSITION_M) == 2
    assert (
        motion_params.MASTER_START_POSITION_M[1]
        == motion_params.ASSISTANT_START_POSITION_M[1]
    )
    assert (
        motion_params.MASTER_START_POSITION_M[0]
        != motion_params.ASSISTANT_START_POSITION_M[0]
    )
    assert float(motion_params.FIELD_SIZE_M[0]) > 0.0
    assert float(motion_params.FIELD_SIZE_M[1]) > 0.0
    assert 0.0 <= float(motion_params.STARTUP_TARGET_Y_M) <= float(
        motion_params.FIELD_SIZE_M[1]
    )
    assert isinstance(motion_params.TRANSPORT_OBJECT_TARGET_EDGE, dict)
    assert motion_params.TRANSPORT_OBJECT_TARGET_EDGE[-1] in {
        "bottom",
        "top",
        "left",
        "right",
    }
    assert float(motion_params.MASTER_TURN_BACK_DELTA_DEG) >= 0.0
    assert 0 < float(safety_params.MAX_DUTY) <= 10000.0
    assert float(safety_params.V_CMD_MAX) > 0.0
    assert float(safety_params.TARGET_SPEED_MAX) > 0.0
    assert float(motion_params.POS_MAX_SPEED) > 0.0
    assert float(motion_params.POS_TOLERANCE) >= 0.0
    assert float(motion_params.ANGLE_TOLERANCE) >= 0.0
    assert float(motion_params.MASTER_TURN_BACK_UNLOCK_TOLERANCE_DEG) >= float(
        motion_params.ANGLE_TOLERANCE
    )
    assert set(motion_params.ACTIVE_WHEELS).issubset({"m", "l", "r"})
    assert 0.0 <= float(motion_params.GYRO_LPF_ALPHA) <= 1.0
    assert float(motion_params.GYRO_SCALE) > 0.0
    assert 0 <= int(motion_params.GYRO_AXIS_Z) <= 5
    assert float(motion_params.YAW_I_MAX) >= 0.0
    assert float(motion_params.AUTO_OMEGA_MAX) >= 0.0
    assert float(motion_params.HEADING_TRANSITION_OMEGA_MAX) >= 0.0
    assert float(motion_params.HOLD_SPEED_EPS) >= 0.0
    assert isinstance(storage_params.IDENT_RESULTS_FILE, str)
    assert isinstance(storage_params.GYRO_OFFSET_FILE, str)


def test_transport_clear_retreat_distance_exceeds_position_tolerance() -> None:
    """主车转身前后退距离应大于位置锁定容差."""

    assert float(motion_params.TRANSPORT_CLEAR_RETREAT_DISTANCE_M) > float(
        motion_params.POS_TOLERANCE
    )


def test_position_control_params_compensate_encoder_count_scale() -> None:
    """位置控制参数保持现场调试后的运动量级."""

    assert float(motion_params.POS_MAX_SPEED) > 0.0
    assert float(motion_params.POS_TOLERANCE) >= 0.0
    assert float(motion_params.TRANSPORT_CLEAR_RETREAT_DISTANCE_M) > float(
        motion_params.POS_TOLERANCE
    )


def test_omni_kinematics_uses_configured_wheel_diameter() -> None:
    """全向轮运动学使用运动配置中的轮径计算脉冲距离."""

    kinematics = OmniKinematics()

    assert kinematics.wheel_diameter == pytest.approx(
        float(motion_params.WHEEL_DIAMETER_M)
    )


def test_omni_kinematics_uses_measured_encoder_counts_per_wheel_rev() -> None:
    """全向轮运动学按编码器实测量级计算轮子单圈计数."""

    kinematics = OmniKinematics()

    assert kinematics.counts_per_rev == pytest.approx(7 * 30)


def test_odometry_applies_axis_scales_in_robot_frame() -> None:
    """里程计先按车体系方向标定速度, 再转换到世界系积分."""

    odometry = Odometry(x_scale=0.5, y_scale=2.0)

    odometry.update(1.0, 1.0, math.pi / 2.0, 1.0)

    assert odometry.x == pytest.approx(2.0)
    assert odometry.y == pytest.approx(-0.5)


@pytest.mark.parametrize(
    ("heading_deg", "expected_x", "expected_y"),
    (
        (0.0, 1.0, 2.5),
        (90.0, 1.5, 2.0),
        (180.0, 1.0, 1.5),
        (-90.0, 0.5, 2.0),
    ),
)
def test_odometry_integrates_forward_velocity_in_clockwise_world_heading(
    heading_deg: float, expected_x: float, expected_y: float
) -> None:
    """轮速里程计按顺时针世界航向积分前进速度。"""
    odometry = Odometry()
    odometry.reset(1.0, 2.0)

    odometry.update(0.0, 0.5, math.radians(heading_deg), 1.0)

    assert odometry.x == pytest.approx(expected_x)
    assert odometry.y == pytest.approx(expected_y)


@pytest.mark.parametrize(
    (
        "start_heading_deg",
        "end_heading_deg",
        "radius_m",
        "expected_x",
        "expected_y",
    ),
    (
        (0.0, 90.0, 0.13, 0.87, 2.13),
        (0.0, -90.0, 0.13, 1.13, 2.13),
        (90.0, 180.0, 0.13, 1.13, 2.13),
        (180.0, 270.0, 0.13, 1.13, 1.87),
        (270.0, 360.0, 0.13, 0.87, 1.87),
        (350.0, 10.0, 0.13, 0.9548515, 2.0),
        (45.0, 405.0, 0.13, 1.0, 2.0),
        (0.0, 90.0, 0.26, 0.74, 2.26),
    ),
)
def test_odometry_applies_orbit_displacement(
    start_heading_deg: float,
    end_heading_deg: float,
    radius_m: float,
    expected_x: float,
    expected_y: float,
) -> None:
    """绕行位移覆盖方向、半径、航向边界和完整一周."""
    odometry = Odometry()

    odometry.apply_orbit_displacement(
        1.0,
        2.0,
        start_heading_deg,
        end_heading_deg,
        radius_m,
    )

    assert odometry.x == pytest.approx(expected_x)
    assert odometry.y == pytest.approx(expected_y)


@pytest.mark.parametrize("radius_m", (0.0, -0.13, float("nan")))
def test_odometry_rejects_non_positive_orbit_radius(radius_m: float) -> None:
    """固定半径绕行拒绝无效半径且保持原位置."""
    odometry = Odometry()
    odometry.reset(1.0, 2.0)

    with pytest.raises(ValueError):
        odometry.apply_orbit_displacement(1.0, 2.0, 0.0, 90.0, radius_m)

    assert odometry.x == pytest.approx(1.0)
    assert odometry.y == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("heading_deg", "expected_x", "expected_y"),
    (
        (0.0, 1.0, 2.5),
        (90.0, 1.5, 2.0),
        (180.0, 1.0, 1.5),
        (-90.0, 0.5, 2.0),
        (30.0, 1.25, 2.4330127),
    ),
)
def test_odometry_applies_forward_displacement(
    heading_deg: float, expected_x: float, expected_y: float
) -> None:
    """里程计按顺时针世界航向应用固定直线位移."""
    odometry = Odometry()
    odometry.reset(1.0, 2.0)

    odometry.apply_forward_displacement(0.5, heading_deg)

    assert odometry.x == pytest.approx(expected_x)
    assert odometry.y == pytest.approx(expected_y)


def test_transport_car_has_no_query_uart_public_api() -> None:
    """运行时对象不暴露通用查询回包串口入口."""
    _transport_car, car = make_minimal_transport_car(
        uart3=CaptureUart(),
        uart8=CaptureUart(),
    )

    assert not hasattr(car, "get_query_uart")


def test_transport_car_stop_stops_ticker_and_zeroes_motors() -> None:
    """停止时关闭 ticker 并清零电机."""
    ticker = DummyTicker()
    motors = [DummyMotor(), DummyMotor()]
    _transport_car, car = make_minimal_transport_car(
        ticker=ticker,
        w_mot=(motors[0], motors[1], DummyMotor()),
        w_pid=[RecordingController(), RecordingController(), RecordingController()],
        w_duty=[0.0, 0.0, 0.0],
    )

    car.stop()

    assert ticker.stop_count == 1
    assert motors[0].duties == [0]
    assert motors[1].duties == [0]


def test_transport_car_builds_health_snapshot() -> None:
    """健康快照直接暴露底盘控制状态."""
    _transport_car, car = make_minimal_transport_car(
        boot_time_ms=200,
        last_exception_text="boom",
        command_lock=True,
        command_mode="locked",
    )
    car._now_ms = lambda: 650

    assert car.build_health_snapshot() == {
        "alive": 1,
        "uptime_ms": 450,
        "last_err": "boom",
        "lock": 1,
        "command_mode": "locked",
    }


def test_transport_car_builds_tick_snapshot() -> None:
    """周期快照继续反映最小统计值."""
    _transport_car, car = make_minimal_transport_car(
        tick_count=4,
        last_loop_dt_us=300,
        max_loop_dt_us=700,
        loop_dt_total_us=2000,
        loop_overrun_count=2,
    )

    assert car.build_tick_snapshot() == {
        "count": 4,
        "last_us": 300,
        "max_us": 700,
        "avg_us": 500,
        "overrun": 2,
    }


def test_transport_car_builds_imu_snapshot() -> None:
    """IMU 快照继续暴露最小姿态事实."""
    _transport_car, car = make_minimal_transport_car(
        imu_data=[1.0],
        heading_est=12.5,
        _yaw_rate=3.0,
        _last_gz_raw=9.0,
    )

    assert car.build_imu_snapshot() == {
        "ok": 1,
        "yaw_deg": 12.5,
        "yaw_rate_dps": 3.0,
        "gz_raw": 9.0,
    }


def test_transport_car_builds_pose_snapshot_from_odometry_and_heading() -> None:
    """位姿快照统一返回世界系位置和当前航向."""
    _transport_car, car = _make_control_car(
        odometry=_Odom(x=0.10, y=-0.50),
        heading_est=12.5,
    )

    assert car.build_pose_snapshot() == {
        "x": 0.10,
        "y": -0.50,
        "angle": 12.5,
    }


def test_transport_car_rebuilds_oblique_pose_from_inset_field_edge() -> None:
    """斜向到边时按推动直线与内缩边界的交点重建位置."""
    _transport_car, car = _make_control_car(
        odometry=_Odom(x=0.50, y=1.00),
        heading_est=33.0,
    )

    car.calibrate_pose_to_field_edge("left", -135.0, 0.08)

    assert car.build_pose_snapshot() == {
        "x": pytest.approx(0.08),
        "y": pytest.approx(0.58),
        "angle": 33.0,
    }


@pytest.mark.parametrize(
    ("vehicle_role", "config_name"),
    (
        ("master", "MASTER_START_POSITION_M"),
        ("assistant", "ASSISTANT_START_POSITION_M"),
    ),
)
def test_transport_car_starts_from_configured_position(
    vehicle_role: str, config_name: str
) -> None:
    """主辅车构造时使用对应发车坐标初始化里程计."""
    transport_car = import_transport_car_module()

    car = transport_car.TransportCar(
        diagnostic_mode=True,
        vehicle_role=vehicle_role,
    )
    expected = getattr(transport_car, config_name)

    assert (car.odometry.x, car.odometry.y) == pytest.approx(expected)


def test_transport_car_selects_odometry_axis_scales_by_role() -> None:
    """底盘构造时按车辆角色选择对应方向的里程计标定比例."""
    transport_car = import_transport_car_module()

    master = transport_car.TransportCar(diagnostic_mode=True, vehicle_role="master")
    assistant = transport_car.TransportCar(diagnostic_mode=True, vehicle_role="assistant")

    assert (master.odometry.x_scale, master.odometry.y_scale) == pytest.approx(
        transport_car.MASTER_ODOMETRY_DISTANCE_SCALE
    )
    assert (assistant.odometry.x_scale, assistant.odometry.y_scale) == pytest.approx(
        transport_car.ASSISTANT_ODOMETRY_DISTANCE_SCALE
    )


def test_transport_car_reports_grayscale_edges_once() -> None:
    """灰度输入只在电平变化时报告对应边沿."""
    transport_car = import_transport_car_module()
    car = transport_car.TransportCar(diagnostic_mode=True)

    car.grayscale._value = 1
    assert car.read_grayscale_edge() == -1
    assert car.read_grayscale_edge() == 0
    car.grayscale._value = 0
    assert car.read_grayscale_edge() == 1


def test_transport_car_builds_encoder_snapshot() -> None:
    """编码器快照继续按轮输出原始值与滤波值."""
    _transport_car, car = make_minimal_transport_car(
        w_raw=[1.0, 2.0, 0.0],
        w_filt=[0.5, 1.5, 0.0],
    )

    assert car.build_encoder_snapshot() == {
        "m_raw": 1.0,
        "m_filt": 0.5,
        "l_raw": 2.0,
        "l_filt": 1.5,
        "r_raw": 0.0,
        "r_filt": 0.0,
    }


def test_transport_car_builds_motor_snapshot() -> None:
    """电机快照继续暴露目标与占空比."""
    _transport_car, car = make_minimal_transport_car(
        w_duty=[11.0, 12.0, 0.0],
        target_speed_m=5.0,
        target_speed_l=6.0,
        target_speed_r=0.0,
    )

    assert car.build_motor_snapshot() == {
        "m_target": 5.0,
        "m_duty": 11.0,
        "l_target": 6.0,
        "l_duty": 12.0,
        "r_target": 0.0,
        "r_duty": 0.0,
    }


def test_transport_car_set_velocity_target_updates_control_state() -> None:
    """结构化速度目标写入后, 底盘控制状态按当前行为保存速度量."""
    _transport_car, car = _make_control_car()
    car.set_velocity_target(1.0, -2.5, 0.5, has_omega=True)

    assert car.control_state == {"vx": 1.0, "vy": -2.5, "omega": 0.5}
    assert car.command_lock is False
    assert car.command_mode == "none"


def test_transport_car_control_targets_use_fixed_fields() -> None:
    """底盘长期控制目标不保存在实例 dict 字段中."""
    _transport_car, car = _make_control_car()

    car.set_velocity_target(1.0, -2.5, 0.5, has_omega=True)

    assert "control_state" not in car.__dict__
    assert car.control_vx == pytest.approx(1.0)
    assert car.control_vy == pytest.approx(-2.5)
    assert car.control_omega == pytest.approx(0.5)


def test_transport_car_velocity_target_keeps_current_speed_limit() -> None:
    """结构化速度目标沿用底盘轮速限幅边界."""
    transport_car, car = _make_control_car()
    limit = float(transport_car.TARGET_SPEED_MAX)

    car.set_velocity_target(limit * 10.0, 0.0, 0.0, has_omega=True)
    car._run_control(0.005)

    assert car.target_speeds == pytest.approx(
        {"m": -limit, "l": limit / 2.0, "r": limit / 2.0}
    )
    assert "target_speeds" not in car.__dict__
    assert car.target_speed_m == pytest.approx(-limit)
    assert car.target_speed_l == pytest.approx(limit / 2.0)
    assert car.target_speed_r == pytest.approx(limit / 2.0)


def test_transport_car_translation_velocity_keeps_angle_target() -> None:
    """平移速度更新不清除当前角度目标."""
    _transport_car, car = _make_control_car(
        control_state={"vx": 0.0, "vy": 0.0, "angle": 45.0},
        command_lock=True,
        command_mode="locked",
    )

    car.set_velocity_target(12.0, -3.0, has_omega=False)

    assert car.control_state["angle"] == 45.0
    assert car.control_state["vx"] == 12.0
    assert car.control_state["vy"] == -3.0
    assert car.command_lock is True
    assert car.command_mode == "locked"


def test_transport_car_explicit_omega_clears_angle_target() -> None:
    """显式角速度更新清除当前角度目标."""
    _transport_car, car = _make_control_car(
        control_state={"vx": 0.0, "vy": 0.0, "angle": 45.0},
        command_lock=True,
        command_mode="locked",
    )

    car.set_velocity_target(12.0, -3.0, 6.0, has_omega=True)

    assert "angle" not in car.control_state
    assert car.control_state == {"vx": 12.0, "vy": -3.0, "omega": 6.0}
    assert car.command_lock is False
    assert car.command_mode == "none"


def test_transport_car_exposes_shared_orbit_entry_without_assistant_naming() -> None:
    """共享底盘公开统一绕行入口, 不暴露 assistant 专属命名."""
    transport_car, car = _make_control_car()
    signature = inspect.signature(transport_car.TransportCar.set_orbit_target)

    assert hasattr(car, "set_orbit_target")
    assert not hasattr(car, "set_assistant_orbit_target")
    assert tuple(signature.parameters) == ("self", "target_angle_deg", "radius_scale")


@pytest.mark.parametrize("radius_scale", (0.0, -1.0))
def test_transport_car_orbit_entry_rejects_non_positive_radius_scale(
    radius_scale: float,
) -> None:
    """统一绕行入口只接受正数半径倍率."""
    _transport_car, car = _make_control_car()

    with pytest.raises(ValueError):
        car.set_orbit_target(90.0, radius_scale)


def test_transport_car_set_orbit_target_enters_locked_shared_orbit_mode() -> None:
    """统一绕行入口只接收目标角度和半径倍率, 不暴露专用 x/y/omega 调参."""
    _transport_car, car = _make_control_car(
        control_state={"vx": 8.0, "vy": -3.0, "omega": 4.0, "x": 1.0, "y": 2.0}
    )

    car.set_orbit_target(90.0, 1.5)

    assert car.orbit_mode is True
    assert car.orbit_radius_scale == pytest.approx(1.5)
    assert car.command_lock is True
    assert car.command_mode == "locked"
    assert car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0, "angle": 90.0}


def test_transport_car_set_heading_target_keeps_non_orbit_translation() -> None:
    """普通角度保持入口在非绕行模式保留平移速度."""
    _transport_car, car = _make_control_car(
        control_state={"vx": 8.0, "vy": -3.0, "omega": 4.0},
        orbit_mode=False,
        orbit_radius_scale=1.5,
    )

    car.set_heading_target(90.0)

    assert car.orbit_mode is False
    assert car.orbit_radius_scale == pytest.approx(_transport_car.MASTER_ORBIT_RADIUS_SCALE)
    assert car.command_lock is True
    assert car.command_mode == "locked"
    assert car.control_state == {"vx": 8.0, "vy": -3.0, "omega": 0.0, "angle": 90.0}


def test_transport_car_set_relative_translation_target_builds_world_target_and_heading_hold() -> None:
    """相对平移入口把车体系位移写成世界系目标并保持当前朝向."""
    _transport_car, car = _make_control_car(
        heading_est=90.0,
        heading_target=12.0,
        odometry=_Odom(x=1.0, y=2.0),
        control_state={"vx": 8.0, "vy": -3.0, "omega": 4.0},
    )

    car.set_relative_translation_target(0.2, -0.1)

    assert car.command_lock is True
    assert car.command_mode == "locked"
    assert car.control_state["vx"] == pytest.approx(0.0)
    assert car.control_state["vy"] == pytest.approx(0.0)
    assert car.control_state["omega"] == pytest.approx(0.0)
    assert car.control_state["angle"] == pytest.approx(90.0)
    assert car.control_state["x"] == pytest.approx(0.9)
    assert car.control_state["y"] == pytest.approx(1.8)
    assert car.heading_target == pytest.approx(90.0)


def test_transport_car_position_control_uses_clockwise_world_heading() -> None:
    """朝向正 X 时，世界系正 X 误差生成车体系前进命令。"""
    _transport_car, car = _make_control_car(
        heading_est=90.0,
        odometry=_Odom(x=0.0, y=0.0),
        control_state={"x": 1.0, "y": 0.0, "angle": 90.0},
        _translation_speed_limit_cmd=None,
    )

    vx_cmd, vy_cmd = car._compute_planar_targets(0.005, 0.0)

    assert vx_cmd == pytest.approx(0.0, abs=1e-9)
    assert vy_cmd > 0.0


def test_transport_car_accepts_world_absolute_translation_target() -> None:
    """绝对平移入口直接写入世界系目标点并保持指定朝向."""
    _transport_car, car = _make_control_car(
        heading_est=37.0,
        odometry=_Odom(x=0.3, y=0.2),
        control_state={"vx": 8.0, "vy": -3.0, "omega": 4.0},
    )

    car.set_translation_target(0.1, 0.45, max_speed_cmd=5)

    assert car.control_state["x"] == pytest.approx(0.1)
    assert car.control_state["y"] == pytest.approx(0.45)
    assert car.control_state["angle"] == pytest.approx(37.0)
    assert car._translation_speed_limit_cmd == pytest.approx(5.0)


def test_transport_car_set_relative_translation_target_accepts_hold_heading_override() -> None:
    """相对平移入口可显式指定保持朝向, 不应总是继承当前角度."""

    _transport_car, car = _make_control_car(
        heading_est=320.0,
        heading_target=270.0,
        odometry=_Odom(x=1.0, y=2.0),
        control_state={"vx": 8.0, "vy": -3.0, "omega": 4.0},
    )

    car.set_relative_translation_target(0.2, 0.0, hold_heading_deg=270.0)

    assert car.control_state["angle"] == pytest.approx(270.0)
    assert car.control_state["x"] == pytest.approx(1.0)
    assert car.control_state["y"] == pytest.approx(2.2)
    assert car.heading_target == pytest.approx(270.0)


def test_transport_car_set_relative_translation_target_accepts_command_speed_limit_override() -> None:
    """相对平移入口可显式指定该段位置控制命令速度上限."""

    _transport_car, car = _make_control_car(
        heading_est=0.0,
        odometry=_Odom(x=0.0, y=0.0),
    )

    car.set_relative_translation_target(0.2, 0.0, max_speed_cmd=0.09)
    vx_cmd, vy_cmd = car._compute_planar_targets(0.005, 0.0)

    assert vx_cmd == pytest.approx(0.09)
    assert vy_cmd == pytest.approx(0.0)


def test_transport_car_position_default_speed_limit_uses_command_units() -> None:
    """默认位置控制速度上限使用编码器命令单位."""

    _transport_car, car = _make_control_car(
        heading_est=0.0,
        odometry=_Odom(x=0.0, y=0.0),
    )

    car.set_relative_translation_target(2.0, 0.0)
    vx_cmd, vy_cmd = car._compute_planar_targets(0.005, 0.0)

    assert vx_cmd == pytest.approx(_transport_car.POS_MAX_SPEED)
    assert vy_cmd == pytest.approx(0.0)


def test_transport_car_clear_retreat_target_generates_negative_y_command() -> None:
    """收尾后退目标应生成车体系 Y 负方向的非零控制命令."""

    _transport_car, car = _make_control_car(
        heading_est=0.0,
        odometry=_Odom(x=0.0, y=0.0),
    )

    car.set_relative_translation_target(
        0.0,
        -float(motion_params.TRANSPORT_CLEAR_RETREAT_DISTANCE_M),
        None,
        float(motion_params.TRANSPORT_CLEAR_RETREAT_MAX_SPEED),
    )
    vx_cmd, vy_cmd = car._compute_planar_targets(
        float(motion_params.TICK_MS) / 1000.0,
        0.0,
    )

    assert vx_cmd == pytest.approx(0.0)
    assert vy_cmd < 0.0
    assert abs(vy_cmd) <= float(motion_params.TRANSPORT_CLEAR_RETREAT_MAX_SPEED)


def test_runtime_config_accepts_separate_orbit_omega_limit() -> None:
    """运行时配置为绕行保留独立角速度限幅参数."""

    assert float(motion_params.ORBIT_AUTO_OMEGA_MAX) >= 0.0


def test_runtime_config_accepts_orbit_angle_confirm_ticks() -> None:
    """运行时配置为绕行保留独立角度到位确认拍数."""

    assert int(motion_params.ORBIT_ANGLE_CONFIRM_TICKS) > 0


def test_runtime_config_accepts_separate_heading_transition_omega_limit() -> None:
    """运行时配置为朝向跳转保留独立角速度限幅参数."""

    assert float(motion_params.HEADING_TRANSITION_OMEGA_MAX) >= 0.0


def test_transport_car_orbit_target_uses_orbit_specific_omega_limit() -> None:
    """绕行角速度限幅与普通角度保持限幅分离."""
    transport_car, car = _make_control_car(
        heading_est=0.0,
        _yaw_rate=0.0,
        yaw_pid=RecordingController(return_value=50.0),
    )

    _set_control_fields(car, {"vx": 0.0, "vy": 0.0, "omega": 0.0, "angle": 90.0})
    car.command_lock = True
    car.command_mode = "locked"
    non_orbit_omega = car._compute_omega_cmd(0.005)

    car.set_orbit_target(90.0, 1.0)
    orbit_omega = car._compute_omega_cmd(0.005)

    assert non_orbit_omega == pytest.approx(float(transport_car.AUTO_OMEGA_MAX))
    assert orbit_omega == pytest.approx(float(transport_car.ORBIT_AUTO_OMEGA_MAX))
    assert orbit_omega < non_orbit_omega


def test_transport_car_heading_transition_target_uses_transition_specific_omega_limit() -> None:
    """朝向跳转角速度限幅与普通朝向保持限幅分离."""
    transport_car, car = _make_control_car(
        heading_est=0.0,
        _yaw_rate=0.0,
        yaw_pid=RecordingController(return_value=50.0),
    )

    _set_control_fields(car, {"vx": 0.0, "vy": 0.0, "omega": 0.0, "angle": 90.0})
    car.command_lock = True
    car.command_mode = "locked"
    non_transition_omega = car._compute_omega_cmd(0.005)

    car.set_heading_transition_target(90.0)
    transition_omega = car._compute_omega_cmd(0.005)

    assert non_transition_omega == pytest.approx(float(transport_car.AUTO_OMEGA_MAX))
    assert transition_omega == pytest.approx(
        float(transport_car.HEADING_TRANSITION_OMEGA_MAX)
    )


def test_transport_car_heading_transition_reverses_after_crossing_target() -> None:
    """朝向跳转跨过目标后应立即给出反向修正, 不能继续同向推动."""

    _transport_car, car = _make_control_car(
        heading_est=91.63,
        _yaw_rate=0.0,
    )
    PositionalPIDController = _load_real_positional_pid_controller()
    car.yaw_pid = PositionalPIDController(
        output_limit=float(motion_params.AUTO_OMEGA_MAX),
        integral_limit=float(motion_params.YAW_I_MAX),
    )
    car.yaw_pid.set_gains(
        float(motion_params.YAW_KP),
        float(motion_params.YAW_KI),
        0.0,
    )

    car.set_heading_transition_target(271.63)
    for _ in range(140):
        car.heading_est = 91.63
        car._compute_omega_cmd(0.005)

    car.heading_est = 320.36

    assert car._compute_omega_cmd(0.005) <= 0.0


def test_transport_car_heading_transition_unlock_accepts_wraparound_small_error() -> None:
    """朝向跳转跨过 0/360 边界时仍应按最短角差判定完成."""

    _transport_car, car = _make_control_car(
        heading_est=359.5,
        heading_target=0.0,
        control_state={"vx": 0.0, "vy": 0.0, "omega": 0.0, "angle": 0.0},
        command_lock=True,
        command_mode="locked",
    )

    car._check_unlock()

    assert car.command_lock is False


def test_transport_car_orbit_target_reuses_legacy_omega_chain_and_scales_radius() -> None:
    """统一绕行保持旧角速度目标行为, 线速度只按半径倍率解算."""
    _transport_car, car = _make_control_car(
        heading_est=10.0,
        yaw_pid=RecordingController(return_value=4.0),
    )
    applied = []

    def _capture(vx_cmd, vy_cmd, omega_cmd, dt_s):
        applied.append((vx_cmd, vy_cmd, omega_cmd, dt_s))

    car._apply_target_speeds = _capture

    car.set_orbit_target(40.0, 0.5)
    car._run_control(0.005)
    first_call = applied[-1]

    car.set_orbit_target(40.0, 2.0)
    car._run_control(0.005)
    second_call = applied[-1]

    assert first_call[2] == pytest.approx(float(_transport_car.ORBIT_AUTO_OMEGA_MAX))
    assert second_call[2] == pytest.approx(float(_transport_car.ORBIT_AUTO_OMEGA_MAX))
    assert first_call[1] == pytest.approx(0.0)
    assert second_call[1] == pytest.approx(0.0)
    assert first_call[0] == pytest.approx(
        -float(_transport_car.ORBIT_AUTO_OMEGA_MAX) * 0.5
    )
    assert second_call[0] == pytest.approx(
        -float(_transport_car.ORBIT_AUTO_OMEGA_MAX) * 2.0
    )
    assert abs(second_call[0]) > abs(first_call[0])


def test_transport_car_orbit_velocity_correction_adds_wheel_targets() -> None:
    """绕行视觉修正先叠加到车体系目标, 再统一解算三轮目标."""

    _transport_car, car = _make_control_car(
        heading_est=10.0,
        yaw_pid=RecordingController(return_value=4.0),
    )

    car.set_orbit_target(40.0, 120.0)
    car.set_orbit_velocity_correction(60.0, 0.0)
    car._run_control(0.005)

    omega_cmd = float(_transport_car.ORBIT_AUTO_OMEGA_MAX)
    wheel_targets = car._inverse_kinematics(-omega_cmd * 120.0 + 60.0, 0.0, omega_cmd)
    expected_targets = {
        "m": wheel_targets[0],
        "l": wheel_targets[1],
        "r": wheel_targets[2],
    }

    assert car.target_speeds == pytest.approx(expected_targets)
    assert car.orbit_mode is True
    assert car.command_lock is True


def test_transport_car_orbit_planar_target_includes_velocity_correction() -> None:
    """绕行平面目标由基础切向速度和视觉平移修正共同组成."""

    _transport_car, car = _make_control_car()

    car.set_orbit_target(40.0, 2.0)
    car.set_orbit_velocity_correction(3.0, -1.0)

    vx_cmd, vy_cmd = car._compute_planar_targets(0.005, 4.0)

    assert vx_cmd == pytest.approx(-5.0)
    assert vy_cmd == pytest.approx(-1.0)


def test_transport_car_leaving_orbit_clears_velocity_correction() -> None:
    """离开绕行模式时清空视觉修正, 避免泄漏成普通平移速度."""

    _transport_car, car = _make_control_car()

    car.set_orbit_target(40.0, 2.0)
    car.set_orbit_velocity_correction(3.0, -2.0)
    car.set_heading_target(40.0)

    vx_cmd, vy_cmd = car._compute_planar_targets(0.005, 0.0)

    assert car.orbit_mode is False
    assert vx_cmd == pytest.approx(0.0)
    assert vy_cmd == pytest.approx(0.0)


def test_transport_car_orbit_target_keeps_left_right_radius_symmetric() -> None:
    """相同半径倍率下, 左右绕行只改变方向, 不改变半径大小."""
    class DirectionalController(RecordingController):
        def update(self, target, measured, dt_s):
            self.update_calls.append((target, measured, dt_s))
            return target - measured

    _transport_car, car = _make_control_car(
        heading_est=0.0,
        yaw_pid=DirectionalController(),
    )

    car.set_orbit_target(90.0, 1.5)
    right_omega = car._compute_omega_cmd(0.005)
    right_vx, right_vy = car._compute_planar_targets(0.005, right_omega)

    car.set_orbit_target(-90.0, 1.5)
    left_omega = car._compute_omega_cmd(0.005)
    left_vx, left_vy = car._compute_planar_targets(0.005, left_omega)

    assert right_omega == pytest.approx(float(_transport_car.ORBIT_AUTO_OMEGA_MAX))
    assert left_omega == pytest.approx(-float(_transport_car.ORBIT_AUTO_OMEGA_MAX))
    assert right_vy == pytest.approx(0.0)
    assert left_vy == pytest.approx(0.0)
    assert abs(right_vx / right_omega) == pytest.approx(abs(left_vx / left_omega))
    assert abs(right_vx / right_omega) == pytest.approx(1.5)


def test_transport_car_orbit_target_runs_through_existing_inverse_kinematics_chain() -> None:
    """统一绕行最终仍走现有底盘控制链和三轮逆运动学."""
    _transport_car, car = _make_control_car(
        heading_est=10.0,
        yaw_pid=RecordingController(return_value=3.0),
    )

    car.set_orbit_target(40.0, 2.0)
    car._run_control(0.005)

    expected_omega = float(_transport_car.ORBIT_AUTO_OMEGA_MAX)
    expected_vx = -expected_omega * 2.0
    expected_targets = {
        "m": (-2.0 / 3.0) * expected_vx + expected_omega / 3.0,
        "l": expected_vx / 3.0 + expected_omega / 3.0,
        "r": expected_vx / 3.0 + expected_omega / 3.0,
    }

    assert car.target_speeds == pytest.approx(expected_targets)
    for controller, target in zip(
        car.w_pid,
        (
            expected_targets["m"],
            expected_targets["l"],
            expected_targets["r"],
        ),
    ):
        assert controller.update_calls == [(target, 0.0, 0.005)]


def test_transport_car_set_orbit_target_unlock_clears_mode_and_output() -> None:
    """统一绕行目标收敛后关闭锁定、清零输出并停止电机."""
    _transport_car, car = _make_control_car(heading_est=0.0, heading_target=0.0)

    car.set_orbit_target(90.0, 1.0)
    car.heading_target = 90.0
    car.heading_est = 90.0

    for _ in range(int(motion_params.ORBIT_ANGLE_CONFIRM_TICKS) - 1):
        car._check_unlock()
        assert car.orbit_mode is True
        assert car.command_lock is True

    car._check_unlock()

    assert car.orbit_mode is False
    assert car.command_lock is False
    assert car.command_mode == "none"
    assert car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert car.w_duty == [0.0, 0.0, 0.0]
    for motor in car.w_mot:
        assert motor.duties == [0]


@pytest.mark.parametrize("radius_scale", (1.0, 4.0))
def test_transport_car_orbit_completion_applies_fixed_radius_pose_once(
    radius_scale: float,
) -> None:
    """绕行完成使用独立物理半径更新位置且不受控制倍率影响."""
    _transport_car, car = _make_control_car(
        heading_est=0.0,
        odometry=Odometry(),
    )
    car.odometry.reset(1.0, 2.0)

    car.set_orbit_target(90.0, radius_scale)
    car.heading_est = 90.0
    for _ in range(int(motion_params.ORBIT_ANGLE_CONFIRM_TICKS)):
        car._check_unlock()

    assert car.odometry.x == pytest.approx(0.87)
    assert car.odometry.y == pytest.approx(2.13)

    car._check_unlock()

    assert car.odometry.x == pytest.approx(0.87)
    assert car.odometry.y == pytest.approx(2.13)


def test_transport_car_position_integration_gate_keeps_heading_updates() -> None:
    """暂停轮速位置积分时继续维护陀螺仪航向."""
    odometry = Odometry()
    _transport_car, car = _make_control_car(
        odometry=odometry,
        imu=_StaticImu(),
        imu_offsets=[0.0] * 6,
        q_est=_YawQuat(0.1),
        last_yaw_rad=0.0,
        gyro_lpf=_PassFilter(),
        w_filt=[0.0, 1.0, -1.0],
        kinematics=OmniKinematics(),
    )

    car.set_position_integration_enabled(False)
    car._update_attitude(0.1)

    assert odometry.x == pytest.approx(0.0)
    assert odometry.y == pytest.approx(0.0)
    assert car.heading_est > 0.0

    car.set_position_integration_enabled(True)
    car._update_attitude(0.1)

    assert abs(odometry.x) + abs(odometry.y) > 0.0


def test_heading_transition_uses_fixed_radius_instead_of_wheel_translation() -> None:
    """主动原地转向按固定半径和航向变化更新位置."""
    odometry = Odometry()
    transport_car, car = _make_control_car(
        odometry=odometry,
        heading_est=0.0,
        heading_transition_mode=True,
        imu=_StaticImu(),
        imu_offsets=[0.0] * 6,
        q_est=_YawQuat(math.pi / 2.0),
        last_yaw_rad=0.0,
        gyro_lpf=_PassFilter(),
        w_filt=[100.0, 0.0, 0.0],
        kinematics=OmniKinematics(),
    )
    odometry.reset(1.0, 2.0)

    car._update_attitude(0.1)

    radius_m = float(transport_car.IN_PLACE_ROTATION_RADIUS_M)
    assert odometry.x == pytest.approx(1.0 - radius_m)
    assert odometry.y == pytest.approx(2.0 + radius_m)


def test_transport_car_orbit_pauses_and_cancellation_restores_wheel_odometry() -> None:
    """绕行自动暂停轮速积分，取消绕行后恢复原积分状态."""
    odometry = Odometry()
    _transport_car, car = _make_control_car(
        odometry=odometry,
        imu=_StaticImu(),
        imu_offsets=[0.0] * 6,
        q_est=_YawQuat(0.1),
        last_yaw_rad=0.0,
        gyro_lpf=_PassFilter(),
        w_filt=[0.0, 1.0, -1.0],
        kinematics=OmniKinematics(),
    )

    car.set_orbit_target(90.0, 1.0)
    car._update_attitude(0.1)

    assert odometry.x == pytest.approx(0.0)
    assert odometry.y == pytest.approx(0.0)
    assert car.heading_est > 0.0

    car.set_heading_target(car.heading_est)
    car._update_attitude(0.1)

    assert abs(odometry.x) + abs(odometry.y) > 0.0


def test_transport_car_applies_forward_pose_distance() -> None:
    """共享底盘把已知直线距离交给里程计 owner 应用."""
    odometry = Odometry()
    odometry.reset(1.0, 2.0)
    _transport_car, car = _make_control_car(odometry=odometry)

    car.apply_forward_pose_distance(0.5, 90.0)

    assert odometry.x == pytest.approx(1.5)
    assert odometry.y == pytest.approx(2.0)


def test_transport_car_orbit_angle_confirm_ticks_must_be_consecutive() -> None:
    """统一绕行目标到位确认只接受连续满足容差的控制拍."""
    _transport_car, car = _make_control_car(heading_est=90.0, heading_target=90.0)

    car.set_orbit_target(90.0, 1.0)

    car._check_unlock()
    car.heading_est = 90.0 + float(motion_params.ANGLE_TOLERANCE) * 2.0
    car._check_unlock()

    car.heading_est = 90.0
    for _ in range(int(motion_params.ORBIT_ANGLE_CONFIRM_TICKS) - 1):
        car._check_unlock()
        assert car.orbit_mode is True
        assert car.command_lock is True

    car._check_unlock()

    assert car.orbit_mode is False
    assert car.command_lock is False


def test_transport_car_translation_target_unlock_clears_pose_targets_and_output() -> None:
    """相对平移目标收敛后清理位置锁定字段并停住."""
    _transport_car, car = _make_control_car(
        heading_est=30.0,
        heading_target=30.0,
        odometry=_Odom(x=1.0, y=2.0),
    )

    car.set_relative_translation_target(0.0, 0.0)
    car._check_unlock()

    assert car.command_lock is False
    assert car.command_mode == "none"
    assert car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}


def test_transport_car_heading_transition_unlock_keeps_target_heading() -> None:
    """朝向跳转解锁后仍应保持原目标角, 不能改写成当前角度."""

    _transport_car, car = _make_control_car(
        heading_est=179.5,
        heading_target=180.0,
        control_state={"vx": 0.0, "vy": 0.0, "omega": 0.0, "angle": 180.0},
        command_lock=True,
        command_mode="locked",
    )

    car._check_unlock()

    assert car.command_lock is False
    assert car.heading_target == pytest.approx(180.0)


def test_transport_car_has_no_legacy_mode_entry() -> None:
    """共享底盘不再暴露旧模式入口."""
    _transport_car, car = _make_control_car()

    assert sorted(
        name for name in dir(car) if name.startswith("set_") and name.endswith("target")
    ) == [
        "set_heading_target",
        "set_heading_transition_target",
        "set_orbit_target",
        "set_relative_translation_target",
        "set_translation_target",
        "set_velocity_target",
    ]


def test_transport_car_reset_control_state_keeps_reset_behavior() -> None:
    """结构化复位入口清空运动状态、姿态状态和锁定状态."""
    _transport_car, car = _make_control_car(
        control_state={"vx": 1.0, "vy": 2.0, "omega": 3.0, "angle": 45.0},
        command_lock=True,
        command_mode="locked",
        _pending_dx=1.0,
        _pending_dy=2.0,
        _pending_d_angle=3.0,
        _pending_lock=True,
        heading_est=12.0,
        heading_target=13.0,
        yaw_integral=7.0,
    )

    car.reset_control_state()

    assert car.odometry.reset_count == 1
    assert car.heading_est == 0.0
    assert car.heading_target == 0.0
    assert car.yaw_integral == 0.0
    assert (car.q_est.w, car.q_est.x, car.q_est.y, car.q_est.z) == (
        1.0,
        0.0,
        0.0,
        0.0,
    )
    assert car.last_yaw_rad == 0.0
    assert car.gyro_lpf.reset_calls == [(0.0,)]
    assert car.control_state == {"vx": 0.0, "vy": 0.0, "omega": 0.0}
    assert car.command_lock is False
    assert car.command_mode == "none"
    assert car._pending_lock is None
    assert car._pending_dx is None
    assert car._pending_dy is None
    assert car._pending_d_angle is None


def test_transport_car_zero_motors_keeps_motor_clear_behavior() -> None:
    """结构化电机清零入口保持三轮占空比清零行为."""
    _transport_car, car = _make_control_car()

    car.zero_motors()

    assert car.w_duty == [0.0, 0.0, 0.0]
    for motor in car.w_mot:
        assert motor.duties == [0]
