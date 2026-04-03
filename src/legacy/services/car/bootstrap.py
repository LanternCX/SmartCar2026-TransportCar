"""@brief 搬运车 staged init 和轻量 helper 集合.

@note
本模块承载两类职责:
1. 角色 profile 与禁用视觉桩对象
2. `TransportCar` 在 core / optional 两阶段初始化时使用的装配 helper

@warning
这里禁止引入 import-time 自动发现或重型单例初始化
"""

import sys

from machine import Pin

from config.boot_role import get_vehicle_role as get_boot_vehicle_role
from services.commanding.session import CommandSession
from services.runtime.minimal_command_runtime import MinimalCommandRuntime
from services.runtime.motion_runtime import MotionRuntime
from services.runtime.runtime_core import RuntimeCore
from services.runtime.uart_ingress import UartIngressService


class VehicleRoleProfile:
    """@brief 车辆角色 profile.

    @note
    profile 只保存角色驱动的编排开关, 不保存运行时状态
    """

    def __init__(self, vehicle_role: str):
        """@brief 根据角色构造 profile.

        @param vehicle_role 角色字符串
        @warning 非 `main` / `aux` 角色会立即抛错, 避免运行时带病继续
        """
        role = str(vehicle_role).strip().lower()
        if role not in ("main", "aux"):
            raise ValueError("unsupported vehicle role: %s" % role)
        main_enabled = role == "main"
        self.vehicle_role = role
        self.vision_processing_enabled = main_enabled
        self.dual_camera_polling_enabled = main_enabled
        self.single_task_state_machine_enabled = main_enabled


class DisabledVisionCoordinatorResult:
    """@brief 辅车禁用视觉推进时的空 refresh 结果."""

    def __init__(self):
        self.step_result = None
        self.resolved_target = None
        self.released_heading_lock = False


class DisabledVisionCoordinator:
    """@brief 辅车 profile 使用的禁用视觉协调器.

    @note
    辅车仍要消费保留帧, 但不能真的推进视觉状态机, 因此这里返回稳定空结果
    """

    def __init__(self):
        self.protocol = None
        self.state_machine = None
        self.step_result = None
        self.resolved_target = None

    def consume_uart_line(self, _line: str, _source: str, _now_ms: int) -> bool:
        """@brief 消费保留视觉载荷.

        @param _line UART 原始行
        @param _source 串口来源
        @param _now_ms 当前毫秒时间
        @return 是否属于视觉保留载荷
        """
        _ = (_source, _now_ms)
        from vision.protocol import VisionProtocol

        return VisionProtocol.is_reserved_payload(_line)

    def refresh(
        self,
        now_ms: int,
        heading_deg: float,
        odom_x: float,
        odom_y: float,
        command_lock: bool,
        selected_input=None,
    ):
        """@brief 返回禁用模式下的空 refresh 结果.

        @return `DisabledVisionCoordinatorResult`
        """
        _ = (now_ms, heading_deg, odom_x, odom_y, command_lock, selected_input)
        return DisabledVisionCoordinatorResult()

    def clear_runtime(self) -> None:
        """@brief 清理运行时缓存.

        @note 禁用协调器无状态, 这里显式保留空实现以维持统一接口
        """
        return None

    def get_observation(self, now_ms: int):
        """@brief 返回当前观测.

        @param now_ms 当前毫秒时间
        @return 始终返回 `None`
        """
        _ = now_ms
        return None

    def get_state_name(self) -> str:
        """@brief 返回状态名.

        @return 固定 `DISABLED`
        """
        return "DISABLED"

    def build_snapshot(self, now_ms: int):
        """@brief 生成禁用视觉快照.

        @param now_ms 当前毫秒时间
        @return 仅包含空观测和 `DISABLED` 状态的快照
        """
        _ = now_ms
        return {
            "state": "DISABLED",
            "obs_age_ms": None,
            "obs_left": None,
            "obs_top": None,
            "obs_right": None,
            "obs_bottom": None,
            "obs_center_x": None,
            "obs_center_y": None,
            "target_x": None,
            "target_y": None,
            "target_angle": None,
        }

    def get_frame(self, camera_id: str, now_ms: int):
        """@brief 返回指定相机帧.

        @param camera_id 相机标识
        @param now_ms 当前毫秒时间
        @return 始终返回 `None`
        """
        _ = (camera_id, now_ms)
        return None


