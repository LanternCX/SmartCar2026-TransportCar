"""搬运收尾阶段共享常量

@file src/role/clear_phase.py
"""

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value


CLEAR_PHASE_NONE = const(0)
CLEAR_PHASE_RETREAT = const(1)
CLEAR_PHASE_FORWARD = const(2)
