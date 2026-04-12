"""承接主车下发文本并转成辅车主链可执行命令, 供应用入口和运行时直接消费。

同时负责把辅车最小状态裁剪成对外回包文本, 作为状态输出的协议出口。

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


def render_state_line(state, state_label=None):
    """渲染辅车最小状态回包

    @brief 把运行时状态裁剪成协议约定的紧凑文本, 供主车轮询读取。
    @param state 当前辅车运行时状态
    @param state_label 可选对外状态标签
    @return str
    """

    if state_label is None:
        state_label = state.state_label
    return (
        "state=1,state_label=%s,last_seq=%d,follow_active=%d,"
        "heading_deg=%.3f,target_heading_deg=%.3f,yaw_rate_deg_s=%.3f,"
        "odom_x=%.4f,odom_y=%.4f,base_ok=%d"
    ) % (
        str(state_label),
        int(state.last_seq),
        1 if state.follow_active else 0,
        float(state.heading_deg),
        float(state.target_heading_deg),
        float(state.yaw_rate_deg_s),
        float(state.odom[0]),
        float(state.odom[1]),
        1 if state.base_ok else 0,
    )


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


def _split_csv_fields(line):
    fields = []
    for item in str(line).strip().split(","):
        field = item.strip()
        if field:
            fields.append(field)
    if not fields:
        raise ValueError("empty_command")
    return fields


def _split_pairs(line):
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


def _require_fields(payload, *required_keys):
    for key in required_keys:
        if key not in payload:
            raise ValueError("missing_required_field")


def parse_command(line):
    """解析辅车协议命令

    @brief 支持控制命令、运动命令和跟随报文
    @param line 原始命令文本
    @return Command
    """

    if "=" in str(line):
        payload = _split_pairs(line)
        if payload.get("f") == "1":
            if int(payload.get("m", 0) or 0) == 1:
                _require_fields(payload, "x", "y")
                return Command(
                    kind="follow_velocity",
                    seq=0,
                    valid=1,
                    vx=float(payload["x"]),
                    vy=float(payload["y"]),
                )
            _require_fields(payload, "s", "v", "x", "y")
            return Command(
                kind="follow",
                seq=int(payload["s"]),
                valid=int(payload["v"]),
                dx=float(payload["x"]),
                dy=float(payload["y"]),
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
