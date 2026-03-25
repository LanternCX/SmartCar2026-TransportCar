"""@brief 视觉状态机各状态动作计算 helper."""

import math

from vision.state_defs import SM
from vision.state_machine.types import clamp
from vision.transforms import normalize_angle


def handle_align_angle(machine, inputs, observation):
    x_error = observation.center_x - machine.config.target_center_x_px
    if abs(x_error) <= machine.config.angle_deadzone_px:
        machine._stable_counter += 1
        if machine._stable_counter >= machine.config.stable_frames:
            machine._set_state(SM.ALIGN_DIST.ANGLE_ALIGNED_STABLE, inputs, observation)
            machine._stable_counter = 0
        return machine._inactive_result()
    machine._stable_counter = 0
    d_angle = clamp(
        x_error * machine.config.angle_kp,
        -machine.config.max_d_angle_deg,
        machine.config.max_d_angle_deg,
    )
    return machine._active_result(0.0, 0.0, d_angle, False)


def handle_align_dist(machine, inputs, observation):
    x_error = observation.center_x - machine.config.target_center_x_px
    if abs(x_error) > machine.config.angle_reentry_px:
        machine._set_state(SM.ALIGN_ANGLE.ANGLE_ERROR_REENTRY, inputs, observation)
        machine._stable_counter = 0
        return machine._inactive_result()
    y_error = observation.bottom - machine.config.target_bottom_px
    if abs(y_error) <= machine.config.dist_deadzone_px:
        machine._stable_counter += 1
        if machine._stable_counter >= machine.config.stable_frames:
            machine._set_state(SM.ALIGN_DX.DISTANCE_ALIGNED_STABLE, inputs, observation)
            machine._stable_counter = 0
        return machine._inactive_result()
    machine._stable_counter = 0
    dy_body = clamp(
        -y_error * machine.config.dist_kp,
        -machine.config.max_dy_m,
        machine.config.max_dy_m,
    )
    return machine._active_result(0.0, dy_body, 0.0, False)


def handle_align_dx(machine, inputs, observation):
    x_error = observation.center_x - machine.config.target_center_x_px
    if abs(x_error) <= machine.config.dx_deadzone_px:
        machine._stable_counter += 1
        if machine._stable_counter >= machine.config.stable_frames:
            y_error = observation.bottom - machine.config.target_bottom_px
            heading_error = normalize_angle(
                machine.config.push_angle_deg - inputs.heading_deg
            )
            machine._stable_counter = 0
            if abs(y_error) > machine.config.dist_deadzone_px:
                machine._set_state(
                    SM.ALIGN_DIST.DISTANCE_NOT_READY, inputs, observation
                )
            elif abs(heading_error) <= machine.config.heading_tolerance_deg:
                machine._set_state(SM.PUSHING.ENTER_PUSHING, inputs, observation)
                machine.start_push(inputs.odom_x, inputs.odom_y)
            else:
                machine._set_state(SM.ORBITING.HEADING_NOT_READY, inputs, observation)
        return machine._inactive_result()
    machine._stable_counter = 0
    dx_body = clamp(
        x_error * machine.config.dx_kp,
        -machine.config.max_dx_m,
        machine.config.max_dx_m,
    )
    return machine._active_result(dx_body, 0.0, 0.0, False)


def handle_orbiting(machine, inputs, observation):
    heading_error = normalize_angle(machine.config.push_angle_deg - inputs.heading_deg)
    if abs(heading_error) <= machine.config.heading_tolerance_deg:
        machine._set_state(SM.ALIGN_DX.HEADING_ALIGNED, inputs, observation)
        return machine._inactive_result()
    d_angle = clamp(
        heading_error, -machine.config.max_d_angle_deg, machine.config.max_d_angle_deg
    )
    return machine._active_result(0.0, 0.0, d_angle, True)


def handle_pushing(machine, inputs, observation):
    distance = math.sqrt(
        (inputs.odom_x - machine._push_start_x) ** 2
        + (inputs.odom_y - machine._push_start_y) ** 2
    )
    if distance >= machine.config.push_distance_m:
        machine._set_state(SM.RETURNING.PUSH_DISTANCE_REACHED, inputs, observation)
        return machine._inactive_result()
    dx_body = 0.0
    if observation is not None:
        x_error = observation.center_x - machine.config.target_center_x_px
        dx_body = clamp(
            x_error * machine.config.push_dx_kp,
            -machine.config.max_dx_m,
            machine.config.max_dx_m,
        )
    heading_error = normalize_angle(machine.config.push_angle_deg - inputs.heading_deg)
    d_angle = clamp(
        heading_error, -machine.config.max_d_angle_deg, machine.config.max_d_angle_deg
    )
    return machine._active_result(dx_body, machine.config.push_dy_m, d_angle, False)


def handle_returning(machine, inputs, observation):
    return_angle = normalize_angle(machine.config.push_angle_deg + 180.0)
    heading_error = normalize_angle(return_angle - inputs.heading_deg)
    if abs(heading_error) <= machine.config.heading_tolerance_deg:
        machine._set_state(SM.DONE.RETURN_HEADING_REACHED, inputs, observation)
        machine._done_since_ms = inputs.now_ms
        return machine._inactive_result()
    d_angle = clamp(
        heading_error, -machine.config.max_d_angle_deg, machine.config.max_d_angle_deg
    )
    return machine._active_result(0.0, 0.0, d_angle, False)


def handle_done(machine, inputs, observation):
    if inputs.now_ms - machine._done_since_ms >= machine.config.done_hold_ms:
        machine._set_state(SM.IDLE.DONE_HOLD_ELAPSED, inputs, observation)
    return machine._inactive_result()
