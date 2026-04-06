def test_master_vision_ingress_tracks_both_configured_uarts() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    assert ingress.active_uart == "uart6"
    assert ingress.reserved_uarts == ("uart8",)
    assert ingress.known_uarts == ("uart6", "uart8")


def test_master_vision_ingress_parses_active_minimal_vision_report() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(
        {"uart": "uart6", "line": "v=1,s=12,x=0.15,y=-0.05"}
    )

    assert observation["valid"] == 1
    assert observation["vision_seq"] == 12
    assert observation["err_x"] == 0.15
    assert observation["err_y"] == -0.05
    assert observation["selected_target"] == "tracked"
    assert observation["configured_uart"] == "uart6"
    assert observation["source_uart"] == "uart6"
    assert "camera_id" not in observation
    assert "target" not in observation


def test_prepare_observation_treats_parser_errors_as_invalid_input() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(
        {"uart": "uart6", "line": "v=1,x=0.15,y=-0.05"}
    )

    assert observation["source_status"] == "invalid"
    assert observation["valid"] == 0


def test_prepare_observation_accepts_both_uarts_with_same_xy_semantics() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    uart6 = ingress.prepare_observation({"uart": "uart6", "line": "v=1,s=12,x=10,y=5"})
    uart8 = ingress.prepare_observation({"uart": "uart8", "line": "v=1,s=3,x=10,y=5"})

    assert uart6["valid"] == 1
    assert uart8["valid"] == 1
    assert uart6["configured_uart"] == "uart6"
    assert uart8["configured_uart"] == "uart6"
    assert uart6["source_uart"] == "uart6"
    assert uart8["source_uart"] == "uart8"
    assert (uart6["err_x"], uart6["err_y"]) == (10.0, 5.0)
    assert (uart8["err_x"], uart8["err_y"]) == (10.0, 5.0)


def test_prepare_observation_accepts_preparsed_valid_payload_without_legacy_fields() -> (
    None
):
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(
        {"uart": "uart8", "vision_seq": 3, "valid": 1, "err_x": 10, "err_y": 5}
    )

    assert observation["source_status"] == "active"
    assert observation["valid"] == 1
    assert observation["configured_uart"] == "uart6"
    assert observation["source_uart"] == "uart8"
    assert observation["selected_target"] == "tracked"
    assert (observation["err_x"], observation["err_y"]) == (10.0, 5.0)
    assert "camera_id" not in observation
    assert "target" not in observation


def test_prepare_observation_accepts_preparsed_invalid_payload_without_legacy_fields() -> (
    None
):
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(
        {"uart": "uart6", "vision_seq": 3, "valid": 0}
    )

    assert observation["source_status"] == "active"
    assert observation["valid"] == 0
    assert observation["selected_target"] == "idle"
    assert "camera_id" not in observation
    assert "target" not in observation


def test_prepare_observation_returns_idle_result_when_input_missing() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(None)

    assert observation["configured_uart"] == "uart6"
    assert observation["source_uart"] == ""
    assert observation["source_status"] == "missing"
    assert observation["valid"] == 0
    assert "camera_id" not in observation
    assert "target" not in observation


def test_prepare_observation_returns_idle_result_for_unknown_uart() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(
        {"uart": "uart9", "line": "v=1,s=1,x=1,y=2"}
    )

    assert observation["configured_uart"] == "uart6"
    assert observation["source_uart"] == "uart9"
    assert observation["source_status"] == "unexpected_uart"
    assert observation["valid"] == 0


def test_select_current_target_prefers_latest_received_fresh_report() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {"uart": "uart6", "line": "v=1,s=8,x=1,y=2", "now_ms": 1000}
    )
    ingress.prepare_observation(
        {"uart": "uart8", "line": "v=1,s=7,x=9,y=9", "now_ms": 1010}
    )

    selected = ingress.select_current_target(now_ms=1010)

    assert selected["selected_target"] == "tracked"
    assert selected["source_uart"] == "uart8"
    assert selected["vision_seq"] == 7
    assert (selected["err_x"], selected["err_y"]) == (9.0, 9.0)


def test_select_current_target_prefers_uart6_when_reports_are_equally_fresh() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {"uart": "uart8", "line": "v=1,s=5,x=10,y=5", "now_ms": 1000}
    )
    ingress.prepare_observation(
        {"uart": "uart6", "line": "v=1,s=5,x=1,y=2", "now_ms": 1000}
    )

    selected = ingress.select_current_target(now_ms=1000)

    assert selected["selected_target"] == "tracked"
    assert selected["source_uart"] == "uart6"
    assert selected["vision_seq"] == 5
    assert (selected["err_x"], selected["err_y"]) == (1.0, 2.0)


