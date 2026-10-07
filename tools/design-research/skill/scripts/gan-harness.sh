#!/usr/bin/env bash
set -euo pipefail
DR_GAN_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON_BIN:-python3}" -B "$DR_GAN_SCRIPT_DIR/harness.py" "$@"
