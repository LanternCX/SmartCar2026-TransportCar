def test_master_vision_ingress_tracks_both_configured_uarts() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    assert ingress.active_uart == "uart6"
    assert ingress.reserved_uarts == ("uart8",)
    assert ingress.known_uarts == ("uart6", "uart8")


def test_master_vision_ingress_parses_active_vision_report() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=12,valid=1,target=follower,err_x=0.15,err_y=-0.05,bbox_left=10,bbox_top=20,bbox_right=30,bbox_bottom=60",
        }
    )

    assert observation["valid"] == 1
    assert observation["camera_id"] == "cam_a"
    assert observation["err_x"] == 0.15
    assert observation["err_y"] == -0.05
    assert observation["configured_uart"] == "uart6"
    assert observation["source_uart"] == "uart6"


def test_prepare_observation_accepts_both_uarts_with_same_xy_semantics() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    uart6 = ingress.prepare_observation(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=12,valid=1,target=follower,err_x=10,err_y=5",
        }
    )
    uart8 = ingress.prepare_observation(
        {
            "uart": "uart8",
            "line": "vision=1,camera_id=cam_b,seq=3,valid=1,target=follower,err_x=10,err_y=5",
        }
    )

    assert uart6["valid"] == 1
    assert uart8["valid"] == 1
    assert uart6["configured_uart"] == "uart6"
    assert uart8["configured_uart"] == "uart6"
    assert uart6["source_uart"] == "uart6"
    assert uart8["source_uart"] == "uart8"
    assert (uart6["err_x"], uart6["err_y"]) == (10.0, 5.0)
    assert (uart8["err_x"], uart8["err_y"]) == (10.0, 5.0)


def test_prepare_observation_normalizes_preparsed_input_through_same_entry() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(
        {
            "uart": "uart8",
            "camera_id": "cam_b",
            "vision_seq": 3,
            "valid": 1,
            "target": "follower",
            "err_x": 10,
            "err_y": 5,
        }
    )

    assert observation["valid"] == 1
    assert observation["camera_id"] == "cam_b"
    assert observation["configured_uart"] == "uart6"
    assert observation["source_uart"] == "uart8"
    assert (observation["err_x"], observation["err_y"]) == (10.0, 5.0)


def test_prepare_observation_returns_idle_result_when_input_missing() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(None)

    assert observation["configured_uart"] == "uart6"
    assert observation["source_uart"] == ""
    assert observation["camera_id"] == ""
    assert observation["source_status"] == "missing"
    assert observation["valid"] == 0


def test_prepare_observation_returns_idle_result_for_unknown_uart() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(
        {
            "uart": "uart9",
            "line": "vision=1,camera_id=cam_x,seq=1,valid=1,target=follower,err_x=1,err_y=2",
        }
    )

    assert observation["configured_uart"] == "uart6"
    assert observation["source_uart"] == "uart9"
    assert observation["camera_id"] == ""
    assert observation["source_status"] == "unexpected_uart"
    assert observation["valid"] == 0


def test_prepare_observation_returns_idle_result_for_invalid_payload() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(
        {
            "uart": "uart6",
            "line": "vision=0,camera_id=cam_a,seq=1,valid=1,target=follower,err_x=1,err_y=2",
        }
    )

    assert observation["configured_uart"] == "uart6"
    assert observation["source_uart"] == "uart6"
    assert observation["camera_id"] == ""
    assert observation["source_status"] == "invalid"
    assert observation["valid"] == 0


def test_select_current_target_prefers_latest_received_fresh_report() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=8,valid=1,target=follower,err_x=1,err_y=2",
            "now_ms": 1000,
        }
    )
    ingress.prepare_observation(
        {
            "uart": "uart8",
            "line": "vision=1,camera_id=cam_b,seq=7,valid=1,target=follower,err_x=9,err_y=9",
            "now_ms": 1010,
        }
    )

    selected = ingress.select_current_target(now_ms=1010)

    assert selected["camera_id"] == "cam_b"
    assert selected["source_uart"] == "uart8"
    assert selected["vision_seq"] == 7
    assert (selected["err_x"], selected["err_y"]) == (9.0, 9.0)


