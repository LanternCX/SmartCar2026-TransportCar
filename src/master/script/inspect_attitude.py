"""主车姿态积分观察脚本.

@file src/master/script/inspect_attitude.py
"""

_USE_DIRECT_IMPORTS = globals().get("__package__") in ("", None)


def format_attitude_line(tick, quat, euler_deg, gyro_deg_s, dt_s):
    """把一拍姿态观察结果格式化成单行文本.

    @brief 统一脚本输出字段顺序, 便于串口观察和日志对比。
    """

    return (
        "tick=%d "
        "dt_s=%.6f "
        "quat=(%.6f,%.6f,%.6f,%.6f) "
        "roll_deg=%.3f pitch_deg=%.3f yaw_deg=%.3f "
        "gyro_deg_s=(%.3f,%.3f,%.3f)"
    ) % (
        int(tick),
        float(dt_s),
        float(quat[0]),
        float(quat[1]),
        float(quat[2]),
        float(quat[3]),
        float(euler_deg[0]),
        float(euler_deg[1]),
        float(euler_deg[2]),
        float(gyro_deg_s[0]),
        float(gyro_deg_s[1]),
        float(gyro_deg_s[2]),
    )


def normalize_gyro_deg_s(gyro_deg_s):
    """整理脚本展示使用的角速度三轴值.

    @brief 这里只做保留一位小数的展示处理, 不改变控制链内部计算精度。
    """

    return tuple(round(float(value), 1) for value in tuple(gyro_deg_s)[:3])


def main(max_ticks=200, tick_ms=10):
    """循环打印主车姿态积分观察结果.

    @brief 串联 IMU 采样、四元数积分和文本输出, 用于人工确认姿态链工作状态。
    """

    import time

    if _USE_DIRECT_IMPORTS:
        from ctrl.attitude import HeadingEstimator, estimator_euler_deg
        from hw.imu import build_imu_bundle
    else:
        from master.ctrl.attitude import HeadingEstimator, estimator_euler_deg
        from master.hw.imu import build_imu_bundle
    from smartcar import ticker

    imu_port = build_imu_bundle()
    imu_port.ensure_device()
    estimator = HeadingEstimator()
    capture_ticker = ticker(1)
    capture_ticker.capture_list(imu_port.ensure_device())
    capture_ticker.callback(lambda _ticker_obj: None)
    capture_ticker.start(int(tick_ms))
    last_time_us = time.ticks_us()

    try:
        tick = 0
        while True:
            tick += 1
            # 诊断脚本默认持续输出, 由外部手动停止, 不在脚本内部主动退出。
            # if int(max_ticks) > 0 and tick > int(max_ticks):
            #     break
            current_time_us = time.ticks_us()
            dt_s = time.ticks_diff(current_time_us, last_time_us) / 1000000.0
            last_time_us = current_time_us
            imu_calibrated = imu_port.read_calibrated()
            gx_deg_s, gy_deg_s, gz_deg_s = normalize_gyro_deg_s(
                (
                    float(imu_calibrated[3]) / 16.384,
                    float(imu_calibrated[4]) / 16.384,
                    float(imu_calibrated[5]) / 16.384,
                )
            )
            estimator.update(
                gx_deg_s,
                gy_deg_s,
                gz_deg_s,
                dt_s,
            )
            quat = (estimator.w, estimator.x, estimator.y, estimator.z)
            print(
                format_attitude_line(
                    tick=tick,
                    dt_s=dt_s,
                    quat=quat,
                    euler_deg=estimator_euler_deg(estimator),
                    gyro_deg_s=(gx_deg_s, gy_deg_s, gz_deg_s),
                )
            )
            time.sleep_ms(int(tick_ms))
    finally:
        capture_ticker.stop()

    return "inspect_attitude_done"


if __name__ == "__main__":
    main()
