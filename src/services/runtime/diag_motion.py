"""@brief 诊断 facade 的运动与日志快照构造器."""


def build_imu_snapshot(chassis_state):
    """@brief 返回 IMU 摘要快照.

    @param chassis_state 底盘状态 owner
    @return dict IMU 查询字段快照
    """
    yaw_rate = 0.0
    gz_raw = 0.0
    heading_est = 0.0
    imu_data = None
    if chassis_state is not None:
        yaw_rate = float(getattr(chassis_state, "yaw_rate", 0.0) or 0.0)
        gz_raw = float(getattr(chassis_state, "last_gz_raw", 0.0) or 0.0)
        heading_est = float(getattr(chassis_state, "heading_est", 0.0) or 0.0)
        imu_data = getattr(chassis_state, "imu_data", None)
    return {
        "ok": 1 if imu_data else 0,
        "yaw_deg": heading_est,
        "yaw_rate_dps": yaw_rate,
        "gz_raw": gz_raw,
    }


def build_encoder_snapshot(chassis_state):
    """@brief 返回编码器摘要快照.

    @param chassis_state 底盘状态 owner
    @return dict 编码器查询字段快照
    """
    snapshot = {}
    wheel_states = [] if chassis_state is None else (chassis_state.wheel_states or [])
    for state in wheel_states:
        name = state["name"]
        snapshot["%s_raw" % name] = float(state.get("raw_speed", 0.0))
        snapshot["%s_filt" % name] = float(state.get("filtered_speed", 0.0))
    return snapshot


def build_motor_snapshot(chassis_state, rear_only_mode: bool):
    """@brief 返回电机摘要快照.

    @param chassis_state 底盘状态 owner
    @param rear_only_mode 当前后轮模式标记
    @return dict 电机查询字段快照
    """
    snapshot = {}
    target_speeds = {} if chassis_state is None else (chassis_state.target_speeds or {})
    wheel_states = [] if chassis_state is None else (chassis_state.wheel_states or [])
    for state in wheel_states:
        name = state["name"]
        snapshot["%s_target" % name] = float(target_speeds.get(name, 0.0) or 0.0)
        snapshot["%s_duty" % name] = float(state.get("duty", 0.0))
    snapshot["rear"] = 1 if rear_only_mode else 0
    return snapshot


def build_pos_snapshot(chassis_state):
    """@brief 返回位置查询快照.

    @param chassis_state 底盘状态 owner
    @return dict 位置查询字段快照
    """
    odometry = getattr(chassis_state, "odometry", None)
    heading_est = float(getattr(chassis_state, "heading_est", 0.0) or 0.0)
    return {
        "x": float(0.0 if odometry is None else odometry.x),
        "y": float(0.0 if odometry is None else odometry.y),
        "heading_deg": heading_est,
    }


def build_lock_snapshot(command_lock: bool):
    """@brief 返回锁定状态快照.

    @param command_lock 当前命令锁状态
    @return dict 锁定状态查询字段快照
    """
    return {"locked": 1 if command_lock else 0}


def build_log_snapshot(logger_manager):
    """@brief 返回日志配置快照.

    @param logger_manager 日志配置 owner
    @return dict 日志查询字段快照
    """
    modules_text = "none"
    if logger_manager.filter_modules:
        modules_text = "|".join(logger_manager.filter_modules)
    return {
        "profile": logger_manager.profile_name.lower(),
        "level": logger_manager.level_name.lower(),
        "filter": logger_manager.filter_mode,
        "color": 1 if logger_manager.color_enabled else 0,
        "modules": modules_text,
    }
