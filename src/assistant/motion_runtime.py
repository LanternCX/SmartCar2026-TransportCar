"""辅车运行时执行闭环

@file src/assistant/motion_runtime.py
"""

try:
    from assistant.ctrl.chassis import MotionRuntime
except ImportError:
    from ctrl.chassis import MotionRuntime


__all__ = ["MotionRuntime"]
