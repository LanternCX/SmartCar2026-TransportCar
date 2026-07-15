"""主辅任务状态参数编码测试."""

import pytest

from role.task_sync import (
    pack_assistant_orbit_arg,
    unpack_assistant_orbit_direction,
    unpack_assistant_orbit_object_id,
    unpack_assistant_orbit_offset_deg,
)


@pytest.mark.parametrize("offset_deg", (-90, -37, 0, 42, 90))
@pytest.mark.parametrize("direction", (-1, 0, 1))
def test_assistant_orbit_arg_round_trips_offset_and_object(
    offset_deg: int,
    direction: int,
) -> None:
    """辅车绕行参数往返保留相对角度与物体编号."""
    arg = pack_assistant_orbit_arg(offset_deg, 63, direction)

    assert unpack_assistant_orbit_offset_deg(arg) == offset_deg
    assert unpack_assistant_orbit_object_id(arg) == 63
    assert unpack_assistant_orbit_direction(arg) == direction


def test_assistant_orbit_arg_rounds_dynamic_offset_to_integer_degree() -> None:
    """动态角度按整数度同步给两车使用."""
    arg = pack_assistant_orbit_arg(22.6, 2)

    assert unpack_assistant_orbit_offset_deg(arg) == 23


@pytest.mark.parametrize("offset_deg", (-91, 91))
def test_assistant_orbit_arg_rejects_out_of_range_offset(
    offset_deg: int,
) -> None:
    """同边直线路径的相对角度限制在正负九十度内."""
    with pytest.raises(ValueError):
        pack_assistant_orbit_arg(offset_deg, 1)


@pytest.mark.parametrize("object_id", (-1, 64))
def test_assistant_orbit_arg_rejects_out_of_range_object_id(
    object_id: int,
) -> None:
    """绕行参数拒绝超出单字节范围的物体编号."""
    with pytest.raises(ValueError):
        pack_assistant_orbit_arg(0, object_id)


@pytest.mark.parametrize("direction", (-2, 2))
def test_assistant_orbit_arg_rejects_unknown_direction(direction: int) -> None:
    """绕行参数只接受负方向、最短路径和正方向."""
    with pytest.raises(ValueError):
        pack_assistant_orbit_arg(0, 1, direction)
