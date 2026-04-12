"""legacy 风格零漂校准脚本.

@file src/master/test/calibrate_gyro.py
"""

from seekfree import IMU660RX
import time

SAMPLE_COUNT = 2000
SAMPLE_INTERVAL_MS = 2
OFFSET_FILE = "/flash/gyro_offset.txt"


def format_offsets_text(offsets):
    return ",".join(["%.4f" % float(value) for value in tuple(offsets)[:6]])


def main(
    sample_count=SAMPLE_COUNT,
    sample_interval_ms=SAMPLE_INTERVAL_MS,
    file_path=OFFSET_FILE,
):
    imu = IMU660RX()
    totals = [0.0] * 6

    print("开始 legacy 风格 IMU 六轴零漂校准，请保持车辆静止")
    print(
        "sample_count=%d sample_interval_ms=%d"
        % (int(sample_count), int(sample_interval_ms))
    )

    for index in range(int(sample_count)):
        data = imu.read()
        for axis in range(6):
            totals[axis] += float(data[axis])
        if index == 0 or ((index + 1) % 200 == 0):
            print("progress=%d/%d" % (index + 1, int(sample_count)))
        time.sleep_ms(int(sample_interval_ms))

    offsets = tuple(total / float(sample_count) for total in totals)
    text = format_offsets_text(offsets)
    with open(file_path, "w") as handle:
        handle.write(text)

    print("offsets=%s" % text)
    print("saved=%s" % str(file_path))
    return text


if __name__ == "__main__":
    main()
