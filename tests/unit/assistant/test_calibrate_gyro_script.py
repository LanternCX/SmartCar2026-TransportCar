def test_calibrate_gyro_script_supports_direct_board_imports() -> None:
    from pathlib import Path

    content = Path("src/assistant/script/calibrate_gyro.py").read_text(encoding="utf-8")

    assert "from hw.imu import build_imu_bundle" in content


def test_calibrate_gyro_script_has_direct_run_guard() -> None:
    from pathlib import Path

    content = Path("src/assistant/script/calibrate_gyro.py").read_text(encoding="utf-8")

    assert 'if __name__ == "__main__"' in content


def test_calibrate_gyro_formats_six_axis_offsets() -> None:
    from assistant.script.calibrate_gyro import format_offsets_text

    text = format_offsets_text((1.0, 2.5, 3.0, 4.25, 5.0, 6.75))

    assert text == "1.0000,2.5000,3.0000,4.2500,5.0000,6.7500"


def test_calibrate_gyro_main_samples_and_saves_offsets(tmp_path, monkeypatch) -> None:
    import assistant.script.calibrate_gyro as script

    class FakeImuDevice:
        def __init__(self, samples):
            self.samples = list(samples)
            self.index = 0

        def read(self):
            sample = self.samples[min(self.index, len(self.samples) - 1)]
            self.index += 1
            return sample

    class FakeImuPort:
        def __init__(self):
            self.device = FakeImuDevice(
                [
                    (1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
                    (3.0, 4.0, 5.0, 6.0, 7.0, 8.0),
                ]
            )

        def ensure_device(self):
            return self.device

        def read_raw(self):
            return (-1.0, -1.0, -1.0, -1.0, -1.0, -1.0)

    monkeypatch.setattr(script, "_read_imu_port_builder", lambda: lambda: FakeImuPort())

    class FakeTime:
        @staticmethod
        def sleep_ms(_delay_ms):
            return None

    monkeypatch.setitem(__import__("sys").modules, "time", FakeTime)

    output_file = tmp_path / "gyro_offset.txt"
    text = script.main(sample_count=2, sample_interval_ms=1, file_path=str(output_file))

    assert text == "2.0000,3.0000,4.0000,5.0000,6.0000,7.0000"
    assert output_file.read_text(encoding="utf-8") == text
