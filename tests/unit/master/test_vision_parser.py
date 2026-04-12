import pytest


def test_parse_vision_line_parses_minimal_valid_frame() -> None:
    from master.vision.parser import parse_vision_line

    observation = parse_vision_line("v=1,s=12,x=7,y=50")

    assert observation == {
        "vision_seq": 12,
        "valid": 1,
        "err_x": 7.0,
        "err_y": 50.0,
    }


def test_parse_vision_line_parses_minimal_invalid_frame() -> None:
    from master.vision.parser import parse_vision_line

    observation = parse_vision_line("v=0,s=13")

    assert observation == {
        "vision_seq": 13,
        "valid": 0,
        "err_x": 0.0,
        "err_y": 0.0,
    }


@pytest.mark.parametrize(
    "line",
    (
        "v=1,x=7,y=50",
        "v=0",
        "v=1,s=12,x=7",
        "v=1,s=12,y=50",
        "v=1,s=12,x=7,y=50,target=red",
        "v=0,s=13,camera_id=cam_a",
        "v=0,s=13,x=7",
        "v=0,s=13,y=50",
        "v=0,s=13,x=7,y=50",
        "v=1,s=12,x=7,y=50,s=13",
        "v=1,s=12,x=7,y=50,v=0",
        "v=1,s=12,x=7,y=50,x=9",
        "v=1,s=12,x=7,y=50,y=9",
    ),
)
def test_parse_vision_line_rejects_incomplete_or_duplicated_minimal_fields(
    line: str,
) -> None:
    from master.vision.parser import parse_vision_line

    with pytest.raises(ValueError):
        parse_vision_line(line)
