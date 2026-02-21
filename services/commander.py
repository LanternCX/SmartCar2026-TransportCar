"""指令分词器:将原始命令行拆分为 (key, raw_val_str) 二元组列表.

业务逻辑(类型转换、限幅、路由)已迁移至 CommandRouter 和 TransportCar.
"""


def tokenize(cmd_str):
    """
    将聚合命令字符串拆分为 (key, raw_val_str) 二元组列表.

    规则:
    - 裸 "reset" 返回 [("reset", "1")]
    - 按逗号分割,忽略不含 "=" 的片段
    - key 转为小写,val 保留原始字符串(由调用方转换类型)

    参数:
        cmd_str: 原始命令行,如 ``"vx=10,vy=5,dx=0.3"``.
    返回:
        list of (key: str, val_str: str),可能为空列表.
    """
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return []

    if cmd_str == "reset":
        return [("reset", "1")]

    tokens = []
    for part in cmd_str.split(","):
        if "=" not in part:
            continue
        key, val_str = part.split("=", 1)
        tokens.append((key.strip().lower(), val_str.strip()))

    return tokens
