def test_master_vision_ingress_keeps_single_route_and_reserve_slot() -> None:
    from master.vision_ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    assert ingress.active_uart == "uart6"
    assert ingress.reserved_uarts == ("uart8",)


def test_master_vision_ingress_parses_active_vision_report() -> None:
    from master.vision_ingress import VisionIngress

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
    assert observation["active_uart"] == "uart6"


def test_master_vision_ingress_rejects_reserved_route_from_runtime_path() -> None:
    from master.vision_ingress import VisionIngress

    ingress = VisionIngress(active_uart="uart6", reserved_uarts=("uart8",))

    observation = ingress.prepare_observation(
        {
            "uart": "uart8",
            "line": "vision=1,camera_id=cam_b,seq=9,valid=1,target=follower,err_x=0.20,err_y=0.10",
        }
    )

    assert observation["valid"] == 0
    assert observation["source_status"] == "reserved"
