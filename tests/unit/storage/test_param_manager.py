"""障碍配置读取行为测试."""

from pathlib import Path

import pytest

from config import motion as motion_params
from config import storage as storage_params
from storage import param_manager


FIELD_SIZE_M = motion_params.FIELD_SIZE_M


def _write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "obstacles.txt"
    path.write_text(content, encoding="ascii")
    return path


def test_storage_files_share_board_directory() -> None:
    paths = (
        storage_params.IDENT_RESULTS_FILE,
        storage_params.GYRO_OFFSET_FILE,
        storage_params.OBSTACLE_CONFIG_FILE,
    )

    assert {path.rsplit("/", 1)[0] for path in paths} == {"/flash/storage"}


@pytest.mark.parametrize(
    ("edge", "left", "right"),
    (
        ("top", 0.0, 3.2),
        ("bottom", 0.25, 2.75),
        ("left", 0.0, 2.4),
        ("right", 0.25, 2.0),
    ),
)
def test_load_obstacle_slots_accepts_all_edges(
    tmp_path: Path, edge: str, left: float, right: float
) -> None:
    path = _write_config(
        tmp_path,
        "brick,%s,%s,%s\n" % (edge, left, right),
    )

    slots = param_manager.load_obstacle_slots(path, FIELD_SIZE_M)

    assert slots == (("brick", edge, left, right),)


def test_load_obstacle_slots_accepts_transport_only_bump(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        "brick,top,1.8,2.1\nbrick,bottom,1.8,2.1\nbump,left,1.05,1.35\n",
    )

    slots = param_manager.load_obstacle_slots(path, FIELD_SIZE_M)

    assert slots == (
        ("brick", "top", 1.8, 2.1),
        ("brick", "bottom", 1.8, 2.1),
        ("bump", "left", 1.05, 1.35),
    )


def test_load_obstacle_slots_accepts_multiple_same_edge_obstacles(
    tmp_path: Path,
) -> None:
    path = _write_config(
        tmp_path,
        "brick,top,0.2,0.4\nbrick,top,1.0,1.2\nbrick,top,2.0,2.2\n",
    )

    slots = param_manager.load_obstacle_slots(path, FIELD_SIZE_M)

    assert slots == (
        ("brick", "top", 0.2, 0.4),
        ("brick", "top", 1.0, 1.2),
        ("brick", "top", 2.0, 2.2),
    )


def test_load_obstacle_slots_strips_field_whitespace(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        " brick , top , 1.45 , 1.75 \n",
    )

    slots = param_manager.load_obstacle_slots(path, FIELD_SIZE_M)

    assert slots == (("brick", "top", 1.45, 1.75),)


def test_load_obstacle_slots_rejects_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.txt"

    with pytest.raises(OSError):
        param_manager.load_obstacle_slots(path, FIELD_SIZE_M)


def test_load_obstacle_slots_accepts_empty_file(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "")

    assert param_manager.load_obstacle_slots(path, FIELD_SIZE_M) == ()


@pytest.mark.parametrize(
    ("obstacle_type", "maximum"),
    (("brick", 3), ("bump", 5)),
)
def test_load_obstacle_slots_rejects_type_count_above_limit(
    tmp_path: Path, obstacle_type: str, maximum: int
) -> None:
    allowed_content = "\n".join(
        "%s,top,%.2f,%.2f"
        % (obstacle_type, index * 0.1, index * 0.1 + 0.05)
        for index in range(maximum)
    )
    allowed_path = _write_config(tmp_path, allowed_content)

    assert len(param_manager.load_obstacle_slots(allowed_path, FIELD_SIZE_M)) == maximum

    rejected_path = _write_config(
        tmp_path,
        allowed_content
        + "\n%s,top,%.2f,%.2f"
        % (obstacle_type, maximum * 0.1, maximum * 0.1 + 0.05),
    )

    with pytest.raises(ValueError):
        param_manager.load_obstacle_slots(rejected_path, FIELD_SIZE_M)


@pytest.mark.parametrize(
    "invalid_line",
    (
        "brick,top,1.0",
        "brick,top,1.0,2.0,extra",
        "wall,top,1.0,2.0",
        "brick,center,1.0,2.0",
        "brick,top,start,2.0",
        "brick,top,nan,2.0",
        "brick,top,1.0,inf",
        "brick,top,2.0,1.0",
        "brick,top,1.0,1.0",
        "brick,top,-0.1,1.0",
        "brick,top,1.0,3.21",
        "brick,left,1.0,2.41",
        "none,none,-1,-1",
    ),
)
def test_load_obstacle_slots_rejects_invalid_slot(
    tmp_path: Path, invalid_line: str
) -> None:
    path = _write_config(tmp_path, invalid_line)

    with pytest.raises(ValueError):
        param_manager.load_obstacle_slots(path, FIELD_SIZE_M)
