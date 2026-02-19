"""
命令处理器注册包：将所有元命令和查询命令注册到 CommandRouter。

每条命令对应一个独立模块，模块约定：
- ``KEYS: tuple``  — 该处理器响应的命令 key（可多个别名）
- ``handle(ctx, value)`` — 命令处理函数（查询处理器签名为 ``handle(ctx)``）

新增命令步骤：
1. 在本目录创建 ``cmd_xxx.py``，定义 ``KEYS`` 和 ``handle``
2. 在本文件的 ``_CMD_MODULES`` 列表中添加该模块的导入
"""
from services.commands.cmd_vx import handle as _h_vx, KEYS as _k_vx
from services.commands.cmd_vy import handle as _h_vy, KEYS as _k_vy
from services.commands.cmd_omega import handle as _h_omega, KEYS as _k_omega
from services.commands.cmd_x import handle as _h_x, KEYS as _k_x
from services.commands.cmd_y import handle as _h_y, KEYS as _k_y
from services.commands.cmd_angle import handle as _h_angle, KEYS as _k_angle
from services.commands.cmd_dx import handle as _h_dx, KEYS as _k_dx
from services.commands.cmd_dy import handle as _h_dy, KEYS as _k_dy
from services.commands.cmd_d_angle import handle as _h_d_angle, KEYS as _k_d_angle
from services.commands.cmd_rear import handle as _h_rear, KEYS as _k_rear
from services.commands.cmd_reset import handle as _h_reset, KEYS as _k_reset
from services.commands.cmd_print import handle as _h_print, KEYS as _k_print
from services.commands.query_pos import handle as _h_qpos, KEYS as _k_qpos
from services.commands.query_lock import handle as _h_qlock, KEYS as _k_qlock

# 命令处理器列表：(KEYS, handle)
_CMD_HANDLERS = [
    (_k_vx,      _h_vx),
    (_k_vy,      _h_vy),
    (_k_omega,   _h_omega),
    (_k_x,       _h_x),
    (_k_y,       _h_y),
    (_k_angle,   _h_angle),
    (_k_dx,      _h_dx),
    (_k_dy,      _h_dy),
    (_k_d_angle, _h_d_angle),
    (_k_rear,    _h_rear),
    (_k_reset,   _h_reset),
    (_k_print,   _h_print),
]

# 查询处理器列表：(KEYS, handle)
_QUERY_HANDLERS = [
    (_k_qpos,  _h_qpos),
    (_k_qlock, _h_qlock),
]


def register_commands(router) -> None:
    """
    将所有命令和查询处理器注册到 CommandRouter 实例。

    由 TransportCar.__init__ 在路由器创建后调用一次。

    参数：
        router: CommandRouter 实例。
    """
    for keys, handler in _CMD_HANDLERS:
        router.command(*keys)(handler)
    for keys, handler in _QUERY_HANDLERS:
        router.query(*keys)(handler)
