#!/usr/bin/env bash
set -euo pipefail

MPY_CLI="${MPY_CLI:-mpy-cli}"
MODE="${1:-incremental}"

case "${MODE}" in
  incremental)
    "${MPY_CLI}" deploy --mode incremental --base master --no-interactive --yes
    ;;
  full)
    "${MPY_CLI}" deploy --mode full --no-interactive --yes
    ;;
  *)
    echo "Usage: bash build.sh [full]" >&2
    echo "Default: incremental deploy based on master" >&2
    exit 2
    ;;
esac
