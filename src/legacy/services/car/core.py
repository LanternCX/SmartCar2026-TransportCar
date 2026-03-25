"""@brief 搬运车控制单例 facade 公开入口.

@note
- 本模块只保留 `TransportCar` 的稳定公开面和最薄 wiring
- 复杂控制, 视觉和兼容桥接逻辑分别下沉到 mixin / helper 中
- 这里保留的类属性多为运行时 owner 的受控转发入口, 便于 host 测试和脚本层继续复用
"""

import time
import gc

from config.params import VISION_CAMERA_POLL_ORDER
from diagnostics.manager import build_uart3_logger_manager
from hardware.encoders import create_encoders
from hardware.imu import create_imu
from hardware.motors import create_motors
from hardware.uart_bus import create_uart3, create_uart6
from services.car.bootstrap import (
    DEFAULT_MAIN_ROLE_PROFILE,
    DisabledVisionCoordinator,
    VehicleRoleProfile,
    build_role_profile,
    drop_stale_handler_modules,
    dual_camera_polling_enabled,
    ensure_command_handlers,
    ensure_query_handlers,
    get_role_profile,
    get_vehicle_role as get_car_role,
    import_runtime_module,
    init_core_runtime,
    init_optional_features,
    runtime_core_field,
    single_task_state_machine_enabled,
    vision_processing_enabled,
)
from services.car.compat import CompatMixin
from services.car.diag import DiagnosticsMixin
from services.car.loop import LoopMixin
from storage.param_manager import load_gyro_offsets, load_ident_lookup


_VISION_MIXIN_LOADED = False
_PENDING_RUNTIME_TRACES = []

if False:
    VisionProtocol = None
    VisionCoordinator = None
    UartIngressService = None
    build_logger_debug_sink = None


def _get_runtime_mem_free() -> int:
    """@brief 返回当前可用堆内存字节数.

    @return 可用字节数, 若平台不支持则返回 `-1`

    @note
    MicroPython 板端优先使用 `gc.mem_free()`, host 环境缺失该接口时走稳定降级
    """
    mem_free = getattr(gc, "mem_free", None)
    if mem_free is None:
        return -1
    try:
        return int(mem_free())
    except Exception:
        return -1


def _write_runtime_trace(text: str, uart=None) -> None:
    """@brief 向 uart3 写出轻量 trace 文本.

    @param text 已格式化好的 trace 文本
    @param uart 可选串口对象, 为空时先进入待冲刷队列

    @note
    启动早期 `TransportCar` 还未构造完成时, 这里先缓存文本, 避免 probe 自己扰动下一阶段内存曲线
    """
    trace_uart = uart
    if trace_uart is None:
        _PENDING_RUNTIME_TRACES.append(str(text))
        return
    try:
        trace_uart.write(text)
    except Exception:
        return


def _create_trace_uart():
    """@brief 尝试创建临时 trace 串口.

    @return `uart3` 对象, 失败时返回 `None`
    """
    try:
        return create_uart3()
    except Exception:
        return None


def trace_runtime_mem(stage: str, uart=None) -> None:
    """@brief 输出运行时内存曲线埋点.

    @param stage 当前阶段名
    @param uart 可选串口对象
    """
    _write_runtime_trace(
        "TRACE mem stage=%s free=%d\r\n" % (str(stage), _get_runtime_mem_free()),
        uart=uart,
    )


def trace_runtime_failure(stage: str, exc, uart=None) -> None:
    """@brief 输出运行时 trace 失败信息.

    @param stage 当前失败阶段名
    @param exc 捕获到的异常对象
    @param uart 可选串口对象
    """
    exc_type = getattr(getattr(exc, "__class__", None), "__name__", "Exception")
    text = "TRACE fail stage=%s type=%s free=%d\r\n" % (
        str(stage),
        str(exc_type),
        _get_runtime_mem_free(),
    )
    trace_uart = uart if uart is not None else _create_trace_uart()
    if trace_uart is not None:
        flush_pending_runtime_traces(trace_uart)
        _write_runtime_trace(text, uart=trace_uart)
        return
    _PENDING_RUNTIME_TRACES.append(text)


