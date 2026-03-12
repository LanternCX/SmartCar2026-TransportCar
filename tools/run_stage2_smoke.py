"""Stage 2 裸片 smoke 执行器."""

import argparse
import ast
import subprocess
import time
from dataclasses import dataclass


PROBE_LOCAL_PATH = "tools/stage2_smoke_probe.py"
PROBE_REMOTE_PATH = ".agent/stage2_smoke_probe.py"
REQUIRED_SNAPSHOTS = ("health", "tick", "imu", "enc", "motor", "vision")
SETTLE_DELAY_S = 0.3


@dataclass
class Stage2RunResult:
    """保存一次 Stage 2 执行结果."""

    status: str
    reason: str
    details: dict


def build_probe_commands(port):
    """构造执行 Stage 2 探针所需的 mpy-cli 命令."""
    common = ["--port", port, "--no-interactive", "--yes"]
    return [
        ["mpy-cli", "plan", "--mode", "incremental"] + common,
        ["mpy-cli", "deploy", "--mode", "incremental"] + common,
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


def _parse_stage2_line(line, details):
    """解析单条 Stage 2 输出行并累积到 details."""
    payload = line[len("STAGE2 ") :].strip()
    if not payload:
        return

    parts = payload.split()
    first = parts[0]
    fields = {}

    if "=" in first:
        token, value = first.split("=", 1)
        fields[token] = value
        details[token] = fields
        items = parts[1:]
    else:
        token = first
        details[token] = fields
        items = parts[1:]

    for item in items:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        fields[key] = value


def parse_probe_output(text):
    """解析 Stage 2 probe 输出并给出状态归因."""
    details = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("STAGE2 "):
            _parse_stage2_line(line, details)

    status_fields = details.get("status")
    if status_fields is None:
        summary = _parse_summary_dict_output(text)
        if summary is not None:
            return _build_result_from_summary_dict(summary)
    if status_fields is None:
        return Stage2RunResult("probe_failed", "missing stage2 status", details)

    if status_fields.get("status") == "fail":
        return Stage2RunResult(
            "probe_failed", status_fields.get("reason", "stage2 failed"), details
        )

    smoke_fields = details.get("smoke")
    if smoke_fields is None:
        return Stage2RunResult("probe_failed", "missing smoke summary", details)
    mode = smoke_fields.get("mode", "full")
    if smoke_fields.get("queries") != "1":
        return Stage2RunResult("probe_failed", "stage2 query chain failed", details)

    if mode == "full":
        if smoke_fields.get("init") != "1":
            return Stage2RunResult("probe_failed", "stage2 init failed", details)
        if smoke_fields.get("step") != "1":
            return Stage2RunResult("probe_failed", "stage2 step failed", details)

        snapshot_text = smoke_fields.get("snapshots", "")
        snapshot_tokens = tuple(token for token in snapshot_text.split(";") if token)
        missing_snapshots = [
            token for token in REQUIRED_SNAPSHOTS if token not in snapshot_tokens
        ]
        if missing_snapshots:
            return Stage2RunResult(
                "probe_failed",
                "missing snapshots: %s" % ";".join(missing_snapshots),
                details,
            )
    elif mode == "lite":
        if smoke_fields.get("init") != "0":
            return Stage2RunResult(
                "probe_failed", "stage2 lite init must be 0", details
            )
        if smoke_fields.get("step") != "0":
            return Stage2RunResult(
                "probe_failed", "stage2 lite step must be 0", details
            )
        snapshot_text = smoke_fields.get("snapshots", "none")
        if snapshot_text not in ("", "none"):
            return Stage2RunResult(
                "probe_failed", "stage2 lite snapshots must be none", details
            )
    else:
        return Stage2RunResult(
            "probe_failed", "unknown stage2 mode: %s" % mode, details
        )

    query_fields = details.get("queries")
    if query_fields is not None and query_fields.get("missing") not in (None, "none"):
        return Stage2RunResult(
            "probe_failed",
            "missing queries: %s" % query_fields.get("missing"),
            details,
        )

    return Stage2RunResult("ok", "ok", details)


def _parse_summary_dict_output(text):
    """尝试解析板端直接打印的 summary dict."""
    candidates = []
    stripped = text.strip()
    if stripped:
        candidates.append(stripped)
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if candidate:
            candidates.append(candidate)

    for candidate in candidates:
        if not candidate.startswith("{"):
            continue
        try:
            summary = ast.literal_eval(candidate)
        except Exception:
            continue
        if isinstance(summary, dict):
            return summary
    return None


def _build_result_from_summary_dict(summary):
    """将 summary dict 适配为 Stage 2 结果对象."""
    details = {
        "status": {
            "status": "ok" if summary.get("status") == "ok" else "fail",
            "reason": str(summary.get("reason", "ok")),
        },
        "queries": {
            "count": str(int(summary.get("query_count", 0))),
            "missing": "none"
            if not summary.get("missing_queries")
            else ";".join(summary.get("missing_queries", [])),
        },
        "smoke": {
            "mode": str(summary.get("transport_mode", "lite")),
            "init": str(int(summary.get("init_ok", 0))),
            "queries": str(int(summary.get("query_ok", 0))),
            "step": str(int(summary.get("step_ok", 0))),
            "tick_count": str(int(summary.get("tick_count", 0))),
            "snapshots": "none"
            if not summary.get("snapshots")
            else ";".join(summary.get("snapshots", {}).keys()),
        },
    }
    if summary.get("status") != "ok":
        return Stage2RunResult(
            "probe_failed", str(summary.get("reason", "stage2 failed")), details
        )
    return Stage2RunResult("ok", "ok", details)


def _run_command(command):
    """执行单条主机侧命令并采集输出."""
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _is_incremental_delete_miss(result):
    """判断 deploy 失败是否仅由增量删除不存在文件导致."""
    if result.returncode == 0:
        return False

    text = "%s\n%s" % (result.stdout or "", result.stderr or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False

    summary_delete_lines = [line for line in lines if line.startswith("- delete ")]
    if summary_delete_lines:
        for line in summary_delete_lines:
            if "No such file or directory" not in line:
                return False
        return True

    saw_delete_miss = False
    for index, line in enumerate(lines):
        if "删除失败" not in line:
            continue
        window = " ".join(lines[index : index + 4])
        if "No such file or directory" not in window:
            return False
        saw_delete_miss = True
    return saw_delete_miss


def run_probe(port):
    """执行完整的 Stage 2 裸片 smoke 流程."""
    plan_cmd, deploy_cmd, upload_cmd, run_cmd, delete_cmd = build_probe_commands(port)

    plan_result = _run_command(plan_cmd)
    if plan_result.returncode != 0:
        reason = (
            plan_result.stderr.strip() or plan_result.stdout.strip() or "plan failed"
        )
        return Stage2RunResult("connect_failed", reason, {})

    deploy_result = _run_command(deploy_cmd)
    if deploy_result.returncode != 0 and not _is_incremental_delete_miss(deploy_result):
        reason = (
            deploy_result.stderr.strip()
            or deploy_result.stdout.strip()
            or "deploy failed"
        )
        return Stage2RunResult("deploy_failed", reason, {})
    time.sleep(SETTLE_DELAY_S)

    upload_result = _run_command(upload_cmd)
    if upload_result.returncode != 0:
        reason = (
            upload_result.stderr.strip()
            or upload_result.stdout.strip()
            or "upload failed"
        )
        return Stage2RunResult("deploy_failed", reason, {})
    time.sleep(SETTLE_DELAY_S)

    try:
        run_result = _run_command(run_cmd)
        if run_result.returncode != 0:
            reason = (
                run_result.stderr.strip() or run_result.stdout.strip() or "run failed"
            )
            return Stage2RunResult("probe_failed", reason, {})
        return parse_probe_output(run_result.stdout)
    finally:
        _run_command(delete_cmd)


def _print_result(result):
    """打印 Stage 2 结果与摘要."""
    print("status=%s reason=%s" % (result.status, result.reason))
    for token, fields in result.details.items():
        parts = []
        for key, value in fields.items():
            parts.append("%s=%s" % (key, value))
        line = ("%s %s" % (token, " ".join(parts))).rstrip()
        print(line)


def main(argv=None):
    """命令行入口."""
    parser = argparse.ArgumentParser(description="运行 Stage 2 裸片 smoke 探针")
    parser.add_argument("--port", required=True, help="mpy-cli 连接使用的串口")
    args = parser.parse_args(argv)

    result = run_probe(args.port)
    _print_result(result)
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
