#!/usr/bin/env bash
set -euo pipefail
DR_GAN_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "reassess" ]]; then
  shift
  exec "${PYTHON_BIN:-python3}" -B "$DR_GAN_SCRIPT_DIR/reassessment.py" "$@"
fi
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  printf "%s\n" "Additional mode: reassess --prior-run <state.json> --slug <new-topic> --brief <reason>"
fi
exec "${PYTHON_BIN:-python3}" -B "$DR_GAN_SCRIPT_DIR/harness.py" "$@"
