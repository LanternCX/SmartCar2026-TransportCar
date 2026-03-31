def test_master_runtime_loop_reads_vision_and_writes_follow_command() -> None:
    from master.app import MasterRuntimeLoop

    class FakeUart:
        def __init__(self, lines=None):
            self.lines = list(lines or [])
            self.writes = []

        def read_line(self):
            if not self.lines:
                return None
            return self.lines.pop(0)

        def write_line(self, payload):
            self.writes.append(payload)

    uart6 = FakeUart(
        ["vision=1,camera_id=cam_a,seq=1,valid=1,target=follower,err_x=12,err_y=-6"]
    )
    uart8 = FakeUart()
    uart3 = FakeUart()

    loop = MasterRuntimeLoop({"uart6": uart6, "uart8": uart8, "uart3": uart3})
    result = loop.step(now_ms=100)

    assert result["assistant_command"] == "follow=1,seq=1,valid=1,dx=12.000,dy=-6.000"
    assert uart3.writes == ["follow=1,seq=1,valid=1,dx=12.000,dy=-6.000"]


def test_master_runtime_loop_writes_hold_when_no_target_is_available() -> None:
    from master.app import MasterRuntimeLoop

    class FakeUart:
        def __init__(self, lines=None):
            self.lines = list(lines or [])
            self.writes = []

        def read_line(self):
            if not self.lines:
                return None
            return self.lines.pop(0)

        def write_line(self, payload):
            self.writes.append(payload)

    uart6 = FakeUart(["vision=1,camera_id=cam_a,seq=1,valid=0,target=follower"])
    uart8 = FakeUart()
    uart3 = FakeUart()

    loop = MasterRuntimeLoop({"uart6": uart6, "uart8": uart8, "uart3": uart3})
    result = loop.step(now_ms=100)

    assert result["assistant_command"] == "follow=1,seq=1,valid=0,dx=0.000,dy=0.000"
    assert uart3.writes == ["follow=1,seq=1,valid=0,dx=0.000,dy=0.000"]
