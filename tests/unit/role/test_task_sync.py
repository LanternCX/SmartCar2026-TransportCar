"""主辅任务状态参数编码测试."""

import pytest

from role.task_sync import (
    pack_assistant_orbit_arg,
    pack_task_arg,
    unpack_assistant_orbit_direction,
    unpack_assistant_orbit_object_id,
    unpack_assistant_orbit_offset_deg,
    unpack_task_arg_object_id,
    unpack_task_arg_preliminary_final,
)


@pytest.mark.parametrize("offset_deg", (-90, -37, 0, 42, 90))
@pytest.mark.parametrize("direction", (-1, 0, 1))
def test_assistant_orbit_arg_round_trips_offset_and_object(
    offset_deg: int,
    direction: int,
) -> None:
    """辅车绕行参数往返保留相对角度与物体编号."""
    arg = pack_assistant_orbit_arg(offset_deg, 31, direction)

    assert unpack_assistant_orbit_offset_deg(arg) == offset_deg
    assert unpack_assistant_orbit_object_id(arg) == 31
    assert unpack_assistant_orbit_direction(arg) == direction


def test_task_args_preserve_preliminary_final_decision() -> None:
    """任务同步在普通阶段和绕行阶段都保留预赛最后一轮标记."""
    task_arg = pack_task_arg(2, 5, preliminary_final=True)
    orbit_arg = pack_assistant_orbit_arg(
        -35,
        5,
        direction=1,
        preliminary_final=True,
    )

    assert unpack_task_arg_object_id(task_arg) == 5
    assert unpack_task_arg_preliminary_final(task_arg) is True
    assert unpack_assistant_orbit_object_id(orbit_arg) == 5
    assert unpack_task_arg_preliminary_final(orbit_arg) is True
    assert unpack_assistant_orbit_direction(orbit_arg) == 1


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


@pytest.mark.parametrize("object_id", (-1, 32))
def test_assistant_orbit_arg_rejects_out_of_range_object_id(
    object_id: int,
) -> None:
    """绕行参数拒绝占用预赛标志位的物体编号."""
    with pytest.raises(ValueError):
        pack_assistant_orbit_arg(0, object_id)


@pytest.mark.parametrize("direction", (-2, 2))
def test_assistant_orbit_arg_rejects_unknown_direction(direction: int) -> None:
    """绕行参数只接受负方向、最短路径和正方向."""
    with pytest.raises(ValueError):
        pack_assistant_orbit_arg(0, 1, direction)
