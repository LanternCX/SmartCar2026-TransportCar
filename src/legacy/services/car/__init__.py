"""搬运车服务分包公开入口."""

import sys

from services.car.bootstrap import (
    DEFAULT_MAIN_ROLE_PROFILE,
    DisabledVisionCoordinator,
    EMPTY_CAMERA_POLLS,
    VehicleRoleProfile,
    import_runtime_module,
    runtime_core_field,
)
from services.car.core import TransportCar, time


_VehicleRoleProfile = VehicleRoleProfile
_DisabledVisionCoordinator = DisabledVisionCoordinator
_DEFAULT_MAIN_ROLE_PROFILE = DEFAULT_MAIN_ROLE_PROFILE
_EMPTY_CAMERA_POLLS = EMPTY_CAMERA_POLLS
_import_runtime_module = import_runtime_module
_runtime_core_field = runtime_core_field
TransportCar._public_module_ref = sys.modules[__name__]  # pyright: ignore[reportAttributeAccessIssue]
TransportCar.__module__ = __name__

if False:
    UartIngressService = None
    VISION_CAMERA_POLL_ORDER = None
    VisionCoordinator = None
    VisionProtocol = None
    build_logger_debug_sink = None
    build_uart3_logger_manager = None
    create_uart3 = None
    create_uart6 = None
    create_imu = None
    create_motors = None
    create_encoders = None
    load_ident_lookup = None
    load_gyro_offsets = None


__all__ = (  # pyright: ignore[reportUnsupportedDunderAll]
    "TransportCar",
    "UartIngressService",
    "VISION_CAMERA_POLL_ORDER",
    "VisionCoordinator",
    "VisionProtocol",
    "build_logger_debug_sink",
    "build_uart3_logger_manager",
    "create_uart3",
    "create_uart6",
    "create_imu",
    "create_motors",
    "create_encoders",
    "load_ident_lookup",
    "load_gyro_offsets",
    "time",
    "_VehicleRoleProfile",
    "_DisabledVisionCoordinator",
    "_DEFAULT_MAIN_ROLE_PROFILE",
    "_EMPTY_CAMERA_POLLS",
    "_import_runtime_module",
    "_runtime_core_field",
)


def __getattr__(name: str):
    """@brief 为公开重型导出提供按需导入入口."""
    if name in (
        "UartIngressService",
        "VISION_CAMERA_POLL_ORDER",
        "VisionCoordinator",
        "VisionProtocol",
        "build_logger_debug_sink",
        "build_uart3_logger_manager",
        "create_encoders",
        "create_imu",
        "create_motors",
        "create_uart3",
        "create_uart6",
        "load_gyro_offsets",
        "load_ident_lookup",
    ):
        from services.car import core as core_module

        return getattr(core_module, name)
    raise AttributeError(name)
