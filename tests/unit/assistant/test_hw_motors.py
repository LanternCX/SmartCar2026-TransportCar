def test_motor_port_ensure_device_propagates_import_error(monkeypatch) -> None:
    import builtins
    import pytest

    from assistant.hw.motors import MotorPort

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "seekfree":
            raise ImportError("缺少 seekfree 模块")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)

    with pytest.raises(ImportError, match="缺少 seekfree 模块"):
        MotorPort("m", "PWM_C30_DIR_C31", False).ensure_device()
