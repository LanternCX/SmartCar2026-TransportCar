"""主车底盘运行时边界.

@file src/master/ctrl/chassis.py
"""


class CoreRuntime:
    def __init__(self, hw_bundle=None):
        self.hw_bundle = hw_bundle


class ChassisRuntime:
    def __init__(self, core_runtime):
        self.core_runtime = core_runtime