DEFAULT_MAIN_ROLE_PROFILE = VehicleRoleProfile("main")
EMPTY_CAMERA_POLLS = ()


def get_car_module(instance):
    """@brief 返回实例所属的 `services.car.core` 模块对象.

    @param instance 宿主实例
    @return 模块对象

    @note
    测试会 monkeypatch `services.car` 公开导出, 因此这里必须通过实例模块反查真实公开模块
    """
    module = getattr(instance.__class__, "_public_module_ref", None)
    if module is not None:
        return module
    module_name = instance.__class__.__module__
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    return __import__(module_name, None, None, ("*",), 0)


def import_runtime_module(module_name: str):
    """@brief 以 MicroPython 兼容方式导入运行时模块.

    @param module_name 模块名
    @return 已导入模块对象
    """
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    return __import__(module_name, None, None, ("*",), 0)


def runtime_core_field(field_name: str):
    """@brief 构造转发到 `RuntimeCore` 的兼容属性.

    @param field_name 字段名
    @return property 对象

    @note
    该 helper 允许 `TransportCar` 继续暴露稳定字段名, 同时把真正 owner 下沉到 `RuntimeCore`
    """

    def getter(self):
        core = getattr(self, "runtime_core", None)
        if core is None:
            return self.__dict__.get(field_name)
        return getattr(core, field_name)

    def setter(self, value) -> None:
        core = getattr(self, "runtime_core", None)
        if core is None:
            self.__dict__[field_name] = value
        else:
            setattr(core, field_name, value)

    return property(getter, setter)


def build_role_profile(vehicle_role):
    """@brief 解析显式或 boot 暴露的车辆角色并构造 profile.

    @param vehicle_role 显式角色, 为空时回退到 boot 状态
    @return `VehicleRoleProfile`
    """
    role = get_boot_vehicle_role() if vehicle_role is None else vehicle_role
    return VehicleRoleProfile(role)


def get_role_profile(self):
    """@brief 返回当前角色 profile.

    @return 当前 profile 或主车兼容桩对象
    """
    return getattr(self, "role_profile", DEFAULT_MAIN_ROLE_PROFILE)


def get_vehicle_role(self):
    """@brief 返回当前 profile 的车辆角色.

    @return `main` 或 `aux`
    """
    return get_role_profile(self).vehicle_role


def vision_processing_enabled(self):
    """@brief 返回当前 profile 是否开启视觉处理."""
    return get_role_profile(self).vision_processing_enabled


def dual_camera_polling_enabled(self):
    """@brief 返回当前 profile 是否声明双摄轮询能力."""
    return get_role_profile(self).dual_camera_polling_enabled


def single_task_state_machine_enabled(self):
    """@brief 返回当前 profile 是否启用唯一任务状态机."""
    return get_role_profile(self).single_task_state_machine_enabled


