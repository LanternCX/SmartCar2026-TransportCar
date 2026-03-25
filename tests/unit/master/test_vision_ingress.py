def test_master_vision_ingress_keeps_single_uart_polling_topology() -> None:
    from master.vision_ingress import VisionIngress

    ingress = VisionIngress(vision_uart="uart6", camera_ids=("cam_a", "cam_b"))

    assert ingress.vision_uart == "uart6"
    assert ingress.camera_ids == ("cam_a", "cam_b")


def test_master_vision_ingress_polls_named_camera_only() -> None:
    from master.vision_ingress import VisionIngress

    ingress = VisionIngress(vision_uart="uart6", camera_ids=("cam_a", "cam_b"))

    poll = ingress.build_poll_request("cam_b")

    assert poll == "?frame=cam_b"


def test_master_vision_ingress_rotates_poll_order_on_single_uart() -> None:
    from master.vision_ingress import VisionIngress

    ingress = VisionIngress(vision_uart="uart6", camera_ids=("cam_a", "cam_b"))

    assert ingress.build_next_poll_request() == "?frame=cam_a"
    assert ingress.build_next_poll_request() == "?frame=cam_b"
