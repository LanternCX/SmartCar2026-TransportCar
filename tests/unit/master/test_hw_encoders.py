def test_encoder_port_reads_fresh_count_each_time(monkeypatch) -> None:
    import sys
    import types

    from master.hw.encoders import EncoderPort

    class FakeEncoderDevice:
        def __init__(self) -> None:
            self.values = [0, 12, 34]
            self.index = 0

        def get(self):
            value = self.values[min(self.index, len(self.values) - 1)]
            self.index += 1
            return value

    device = FakeEncoderDevice()
    monkeypatch.setitem(
        sys.modules, "smartcar", types.SimpleNamespace(encoder=lambda *args: device)
    )

    port = EncoderPort("m", "D15", "D16", True)

    assert port.read() == 12
    assert port.read() == 34