def test_select_current_target_prefers_current_valid_target_over_newer_invalid_report() -> (
    None
):
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation({"uart": "uart6", "line": "v=1,s=4,x=2,y=3"})
    ingress.prepare_observation({"uart": "uart8", "line": "v=0,s=5"})

    selected = ingress.select_current_target()

    assert selected["selected_target"] == "tracked"
    assert selected["source_uart"] == "uart6"
    assert selected["valid"] == 1
    assert selected["vision_seq"] == 4


def test_prepare_observation_ignores_older_seq_from_same_uart() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {"uart": "uart6", "line": "v=1,s=9,x=12,y=-6", "now_ms": 1000}
    )
    stale = ingress.prepare_observation(
        {"uart": "uart6", "line": "v=1,s=8,x=1,y=1", "now_ms": 1010}
    )
    selected = ingress.select_current_target(now_ms=1010)

    assert stale["vision_seq"] == 9
    assert stale["source_uart"] == "uart6"
    assert (stale["err_x"], stale["err_y"]) == (12.0, -6.0)
    assert selected["vision_seq"] == 9
    assert (selected["err_x"], selected["err_y"]) == (12.0, -6.0)


def test_prepare_observation_ignores_duplicate_seq_from_same_uart() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {"uart": "uart6", "line": "v=1,s=9,x=12,y=-6", "now_ms": 1000}
    )
    duplicate = ingress.prepare_observation(
        {"uart": "uart6", "line": "v=1,s=9,x=1,y=1", "now_ms": 1010}
    )
    selected = ingress.select_current_target(now_ms=1010)

    assert duplicate["vision_seq"] == 9
    assert duplicate["source_uart"] == "uart6"
    assert (duplicate["err_x"], duplicate["err_y"]) == (12.0, -6.0)
    assert selected["vision_seq"] == 9
    assert (selected["err_x"], selected["err_y"]) == (12.0, -6.0)


def test_select_current_target_prefers_configured_active_uart_when_equally_fresh() -> (
    None
):
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart8", reserved_uarts=("uart6",))

    ingress.prepare_observation(
        {"uart": "uart6", "line": "v=1,s=5,x=10,y=5", "now_ms": 1000}
    )
    ingress.prepare_observation(
        {"uart": "uart8", "line": "v=1,s=5,x=1,y=2", "now_ms": 1000}
    )

    selected = ingress.select_current_target(now_ms=1000)

    assert selected["source_uart"] == "uart8"
    assert selected["vision_seq"] == 5
    assert (selected["err_x"], selected["err_y"]) == (1.0, 2.0)


def test_select_current_target_keeps_last_valid_target_within_freshness_window() -> (
    None
):
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {"uart": "uart6", "line": "v=1,s=9,x=12,y=-6", "now_ms": 1000}
    )
    ingress.begin_frame()

    selected = ingress.select_current_target(now_ms=1100)

    assert selected["selected_target"] == "tracked"
    assert selected["source_uart"] == "uart6"
    assert selected["valid"] == 1
    assert selected["fresh"] == 1
    assert selected["stale"] == 0
    assert selected["has_new_input"] == 0
    assert (selected["err_x"], selected["err_y"]) == (12.0, -6.0)


def test_prepare_observation_uart_and_now_ms_only_keeps_fresh_target() -> None:
    from master.vision.ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    ingress.prepare_observation(
        {"uart": "uart6", "line": "v=1,s=9,x=12,y=-6", "now_ms": 1000}
    )
    ingress.begin_frame(now_ms=1100)
    ingress.prepare_observation({"uart": "uart6", "now_ms": 1100})

    selected = ingress.select_current_target(now_ms=1100)

    assert selected["selected_target"] == "tracked"
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
        {"uart": "uart6", "line": "v=1,s=9,x=12,y=-6", "now_ms": 1000}
    )
    ingress.begin_frame()

    selected = ingress.select_current_target(now_ms=1200)

    assert selected["selected_target"] == "idle"
    assert selected["valid"] == 0
    assert selected["fresh"] == 0
    assert selected["stale"] == 1
    assert selected["has_new_input"] == 0
