"""主辅任务状态参数编码测试."""

import pytest

from role.task_sync import (
    ASSISTANT_ORBIT_MODE_AVOID_NEGATIVE,
    ASSISTANT_ORBIT_MODE_AVOID_POSITIVE,
    ASSISTANT_ORBIT_MODE_NORMAL,
    pack_assistant_avoidance_shift_arg,
    pack_assistant_orbit_arg,
    unpack_assistant_avoidance_shift_distance_cm,
    unpack_assistant_avoidance_shift_object_id,
    unpack_assistant_orbit_mode,
    unpack_assistant_orbit_object_id,
)


@pytest.mark.parametrize(
    "mode",
    (
        ASSISTANT_ORBIT_MODE_NORMAL,
        ASSISTANT_ORBIT_MODE_AVOID_NEGATIVE,
        ASSISTANT_ORBIT_MODE_AVOID_POSITIVE,
    ),
)
def test_assistant_orbit_arg_round_trips_named_mode_and_object(mode: int) -> None:
    """辅车绕行参数往返保留有名模式与物体编号."""
    arg = pack_assistant_orbit_arg(mode, 201)

    assert unpack_assistant_orbit_mode(arg) == mode
    assert unpack_assistant_orbit_object_id(arg) == 201


@pytest.mark.parametrize("distance_cm", (1, 127, 255))
def test_assistant_avoidance_shift_arg_round_trips_distance(
    distance_cm: int,
) -> None:
    """辅车避障平移参数往返保留厘米距离与物体编号."""
    arg = pack_assistant_avoidance_shift_arg(distance_cm, 201)

    assert unpack_assistant_avoidance_shift_distance_cm(arg) == distance_cm
    assert unpack_assistant_avoidance_shift_object_id(arg) == 201


@pytest.mark.parametrize("mode", (-1, 3))
def test_assistant_orbit_arg_rejects_unknown_mode(mode: int) -> None:
    """辅车绕行参数拒绝未定义模式."""
    with pytest.raises(ValueError):
        pack_assistant_orbit_arg(mode, 1)


@pytest.mark.parametrize("distance_cm", (0, 256))
def test_assistant_avoidance_shift_arg_rejects_out_of_range_distance(
    distance_cm: int,
) -> None:
    """辅车避障平移参数只接受一个字节可表达的正厘米距离."""
    with pytest.raises(ValueError):
        pack_assistant_avoidance_shift_arg(distance_cm, 1)


@pytest.mark.parametrize("object_id", (-1, 256))
def test_named_task_args_reject_out_of_range_object_id(object_id: int) -> None:
    """有名任务参数拒绝超出单字节范围的物体编号."""
    with pytest.raises(ValueError):
        pack_assistant_orbit_arg(ASSISTANT_ORBIT_MODE_NORMAL, object_id)
    with pytest.raises(ValueError):
        pack_assistant_avoidance_shift_arg(1, object_id)
