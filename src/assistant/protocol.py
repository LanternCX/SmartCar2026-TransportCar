"""辅车协议文本解析

@file src/assistant/protocol.py
"""


class Command:
    """协议命令

    @brief 表示主车发给辅车的一条已解析命令
    """

    def __init__(
        self,
        kind,
        seq=0,
        valid=0,
        vx=0.0,
        vy=0.0,
        omega=0.0,
        dx=0.0,
        dy=0.0,
        dtheta=0.0,
    ):
        # 命令参数统一在构造时完成类型归一, 便于运行时直接消费
        self.kind = str(kind)
        self.seq = int(seq)
        self.valid = 1 if int(valid) else 0
        self.vx = float(vx)
        self.vy = float(vy)
        self.omega = float(omega)
        self.dx = float(dx)
        self.dy = float(dy)
        self.dtheta = float(dtheta)


def _split_fields(line):
    """标准化命令行

    @brief 去掉首尾空白并按空格拆分字段
    @param line 原始命令文本
    @return list[str]
    """

    fields = line.strip().split()
    if not fields:
        raise ValueError("empty_command")
    return fields


def _split_pairs(line):
    """按逗号拆解键值对协议

    @brief 用于解析 `follow=1,...` 形式的键值报文
    @param line 原始命令文本
    @return dict
    """

    payload = {}
    for item in str(line).strip().split(","):
        field = item.strip()
        if not field:
            continue
        if "=" not in field:
            raise ValueError("invalid_field")
        key, value = field.split("=", 1)
        key = key.strip().lower()
        if key in payload:
            raise ValueError("duplicate_key")
        payload[key] = value.strip()
    if not payload:
        raise ValueError("empty_command")
    return payload


def parse_command(line):
    """解析辅车协议命令

    @brief 支持控制命令、运动命令和跟随报文
    @param line 原始命令文本
    @return Command
    """

    # 带等号的文本优先按键值协议解析, 用于处理高频跟随报文
    if "=" in str(line):
        payload = _split_pairs(line)
        if payload.get("follow") == "1":
            return Command(
                kind="follow",
                seq=int(payload["seq"]),
                valid=int(payload["valid"]),
                dx=float(payload.get("dx", 0.0)),
                dy=float(payload.get("dy", 0.0)),
                dtheta=float(payload.get("d_angle", 0.0)),
            )

    fields = _split_fields(line)
    opcode = fields[0].upper()

    # 文本命令按首字段分发到对应命令类型

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
