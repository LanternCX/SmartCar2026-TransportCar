"""Stage 3 设备观测执行器."""

import argparse
import subprocess
from dataclasses import dataclass


PROBE_LOCAL_PATH = "tools/device_observe_probe.py"
PROBE_REMOTE_PATH = ".agent/device_observe_probe.py"
TICK_MAX_US_LIMIT = 8000


@dataclass
class ObserveRunResult:
    """保存一次 Stage 3 设备观测执行结果."""

    status: str
    reason: str
    snapshots: dict


def build_probe_commands(port):
    """构造执行 Stage 3 探针所需的 mpy-cli 命令."""
    common = ["--port", port, "--no-interactive", "--yes"]
    return [
        ["mpy-cli", "plan", "--mode", "incremental"] + common,
        [
            "mpy-cli",
            "upload",
            "--local",
            PROBE_LOCAL_PATH,
            "--remote",
            PROBE_REMOTE_PATH,
        ]
        + common,
        ["mpy-cli", "run", "--path", PROBE_REMOTE_PATH] + common,
        ["mpy-cli", "delete", "--path", PROBE_REMOTE_PATH] + common,
    ]


def _parse_int(value):
    """将字符串安全转换为整数,失败时回退到 0."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def parse_probe_output(text):
    """解析设备观测探针输出并给出状态归因."""
    snapshots = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("OBSERVE "):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        token = parts[1]
        fields = {}
        for item in parts[2:]:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            fields[key] = value
        snapshots[token] = fields

    if "error" in snapshots:
        reason = snapshots["error"].get("reason", "probe error")
        return ObserveRunResult("probe_failed", reason, snapshots)

    if "tick" not in snapshots:
        return ObserveRunResult("probe_failed", "missing tick snapshot", snapshots)

    tick_snapshot = snapshots["tick"]
    overrun = _parse_int(tick_snapshot.get("overrun"))
    max_us = _parse_int(tick_snapshot.get("max_us"))

    if overrun > 0:
        return ObserveRunResult(
            "observe_failed", "tick overrun detected: %d" % overrun, snapshots
        )
    if max_us > TICK_MAX_US_LIMIT:
        return ObserveRunResult(
            "observe_failed", "tick max_us exceeds limit: %d" % max_us, snapshots
        )

    return ObserveRunResult("ok", "ok", snapshots)


def _run_command(command):
    """执行单条主机侧命令并采集输出."""
    return subprocess.run(command, capture_output=True, text=True, check=False)


def run_probe(port):
    """执行完整的 Stage 3 观测探针流程."""
    plan_cmd, upload_cmd, run_cmd, delete_cmd = build_probe_commands(port)

    plan_result = _run_command(plan_cmd)
    if plan_result.returncode != 0:
        reason = (
            plan_result.stderr.strip() or plan_result.stdout.strip() or "plan failed"
        )
        return ObserveRunResult("connect_failed", reason, {})

    upload_result = _run_command(upload_cmd)
    if upload_result.returncode != 0:
        reason = (
            upload_result.stderr.strip()
            or upload_result.stdout.strip()
            or "upload failed"
        )
        return ObserveRunResult("deploy_failed", reason, {})

    try:
        run_result = _run_command(run_cmd)
        if run_result.returncode != 0:
            reason = (
                run_result.stderr.strip() or run_result.stdout.strip() or "run failed"
            )
            return ObserveRunResult("probe_failed", reason, {})
        return parse_probe_output(run_result.stdout)
    finally:
        _run_command(delete_cmd)


def _print_result(result):
    """打印观测结果与快照摘要."""
    print("status=%s reason=%s" % (result.status, result.reason))
    for token, snapshot in result.snapshots.items():
        parts = []
        for key, value in snapshot.items():
            parts.append("%s=%s" % (key, value))
        line = ("%s %s" % (token, " ".join(parts))).rstrip()
        print(line)


def main(argv=None):
    """命令行入口."""
    parser = argparse.ArgumentParser(description="运行 Stage 3 设备观测探针")
    parser.add_argument("--port", required=True, help="mpy-cli 连接使用的串口")
    args = parser.parse_args(argv)

    result = run_probe(args.port)
    _print_result(result)
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
