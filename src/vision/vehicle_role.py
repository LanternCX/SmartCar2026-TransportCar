"""车号识别模块.

根据 `D8/D9` 拨码输入解码当前板子的角色。
"""

ROLE_MASTER = "master"
ROLE_ASSISTANT = "assistant"


def decode_vehicle_role(d8_value: int, d9_value: int) -> str:
    """将 D8/D9 电平解码为主车或辅车角色."""

    d8_state = int(d8_value)
    d9_state = int(d9_value)

    if d8_state == 0 and d9_state == 1:
        return ROLE_MASTER
    if d8_state == 1 and d9_state == 0:
        return ROLE_ASSISTANT

    raise ValueError("invalid vehicle role pins: D8=%d,D9=%d" % (d8_state, d9_state))


def _read_role_pin(pin_name: str) -> int:
    """读取单个角色拨码输入."""

    from machine import Pin

    pin = Pin(pin_name, Pin.IN, pull=Pin.PULL_UP_47K)
    return int(pin.value())


def read_vehicle_role() -> str:
    """读取 D8/D9 拨码输入并返回当前角色."""

    return decode_vehicle_role(_read_role_pin("D8"), _read_role_pin("D9"))