def flush_pending_runtime_traces(uart) -> None:
    """@brief 把早期缓存的 trace 文本冲刷到已就绪串口.

    @param uart 已就绪的 `uart3` 对象
    """
    if uart is None:
        return
    pending = tuple(_PENDING_RUNTIME_TRACES)
    if not pending:
        return
    del _PENDING_RUNTIME_TRACES[:]
    for text in pending:
        _write_runtime_trace(text, uart=uart)


def _get_instance_attr(instance, name: str):
    """@brief 安全读取实例属性, 避免触发兼容回退递归.

    @param instance 目标实例
    @param name 属性名
    @return 属性值, 缺失时返回 `None`
    """
    try:
        return object.__getattribute__(instance, name)
    except AttributeError:
        return None


def _ensure_vision_mixin_loaded() -> None:
    """@brief 按需把 `VisionMixin` 方法装配到 `TransportCar`.

    @note
    这里故意不在模块导入期直接引用 `services.car.vision`
    以降低 `services.car` 首次导入时把整条视觉依赖链一起拉起的峰值
    """
    global _VISION_MIXIN_LOADED
    if _VISION_MIXIN_LOADED:
        return
    from services.car.vision import VisionMixin

    transport_car = globals().get("TransportCar")
    if transport_car is None:
        return
    for name, value in VisionMixin.__dict__.items():
        if name.startswith("__"):
            continue
        setattr(transport_car, name, value)
    _VISION_MIXIN_LOADED = True


def _get_lazy_vision_attr(instance, name: str):
    """@brief 按需解析 `VisionMixin` 属性并返回绑定结果.

    @param instance `TransportCar` 实例
    @param name 待解析的方法名
    @return 绑定到实例的属性或方法

    @note
    仅当首次真正访问视觉相关入口时才触发 mixin 装配,
    避免把视觉方法表注入提前到 `TransportCar.__init__()`
    """
    trace_mem = _get_instance_attr(instance, "trace_runtime_mem")
    trace_fail = _get_instance_attr(instance, "trace_runtime_failure")
    uart = _get_instance_attr(instance, "uart3")
    if callable(trace_mem):
        trace_mem("before_lazy_vision_attr", uart=uart)
    try:
        from services.car.vision import VisionMixin

        value = VisionMixin.__dict__.get(name)
        if value is None:
            raise AttributeError(name)
        _ensure_vision_mixin_loaded()
        if hasattr(value, "__get__"):
            value = value.__get__(instance, instance.__class__)
        elif callable(value):
            callable_value = value

            def bound(*args, **kwargs):
                return callable_value(instance, *args, **kwargs)

            value = bound
        if callable(trace_mem):
            trace_mem("after_lazy_vision_attr", uart=uart)
        return value
    except Exception as exc:
        if callable(trace_fail):
            trace_fail("lazy_vision_attr", exc, uart=uart)
        raise