def test_select_current_target_prefers_uart6_when_reports_are_equally_fresh() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {
            "uart": "uart8",
            "line": "vision=1,camera_id=cam_b,seq=5,valid=1,target=follower,err_x=10,err_y=5",
            "now_ms": 1000,
        }
    )
    ingress.prepare_observation(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=5,valid=1,target=follower,err_x=1,err_y=2",
            "now_ms": 1000,
        }
    )

    selected = ingress.select_current_target(now_ms=1000)

    assert selected["camera_id"] == "cam_a"
    assert selected["source_uart"] == "uart6"
    assert selected["vision_seq"] == 5
    assert (selected["err_x"], selected["err_y"]) == (1.0, 2.0)


def test_select_current_target_prefers_current_valid_target_over_newer_invalid_report() -> (
    None
):
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=4,valid=1,target=follower,err_x=2,err_y=3",
        }
    )
    ingress.prepare_observation(
        {
            "uart": "uart8",
            "line": "vision=1,camera_id=cam_b,seq=5,valid=0,target=follower",
        }
    )

    selected = ingress.select_current_target()

    assert selected["camera_id"] == "cam_a"
    assert selected["source_uart"] == "uart6"
    assert selected["valid"] == 1
    assert selected["vision_seq"] == 4


def test_select_current_target_uses_fixed_uart6_priority_when_equally_fresh() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart8", reserved_uarts=("uart6",))

    ingress.prepare_observation(
        {
            "uart": "uart8",
            "line": "vision=1,camera_id=cam_b,seq=6,valid=1,target=follower,err_x=10,err_y=5",
            "now_ms": 1000,
        }
    )
    ingress.prepare_observation(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=6,valid=1,target=follower,err_x=1,err_y=2",
            "now_ms": 1000,
        }
    )

    selected = ingress.select_current_target(now_ms=1000)

    assert selected["camera_id"] == "cam_a"
    assert selected["source_uart"] == "uart6"


def test_select_current_target_keeps_last_valid_target_within_freshness_window() -> (
    None
):
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )
    ingress.begin_frame()

    selected = ingress.select_current_target(now_ms=1100)

    assert selected["camera_id"] == "cam_a"
    assert selected["source_uart"] == "uart6"
    assert selected["valid"] == 1
    assert selected["fresh"] == 1
    assert selected["stale"] == 0
    assert selected["has_new_input"] == 0
    assert (selected["err_x"], selected["err_y"]) == (12.0, -6.0)


def test_prepare_observation_empty_uart_frame_does_not_erase_fresh_target() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )
    ingress.begin_frame(now_ms=1100)
    ingress.prepare_observation({"uart": "uart6"}, now_ms=1100)

    selected = ingress.select_current_target(now_ms=1100)

    assert selected["camera_id"] == "cam_a"
    assert selected["source_uart"] == "uart6"
    assert selected["valid"] == 1
    assert selected["fresh"] == 1
    assert selected["stale"] == 0
    assert selected["has_new_input"] == 0
    assert (selected["err_x"], selected["err_y"]) == (12.0, -6.0)


def test_select_current_target_expires_last_valid_target_after_freshness_window() -> (
    None
):
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {
            "uart": "uart6",
            "line": "vision=1,camera_id=cam_a,seq=9,valid=1,target=follower,err_x=12,err_y=-6",
            "now_ms": 1000,
        }
    )
    ingress.begin_frame()

    selected = ingress.select_current_target(now_ms=1200)

    assert selected["selected_target"] == "idle"
    assert selected["valid"] == 0
    assert selected["fresh"] == 0
    assert selected["stale"] == 1
    assert selected["has_new_input"] == 0
