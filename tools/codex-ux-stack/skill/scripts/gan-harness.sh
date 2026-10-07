#!/usr/bin/env bash
set -euo pipefail
UX_GAN_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$UX_GAN_SCRIPT_DIR/harness.py" "$@"
