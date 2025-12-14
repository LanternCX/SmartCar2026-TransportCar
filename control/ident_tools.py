import math


def create_ident_buffers(names, max_samples):
    from array import array

    return {
        name: {
            "t": array("f", [0.0] * max_samples),
            "v": array("f", [0.0] * max_samples),
            "count": 0,
        }
        for name in names
    }


def push_ident_sample(name, t_ms, val, buf, max_samples=None):
    slot = buf[name]
    size = max_samples or len(slot["t"])
    idx = slot["count"] % size
    slot["t"][idx] = t_ms
    slot["v"][idx] = val
    slot["count"] += 1


def get_ident_samples(name, buf, max_samples=None):
    slot = buf[name]
    size = max_samples or len(slot["t"])
    n = min(slot["count"], size)
    if n == 0:
        return []
    start = (slot["count"] - n) % max_samples
    samples = []
    for i in range(n):
        idx = (start + i) % max_samples
        samples.append((slot["t"][idx], slot["v"][idx]))
    return samples


def identify_wheel(samples, step_duty):
    if not samples or step_duty == 0:
        return None, None

    tail = samples[-min(len(samples), 40) :]
    steady = sum(val for _, val in tail) / len(tail)
    gain = steady / step_duty if step_duty != 0 else 0.0
    if gain <= 0:
        return None, None

    target63 = steady * 0.632
    t0 = samples[0][0]
    tau = None

    for t_ms, val in samples:
        if val >= target63:
            tau = max((t_ms - t0) / 1000.0, 0.01)
            break

    if tau is None:
        xs = []
        zs = []
        for t_ms, val in samples:
            if val < steady and steady > 1e-6:
                x = (t_ms - t0) / 1000.0
                r = 1.0 - val / steady
                if r > 0.0:
                    xs.append(x)
                    zs.append(math.log(r))
        if xs:
            num = sum(x * z for x, z in zip(xs, zs))
            den = sum(x * x for x in xs)
            if den > 0 and num < 0:
                tau_est = -den / num
                tau = max(tau_est, 0.001)

    if tau is None:
        return None, None
    return gain, tau
