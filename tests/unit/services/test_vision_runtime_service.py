"""VisionRuntimeService 单元测试."""

import types

import pytest


pytestmark = pytest.mark.unit


def test_aux_role_does_not_activate_full_vision_runtime() -> None:
    from services.runtime.vision_runtime_service import VisionRuntimeService

    service = VisionRuntimeService(
        vehicle_role="aux",
        build_disabled_coordinator=lambda: types.SimpleNamespace(
            get_state_name=lambda: "DISABLED"
        ),
    )

    assert service.enabled is False
    assert service.vision_runtime is None
    assert service.vision_coordinator.get_state_name() == "DISABLED"


def test_main_role_builds_runtime_and_coordinator_once() -> None:
    from services.runtime.vision_runtime_service import VisionRuntimeService

    created = []

    def build_runtime(timeout_ms):
        runtime = types.SimpleNamespace(timeout_ms=timeout_ms)
        created.append(("runtime", timeout_ms))
        return runtime

    def build_coordinator(runtime):
        created.append(("coordinator", runtime.timeout_ms))
        return types.SimpleNamespace(runtime=runtime, get_state_name=lambda: "IDLE")

    service = VisionRuntimeService(
        vehicle_role="main",
        build_runtime=build_runtime,
        build_coordinator=build_coordinator,
    )

    assert service.enabled is True
    assert service.vision_runtime is not None
    assert service.vision_runtime.timeout_ms > 0
    assert service.vision_coordinator.runtime is service.vision_runtime
    assert created == [
        ("runtime", service.vision_runtime.timeout_ms),
        ("coordinator", service.vision_runtime.timeout_ms),
    ]
