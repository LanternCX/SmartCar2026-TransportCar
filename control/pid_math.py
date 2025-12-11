def hardness_factor(name):
    if name == "soft":
        return 4.0
    if name == "hard":
        return 1.0
    if name == "hard2":
        return 0.5
    if name == "hard3":
        return 0.05
    return 2.0


def clamp(val, lo, hi):
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val


def compute_pi_from_id(gain, tau, hardness_name, kp_max, ki_max, gain_boost):
    lam = tau * hardness_factor(hardness_name)
    kp = (tau / (gain * lam)) * gain_boost
    ki = (1.0 / (gain * lam)) * gain_boost
    return clamp(kp, 0.0, kp_max), clamp(ki, 0.0, ki_max)


def incremental_pi(state, target, dt_s, max_duty):
    err = target - state["filtered_speed"]
    du = state["kp"] * (err - state["prev_err"]) + state["ki"] * err * dt_s
    duty = clamp(state["duty"] + du, -max_duty, max_duty)
    state["prev_err"] = err
    state["duty"] = duty
    return duty


def reset_pi_state(states):
    for state in states:
        state["duty"] = 0.0
        state["prev_err"] = 0.0
