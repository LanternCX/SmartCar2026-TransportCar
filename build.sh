#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${MPY_CLI:-}" ]]; then
  MPY_CMD=("${MPY_CLI}")
else
  MPY_CMD=(uv run --group board mpy-cli)
fi
MODE="${1:-incremental}"

case "${MODE}" in
  incremental)
    "${MPY_CMD[@]}" deploy --mode incremental --base master --no-interactive --yes
    ;;
  full)
    "${MPY_CMD[@]}" deploy --mode full --no-interactive --yes
    ;;
  *)
    echo "Usage: bash build.sh [full]" >&2
    echo "Default: incremental deploy based on master" >&2
    exit 2
    ;;
esac