def init_core_runtime(self):
    """@brief 初始化核心运行时 owner.

    @param self `TransportCar` 宿主实例

    @note
    该阶段只装配最低成本 owner: pin, 串口, 日志, motion runtime 和最小路由入口
    视觉与命令扩展保持延迟装配, 防止在最小导入路径上过早膨胀内存占用
    """

    # 先定位公开模块, 这样 host 测试中的 monkeypatch 才能落到当前装配路径
    module = get_car_module(self)

    # 开关和 LED 属于主循环最小依赖, 仍保留在核心阶段创建
    self.led = Pin("C4", Pin.OUT, value=True)
    self.switch2 = Pin("D9", Pin.IN, pull=Pin.PULL_UP_47K)
    self.switch2_init = self.switch2.value()
    self.runtime_core = RuntimeCore(
        vehicle_role=self.role_profile.vehicle_role,
        now_ms=self._now_ms,
        now_us=self._now_us,
        create_uart3_func=module.create_uart3,
        create_uart6_func=module.create_uart6,
        logger_builder=module.build_uart3_logger_manager,
    )
    # 日志和命令会话必须在 motion owner 之前就绪, 这样后续失败路径可观测
    self.log_system.info("System Starting...")
    self._command_session = CommandSession()
    self.motion_runtime = MotionRuntime(
        diagnostic_mode=self.diagnostic_mode,
        uart_writer=self.uart3,
        create_imu_func=module.create_imu,
        create_motors_func=module.create_motors,
        create_encoders_func=module.create_encoders,
        load_ident_lookup_func=module.load_ident_lookup,
        load_gyro_offsets_func=module.load_gyro_offsets,
    )
    self.chassis_state = self.motion_runtime.chassis_state
    self.chassis_controller = self.motion_runtime.chassis_controller
    self._router = import_runtime_module("services.commanding.router").router


def init_optional_features(self):
    """@brief 按当前 profile 装配可选功能和扩展入口.

    @param self `TransportCar` 宿主实例

    @note
    这里仅预建 command lazy loader
    视觉服务和 UART ingress 继续延迟到首次真正使用时再装配, 以降低实例化峰值
    """
    self.command_runtime = MinimalCommandRuntime(
        import_runtime_module=import_runtime_module,
        drop_stale_handler_modules=self._drop_stale_handler_modules,
    )


def drop_stale_handler_modules(self, start_index: int, stop_index=None) -> None:
    """@brief 清理指定区间的 handler 模块缓存.

    @param self `TransportCar` 宿主实例
    @param start_index 起始下标
    @param stop_index 结束下标, 为空时清到末尾
    """
    handlers_module = import_runtime_module("services.commanding.handlers")
    modnames = getattr(handlers_module, "ALL_HANDLER_MODULES", ())
    if stop_index is None:
        stop_index = len(modnames)
    for index in range(start_index, int(stop_index)):
        sys.modules.pop(modnames[index], None)


def ensure_query_handlers(self) -> None:
    """@brief 按需装配 query handlers.

    @param self `TransportCar` 宿主实例
    """

    # 允许 host 测试通过 `__new__` 构造最小实例后再补建 command runtime
    runtime = getattr(self, "command_runtime", None)
    if runtime is None:
        runtime = MinimalCommandRuntime(
            import_runtime_module=import_runtime_module,
            drop_stale_handler_modules=self._drop_stale_handler_modules,
            query_handlers_ready=getattr(self, "_query_handlers_ready", False),
            command_handlers_ready=getattr(self, "_command_handlers_ready", False),
        )
        self.command_runtime = runtime
    runtime.ensure_query_handlers()
    self._query_handlers_ready = bool(getattr(runtime, "query_handlers_ready", True))


def ensure_command_handlers(self) -> None:
    """@brief 按需装配 command handlers.

    @param self `TransportCar` 宿主实例
    """

    # full command 装配和 query 装配共享同一个 runtime owner, 这里必须先兜底补建
    runtime = getattr(self, "command_runtime", None)
    if runtime is None:
        runtime = MinimalCommandRuntime(
            import_runtime_module=import_runtime_module,
            drop_stale_handler_modules=self._drop_stale_handler_modules,
            query_handlers_ready=getattr(self, "_query_handlers_ready", False),
            command_handlers_ready=getattr(self, "_command_handlers_ready", False),
        )
        self.command_runtime = runtime
    runtime.activate_full_commands()
    self._command_handlers_ready = bool(
        getattr(runtime, "command_handlers_ready", True)
    )
