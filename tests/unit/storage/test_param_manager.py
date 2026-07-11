"""障碍配置读取行为测试."""

from pathlib import Path

import pytest

from config import motion as motion_params
from config import storage as storage_params
from storage import param_manager


ROOT = Path(__file__).resolve().parents[3]
MOCK_OBSTACLE_FILE = ROOT / "src" / "storage" / "obstacles.txt"
FIELD_SIZE_M = motion_params.FIELD_SIZE_M
MOCK_OBSTACLE_WIDTH_M = 0.30


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


def test_load_obstacle_slots_reads_repository_mock_file() -> None:
    slots = param_manager.load_obstacle_slots(MOCK_OBSTACLE_FILE, FIELD_SIZE_M)
    edge, left, right = slots[0]

    assert edge == motion_params.TRANSPORT_OBJECT_TARGET_EDGE[-1]
    assert (left + right) * 0.5 == pytest.approx(FIELD_SIZE_M[1] * 0.5)
    assert right - left == pytest.approx(MOCK_OBSTACLE_WIDTH_M)
    assert slots[1:] == ((None, -1.0, -1.0), (None, -1.0, -1.0))


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
        "%s,%s,%s\nnone,-1,-1\nnone,-1,-1\n" % (edge, left, right),
    )

    slots = param_manager.load_obstacle_slots(path, FIELD_SIZE_M)

    assert slots[0] == (edge, left, right)


def test_load_obstacle_slots_accepts_multiple_same_edge_obstacles(
    tmp_path: Path,
) -> None:
    path = _write_config(tmp_path, "top,0.2,0.4\ntop,1.0,1.2\ntop,2.0,2.2\n")

    slots = param_manager.load_obstacle_slots(path, FIELD_SIZE_M)

    assert slots == (
        ("top", 0.2, 0.4),
        ("top", 1.0, 1.2),
        ("top", 2.0, 2.2),
    )


def test_load_obstacle_slots_strips_field_whitespace(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        " top , 1.45 , 1.75 \n none , -1 , -1 \n none , -1 , -1 \n",
    )

    slots = param_manager.load_obstacle_slots(path, FIELD_SIZE_M)

    assert slots == (
        ("top", 1.45, 1.75),
        (None, -1.0, -1.0),
        (None, -1.0, -1.0),
    )


def test_load_obstacle_slots_rejects_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.txt"

    with pytest.raises(OSError):
        param_manager.load_obstacle_slots(path, FIELD_SIZE_M)


@pytest.mark.parametrize(
    "content",
    (
        "top,1.0,2.0\nnone,-1,-1\n",
        "top,1.0,2.0\nnone,-1,-1\nnone,-1,-1\nnone,-1,-1\n",
        "\ntop,1.0,2.0\nnone,-1,-1\nnone,-1,-1\n",
    ),
)
def test_load_obstacle_slots_requires_exactly_three_lines(
    tmp_path: Path, content: str
) -> None:
    path = _write_config(tmp_path, content)

    with pytest.raises(ValueError):
        param_manager.load_obstacle_slots(path, FIELD_SIZE_M)


@pytest.mark.parametrize(
    "invalid_line",
    (
        "top,1.0",
        "top,1.0,2.0,extra",
        "center,1.0,2.0",
        "top,start,2.0",
        "top,nan,2.0",
        "top,1.0,inf",
        "top,2.0,1.0",
        "top,1.0,1.0",
        "top,-0.1,1.0",
        "top,1.0,3.21",
        "left,1.0,2.41",
        "none,-1,0",
        "none,0,-1",
    ),
)
def test_load_obstacle_slots_rejects_invalid_slot(
    tmp_path: Path, invalid_line: str
) -> None:
    path = _write_config(
        tmp_path,
        "none,-1,-1\n%s\nnone,-1,-1\n" % invalid_line,
    )

    with pytest.raises(ValueError):
        param_manager.load_obstacle_slots(path, FIELD_SIZE_M)