class TransportCar(CompatMixin, DiagnosticsMixin, LoopMixin):
    """@brief 搬运车核心控制 facade.

    @note
    该类的职责被严格限制为 3 类:
    1. 启动阶段按角色 profile 装配核心 owner
    2. 暴露脚本层和测试层依赖的稳定公开接口
    3. 通过受控转发把运行时 owner 收口为单一入口

    @warning
    不要把控制算法, 视觉状态机或日志细节重新堆回本类
    """

    runtime_core = None
    motion_runtime = None
    command_runtime = None
    vision_service = None
    vision_runtime = None
    vision_coordinator = None
    uart_ingress = None
    _router = None
    _command_session = None
    _diagnostics_facade = None
    _public_module_ref = None
    _vision_debug_sink = None
    _vision_frame_query_cache = None
    _active_vision_target_role = None
    _chassis_state = None
    _chassis_controller = None

    uart3 = runtime_core_field("uart3")
    uart6 = runtime_core_field("uart6")
    error_count = runtime_core_field("error_count")
    last_error_stage = runtime_core_field("last_error_stage")
    _last_error_log_text = runtime_core_field("_last_error_log_text")
    oom_count = runtime_core_field("oom_count")
    last_oom_stage = runtime_core_field("last_oom_stage")
    logger_manager = runtime_core_field("logger_manager")
    log_system = runtime_core_field("log_system")
    log_command = runtime_core_field("log_command")
    log_vision = runtime_core_field("log_vision")
    log_health = runtime_core_field("log_health")
    pit_flag = runtime_core_field("pit_flag")
    tick_count = runtime_core_field("tick_count")
    ticker = runtime_core_field("ticker")
    boot_time_ms = runtime_core_field("boot_time_ms")
    last_time_us = runtime_core_field("last_time_us")
    last_loop_dt_us = runtime_core_field("last_loop_dt_us")
    max_loop_dt_us = runtime_core_field("max_loop_dt_us")
    loop_dt_total_us = runtime_core_field("loop_dt_total_us")
    loop_overrun_count = runtime_core_field("loop_overrun_count")
    last_exception_text = runtime_core_field("last_exception_text")

    @staticmethod
    def trace_runtime_mem(stage: str, uart=None) -> None:
        """@brief 输出运行时内存曲线埋点.

        @param stage 当前阶段名
        @param uart 可选串口对象
        """
        trace_runtime_mem(stage, uart=uart)

    @staticmethod
    def trace_runtime_failure(stage: str, exc, uart=None) -> None:
        """@brief 输出运行时 trace 失败信息.

        @param stage 当前失败阶段名
        @param exc 捕获到的异常对象
        @param uart 可选串口对象
        """
        trace_runtime_failure(stage, exc, uart=uart)

    @staticmethod
    def flush_pending_runtime_traces(uart) -> None:
        """@brief 冲刷早期缓存的 trace 文本."""
        flush_pending_runtime_traces(uart)

    def __init__(self, diagnostic_mode=False, vehicle_role=None):
        """@brief 初始化搬运车运行时入口.

        @param diagnostic_mode 是否启用诊断模式
        @param vehicle_role 显式角色, 为空时回退到 boot 暴露状态
        """

        # `role_profile` 是后续 staged init 的唯一角色判据, 先解析再装配
        self.diagnostic_mode = bool(diagnostic_mode)
        self.role_profile = build_role_profile(vehicle_role)
        self._active_vision_target_role = None
        self._init_core_runtime()
        self._init_optional_features()

    def _init_core_runtime(self):
        """@brief 初始化核心运行时 owner.

        @note
        这里只允许装配串口, 日志, 运动 owner 和最小路由入口
        视觉和命令扩展仍在下一阶段延迟装配, 以控制 import-time 和 init-time 内存占用
        """
        init_core_runtime(self)

    def _init_optional_features(self):
        """@brief 按角色 profile 装配可选功能.

        @note
        该阶段仍要求显式延迟, 不能回退到 import-time 自动发现
        """
        init_optional_features(self)

    def _refresh_vision_target(self, now_ms=None):
        """@brief 按需桥接视觉目标刷新入口."""
        return _get_lazy_vision_attr(self, "_refresh_vision_target")(now_ms)

    def _get_active_position_targets(self):
        """@brief 按需桥接视觉位置目标入口."""
        return _get_lazy_vision_attr(self, "_get_active_position_targets")()

    def _get_vision_resolved_target(self):
        """@brief 按需桥接视觉解析目标入口."""
        return _get_lazy_vision_attr(self, "_get_vision_resolved_target")()

    def _get_active_angle_command(self):
        """@brief 按需桥接视觉角度目标入口."""
        return _get_lazy_vision_attr(self, "_get_active_angle_command")()

    def _get_active_rear_only_mode(self):
        """@brief 按需桥接视觉后轮模式入口."""
        return _get_lazy_vision_attr(self, "_get_active_rear_only_mode")()

    def _drop_stale_handler_modules(self, start_index: int, stop_index=None) -> None:
        """@brief 清理指定区间的 handler 模块缓存.

        @param start_index 起始下标
        @param stop_index 结束下标, 为空时清到末尾
        """
        drop_stale_handler_modules(self, start_index, stop_index)

    def _ensure_query_handlers(self) -> None:
        """@brief 按需装配 query handlers."""
        ensure_query_handlers(self)

    def _ensure_command_handlers(self) -> None:
        """@brief 按需装配 command handlers."""
        ensure_command_handlers(self)

    def mark_tick(self, _tick=None):  # noqa: F841
        """@brief PIT 中断回调仅置位 tick 标志.

        @param _tick 底层 ticker 传入的保留参数

        @note
        中断里不做任何重计算, 所有重逻辑留到主循环 `_handle_tick()`
        """
        self.pit_flag = True

    def set_ticker(self, ticker_obj):
        """@brief 记录 ticker 实例供 stop 阶段复用.

        @param ticker_obj 已启动或待启动的 ticker 对象
        """
        self.ticker = ticker_obj

    @property
    def vehicle_role(self):
        """@brief 返回当前 profile 的车辆角色.

        @return `main` 或 `aux`
        """
        return get_car_role(self)

    @property
    def vision_processing_enabled(self):
        """@brief 返回当前 profile 是否开启视觉处理."""
        return vision_processing_enabled(self)

    @property
    def dual_camera_polling_enabled(self):
        """@brief 返回当前 profile 是否声明双摄轮询能力."""
        return dual_camera_polling_enabled(self)

    @property
    def single_task_state_machine_enabled(self):
        """@brief 返回当前 profile 是否启用唯一任务状态机."""
        return single_task_state_machine_enabled(self)

    def _get_role_profile(self):
        """@brief 返回当前角色 profile.

        @return `VehicleRoleProfile` 或兼容桩对象
        """
        return get_role_profile(self)

    def _build_role_profile(self, vehicle_role):
        """@brief 解析角色并构造 profile.

        @param vehicle_role 外部传入角色
        @return `VehicleRoleProfile`
        """
        return build_role_profile(vehicle_role)

    def _now_ms(self):
        """@brief 返回当前毫秒时间戳.

        @return 毫秒整数时间

        @note
        先尝试 MicroPython 的 `ticks_ms`, host 环境下再回退到 `time.time`
        """
        ticks_ms = getattr(time, "ticks_ms", None)
        if ticks_ms is not None:
            return int(ticks_ms())
        return int(time.time() * 1000)

    def now_ms(self):
        """@brief 返回公开毫秒时间戳接口.

        @return 毫秒整数时间
        """
        return self._now_ms()

    def _now_us(self):
        """@brief 返回当前微秒时间戳.

        @return 微秒整数时间
        """
        ticks_us = getattr(time, "ticks_us", None)
        if ticks_us is not None:
            return int(ticks_us())
        return int(time.time() * 1000000)

    def _ticks_diff_us(self, current_us, previous_us):
        """@brief 计算两个微秒时间戳差值.

        @param current_us 当前时刻
        @param previous_us 上一时刻
        @return 微秒差值
        """
        ticks_diff = getattr(time, "ticks_diff", None)
        if ticks_diff is not None:
            return int(ticks_diff(current_us, previous_us))
        return int(current_us - previous_us)


__all__ = (  # pyright: ignore[reportUnsupportedDunderAll]
    "TransportCar",
    "VehicleRoleProfile",
    "DisabledVisionCoordinator",
    "DEFAULT_MAIN_ROLE_PROFILE",
    "VISION_CAMERA_POLL_ORDER",
    "VisionProtocol",
    "VisionCoordinator",
    "UartIngressService",
    "build_logger_debug_sink",
    "build_uart3_logger_manager",
    "create_uart3",
    "create_uart6",
    "create_imu",
    "create_motors",
    "create_encoders",
    "load_ident_lookup",
    "load_gyro_offsets",
    "import_runtime_module",
    "runtime_core_field",
)


def __getattr__(name: str):
    """@brief 为重型视觉导出提供按需导入入口."""
    if name == "VisionProtocol":
        from vision.protocol import VisionProtocol

        return VisionProtocol
    if name == "VisionCoordinator":
        from vision.coordinator import VisionCoordinator

        return VisionCoordinator
    if name == "build_logger_debug_sink":
        from vision.debug import build_logger_debug_sink

        return build_logger_debug_sink
    if name == "UartIngressService":
        from services.runtime.uart_ingress import UartIngressService

        return UartIngressService
    raise AttributeError(name)
