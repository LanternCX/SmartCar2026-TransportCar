import io


def save_pid_params(path, states, hardness):
    f = io.open(path, "w")
    try:
        f.write("hardness %s\n" % hardness)
        for state in states:
            gain = state.get("id_gain") or 0.0
            tau = state.get("id_tau") or 0.0
            kp = state.get("kp") or 0.0
            ki = state.get("ki") or 0.0
            f.write("%s %.6f %.6f %.6f %.6f\n" % (state["name"], gain, tau, kp, ki))
    finally:
        f.close()


def load_pid_params(path):
    meta = {"hardness": None, "params": {}}
    try:
        f = io.open(path, "r")
    except OSError:
        return meta

    try:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if parts[0] == "hardness" and len(parts) >= 2:
                meta["hardness"] = parts[1]
                continue
            if len(parts) >= 5:
                name = parts[0]
                gain = float(parts[1])
                tau = float(parts[2])
                kp = float(parts[3])
                ki = float(parts[4])
                meta["params"][name] = {
                    "gain": gain,
                    "tau": tau,
                    "kp": kp,
                    "ki": ki,
                }
    finally:
        f.close()

    return meta
