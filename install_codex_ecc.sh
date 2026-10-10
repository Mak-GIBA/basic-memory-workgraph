#!/usr/bin/env bash
# ECC native install + four on-demand entrypoints + selected independent MCPs.
# Requires this repository. Existing MCP settings are preserved.
# Default: offline preview. --apply installs/configures; --update --apply updates.
# --mcps recommended|research|browser|cloudflare|none or comma-separated names.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER="$SCRIPT_DIR/tools/ecc-on-demand/install_ecc.py"
command -v python3 >/dev/null || { printf '%s\n' 'ERROR: Python 3.11以降が必要です。' >&2; exit 2; }
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' || {
  printf '%s\n' 'ERROR: python3 は3.11以降である必要があります。' >&2; exit 2;
}
[[ -f "$INSTALLER" ]] || {
  printf '%s\n' 'ERROR: tools/ecc-on-demand/ を含むリポジトリ一式が必要です。' >&2; exit 2;
}
export PYTHONDONTWRITEBYTECODE=1
exec python3 -B "$INSTALLER" "$@"
