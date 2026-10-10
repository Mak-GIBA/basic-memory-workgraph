#!/usr/bin/env python3
"""Build/check the standalone installer deterministically from reviewed source assets."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import zlib

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parents[1]/'install_codex_yomiyasu.sh'
HEADER = '''#!/usr/bin/env bash
# yomiyasu Japanese writing integration 2.0.0-proposal.1 — standalone.
# Default: dry-run. --update --apply migrates an owned 1.3.0 installation.
# --update --upstream-only --apply refreshes upstream without changing local rules.
# Python 3.10+; no npm/pip/sudo/hooks/AGENTS.md edits. Save to a file before running.
PY="${PYTHON_BIN:-}"
if [[ -z "$PY" ]]; then
  for candidate in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      PY="$candidate"; break
    fi
  done
fi
if [[ -z "$PY" ]] || ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
  printf '%s\\n' 'ERROR: Python 3.10+が必要です。PYTHON_BIN=/path/to/python3で指定できます。' >&2
  exit 2
fi
export PYTHONDONTWRITEBYTECODE=1
"$PY" -B - "$0" "$@" <<'YOMI_INSTALL_PY'
'''


def build() -> str:
    assets = {}
    for prefix, folder in [('', ROOT/'assets'), ('tests/', ROOT/'tests'), ('evals/', ROOT/'evals')]:
        for p in sorted(folder.rglob('*')):
            if p.is_symlink():
                raise ValueError('Symlink in source assets: '+str(p))
            if p.is_file() and '__pycache__' not in p.parts:
                assets[prefix+p.relative_to(folder).as_posix()] = p.read_text(encoding='utf-8')
    raw = zlib.compress(json.dumps(assets, ensure_ascii=False, sort_keys=True,
                                  separators=(',', ':')).encode(), 9)
    source = (ROOT/'installer.py').read_text(encoding='utf-8')
    source = source.replace("ASSET_B64 = '@ASSET_B64@'", 'ASSET_B64 = '+repr(base64.b64encode(raw).decode()))
    source = re.sub(r"^ASSET_SHA256 = '.*'$", 'ASSET_SHA256 = '+repr(hashlib.sha256(raw).hexdigest()), source, flags=re.M)
    source = source.replace("if __name__ == '__main__':\n    raise SystemExit(main())",
                            "if __name__ == '__main__':\n    SELF_SCRIPT = abs_path(sys.argv[1])\n    raise SystemExit(main(sys.argv[2:]))")
    compile(source, 'embedded-installer.py', 'exec')
    return HEADER+source.rstrip()+'\n\nYOMI_INSTALL_PY\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    generated = build()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding='utf-8') != generated:
            parser.exit(1, 'Standalone installer differs from maintained source. Rebuild it.\n')
        print('Standalone installer matches maintained source.')
    else:
        OUTPUT.write_text(generated, encoding='utf-8')
        print('Built '+str(OUTPUT))


if __name__ == '__main__':
    main()
