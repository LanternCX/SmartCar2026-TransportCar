"""主车控制层包入口.

上游由 `motion_runtime.py` 这类运行时编排代码调用, 下游连接姿态、滤波、运动学和速度环模块。这里只保留导航说明, 不放控制实现细节。

@file src/master/ctrl/__init__.py
"""
