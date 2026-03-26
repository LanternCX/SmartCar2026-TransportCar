"""辅车最小运动协议解析

@file src/assistant/protocol.py
"""


class Command:
    """协议命令

    @brief 表示主车发给辅车的一条最小命令
    """

    def __init__(
        self,
        kind,
        vx=0.0,
        vy=0.0,
        omega=0.0,
        dx=0.0,
        dy=0.0,
        dtheta=0.0,
    ):
        self.kind = str(kind)
        self.vx = float(vx)
        self.vy = float(vy)
        self.omega = float(omega)
        self.dx = float(dx)
        self.dy = float(dy)
        self.dtheta = float(dtheta)


def _split_fields(line):
    """标准化命令行

    @brief 去掉首尾空白并按空格拆分
    @param line 原始命令文本
    @return list[str]
    """

    fields = line.strip().split()
    if not fields:
        raise ValueError("empty_command")
    return fields


def parse_command(line):
    """解析辅车最小协议

    @brief 支持控制类和运动类最小命令
    @param line 原始命令文本
    @return Command
    """

    fields = _split_fields(line)
    opcode = fields[0].upper()

    if opcode == "ARM" and len(fields) == 1:
        return Command(kind="arm")
    if opcode == "DISARM" and len(fields) == 1:
        return Command(kind="disarm")
    if opcode == "STOP" and len(fields) == 1:
        return Command(kind="stop")
    if opcode == "PING" and len(fields) == 1:
        return Command(kind="ping")
    if opcode == "STATE?" and len(fields) == 1:
        return Command(kind="state_query")
    if opcode == "HOLD" and len(fields) == 1:
        return Command(kind="hold")
    if opcode == "RESET_ODOM" and len(fields) == 1:
        return Command(kind="reset_odom")
    if opcode == "VEL" and len(fields) == 4:
        return Command(
            kind="vel",
            vx=float(fields[1]),
            vy=float(fields[2]),
            omega=float(fields[3]),
        )
    if opcode == "MOVE" and len(fields) == 4:
        return Command(
            kind="move",
            dx=float(fields[1]),
            dy=float(fields[2]),
            dtheta=float(fields[3]),
        )

    raise ValueError("unsupported_command")
