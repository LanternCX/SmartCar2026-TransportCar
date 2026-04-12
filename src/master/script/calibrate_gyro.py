"""主车零漂校准脚本.

@file src/master/script/calibrate_gyro.py
"""

_USE_DIRECT_IMPORTS = globals().get("__package__") in ("", None)

SAMPLE_COUNT = 2000
SAMPLE_INTERVAL_MS = 2
# `gyro_offset.txt` 保存六轴平均零漂, `main()` 写入后由 IMU 装配逻辑回读
OFFSET_FILE = "/flash/gyro_offset.txt"


def format_offsets_text(offsets):
    """把六轴零漂结果格式化成参数文件文本.

    @brief 输出逗号分隔格式, 方便板端直接写入 `gyro_offset.txt`。
    """

    return ",".join(["%.4f" % float(value) for value in tuple(offsets)[:6]])


def _read_imu_port_builder():
    if _USE_DIRECT_IMPORTS:
        from hw.imu import build_imu_bundle
    else:
        from master.hw.imu import build_imu_bundle
    return build_imu_bundle


def _sample_offsets(sample_count=SAMPLE_COUNT, sample_interval_ms=SAMPLE_INTERVAL_MS):
    """连续采样静止 IMU 并计算六轴平均零漂.

    @brief 校准脚本的核心阶段只做采样和平均, 不在这里处理文件写入。
    """

    import time

    imu_port = _read_imu_port_builder()()
    imu_device = imu_port.ensure_device()
    totals = [0.0] * 6

    print("开始主车 IMU 六轴零漂校准，请保持车辆静止")
    print(
        "sample_count=%d sample_interval_ms=%d"
        % (int(sample_count), int(sample_interval_ms))
    )

    for index in range(int(sample_count)):
        reader = getattr(imu_device, "read", None)
        if reader is not None:
            raw = tuple(reader())
        else:
            raw = imu_port.read_raw()
        for axis in range(6):
            totals[axis] += float(raw[axis])
        if index == 0 or ((index + 1) % 200 == 0):
            print("progress=%d/%d" % (index + 1, int(sample_count)))
        time.sleep_ms(int(sample_interval_ms))

    return tuple(total / float(sample_count) for total in totals)


def _save_offsets(offsets, file_path=OFFSET_FILE):
    text = format_offsets_text(offsets)
    with open(file_path, "w") as handle:
        handle.write(text)
    return text


def main(
    sample_count=SAMPLE_COUNT,
    sample_interval_ms=SAMPLE_INTERVAL_MS,
    file_path=OFFSET_FILE,
):
    """执行主车 IMU 零漂校准并保存结果.

    @brief 串联采样、写文件和控制台输出, 供板端单独运行这个校准脚本。
    """

    offsets = _sample_offsets(
        sample_count=sample_count, sample_interval_ms=sample_interval_ms
    )
    text = _save_offsets(offsets, file_path=file_path)
    print("offsets=%s" % text)
    print("saved=%s" % str(file_path))
    return text


if __name__ == "__main__":
    main()
