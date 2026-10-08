#!/usr/bin/env python3
"""Build a deterministic one-file installer from the extracted companion sources.

This embeds our Python/Markdown/test resources, NOT third-party SpecKit code.
Usage: python3 build_single.py /path/to/install_speckit_upstream.sh
"""
from __future__ import annotations
import argparse, base64, hashlib, io, os, sys, tempfile, textwrap, zipfile
from pathlib import Path

HEADER = r'''#!/usr/bin/env bash
# SpecKit Upstream Workbench 2.0.1 — single-file installer / Linux, WSL2
# Add THIS FILE ONLY to your repository. No sibling ZIP or scripts are required.
# Custom companion to official SpecKit. Does not alter ECC, Basic Memory, hooks,
# Codex config.toml, AGENTS.md, app sources, databases, or Git remotes.
#
# Usage:
#   bash install_speckit_upstream.sh --dry-run       # default; no persistent writes
#   bash install_speckit_upstream.sh --apply
#   bash install_speckit_upstream.sh --apply --update # upgrade unmodified owned files
#   bash install_speckit_upstream.sh --self-test     # offline mock-based tests
#   bash install_speckit_upstream.sh --extract /tmp/swb-source  # inspect all sources
#
# Requires Python 3.11+ (and python venv/pip when installing SpecKit).
# Set PYTHON_BIN=/absolute/path/python3.12 if needed. No sudo.
# Own assets are embedded below. Only absent SpecKit is fetched from PyPI
# as specify-cli==1.0.8 with its dependencies. --skip-specify makes setup offline.
# Integrity hash detects corruption; it does NOT authenticate the publisher.
# Run from a saved file rather than piping an unreviewed download into a shell.
set -euo pipefail
PY="${PYTHON_BIN:-}"
if [[ -z "$PY" ]]; then
  for candidate in python3 python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
      PY="$candidate"
      break
    fi
  done
fi
if [[ -z "$PY" ]] || ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
  printf '%s\n' 'ERROR: Python 3.11+ is required. Set PYTHON_BIN to a suitable interpreter.' >&2
  exit 2
fi
export PYTHONDONTWRITEBYTECODE=1
"$PY" - "$0" "$@" <<'SWB_BOOTSTRAP_PY'
import base64, hashlib, io, os, stat, subprocess, sys, tempfile, zipfile
from pathlib import Path, PurePosixPath

EXPECTED_SHA256 = "@DIGEST@"
MARKER = "\n: <<'SWB_EMBEDDED_RESOURCES_V1'\n"

def fail(message):
    print('ERROR: '+message,file=sys.stderr)
    raise SystemExit(2)

def validate_path(path):
    for p in [path,*path.parents]:
        if p.is_symlink():fail('symlink destination is not supported: '+str(p))

try:
    source=Path(sys.argv[1]).read_text(encoding='utf-8')
    if MARKER not in source:fail('embedded resource marker is missing')
    section=source.split(MARKER,1)[1]
    encoded=section.rsplit('\nSWB_EMBEDDED_RESOURCES_V1',1)[0]
    data=base64.b64decode(''.join(encoded.split()),validate=True)
    if hashlib.sha256(data).hexdigest()!=EXPECTED_SHA256:
        fail('embedded resource checksum mismatch; re-download the saved file')
    z=zipfile.ZipFile(io.BytesIO(data))
    names=set();total=0
    for item in z.infolist():
        name=item.filename;p=PurePosixPath(name)
        if name in names:fail('duplicate archive member')
        names.add(name)
        if not name or p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
            fail('unsafe archive member: '+name)
        if item.is_dir() or stat.S_ISLNK(item.external_attr>>16):fail('unexpected archive entry: '+name)
        if item.file_size>3_000_000:fail('oversized embedded file')
        total+=item.file_size
    if total>15_000_000 or len(names)>1000:fail('oversized embedded payload')
    if not {'install.py','swb.py','README_COMMANDS.md'}<=names:fail('incomplete embedded resources')
    args=sys.argv[2:]
    if '--help' in args or '-h' in args:
        print('Single-file global SpecKit upstream installer 2.0.1\n'
              '  --dry-run (default)          show installation plan\n'
              '  --apply                     apply global installation\n'
              '  --update                    update unmodified owned companion files only\n'
              '  --skip-specify              install companion assets only; no dependency fetch\n'
              '  --doctor                    diagnose global installation (read only)\n'
              '  --self-test                 offline unit tests; SpecKit boundary is mocked\n'
              '  --extract DIRECTORY         extract readable sources; do not install\n'
              '\nCodex commands after install:\n'
              '  $upstream-new / $upstream-existing / $upstream-change\n'
              '  $upstream-bug / $upstream-refactor / $upstream-check\n'
              '  $upstream-review / $upstream-approve\n'
              '\nOnly document structure is checked by CLI. Skill instructions are not access control.')
        raise SystemExit(0)
    if '--extract' in args:
        if len(args)!=2 or args[0]!='--extract':fail('use --extract DIRECTORY alone')
        target=Path(args[1]).expanduser().absolute();validate_path(target)
        if target.exists() and (not target.is_dir() or any(target.iterdir())):
            fail('extract destination must be missing or an empty directory')
        target.mkdir(parents=True,exist_ok=True)
        for item in z.infolist():
            dst=target/item.filename;validate_path(dst);dst.parent.mkdir(parents=True,exist_ok=True)
            with dst.open('xb') as f:f.write(z.read(item))
            dst.chmod(0o644)
        print('Extracted readable sources (no global install): '+str(target))
        print('Guide: '+str(target/'README_COMMANDS.md'))
        raise SystemExit(0)
    if '--self-test' in args and args!=['--self-test']:fail('use --self-test alone')
    if '--doctor' in args and args!=['--doctor']:fail('use --doctor alone')
    with tempfile.TemporaryDirectory(prefix='speckit-upstream-installer-') as directory:
        root=Path(directory)
        for item in z.infolist():
            dst=root/item.filename;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(z.read(item))
        if args==['--self-test']:
            print('Offline tests in isolated temporary HOME. SpecKit CLI is mocked.\n'
                  'This is NOT a real Codex/SpecKit end-to-end test.',flush=True)
            argv=[sys.executable,'-m','unittest','discover','-s','tests','-v']
        elif args==['--doctor']:
            argv=[sys.executable,str(root/'swb.py'),'doctor']
        else:
            argv=[sys.executable,str(root/'install.py'),*args]
        completed=subprocess.run(argv,cwd=root,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        raise SystemExit(completed.returncode)
except (OSError,ValueError,zipfile.BadZipFile,RuntimeError) as exc:
    fail(str(exc))
SWB_BOOTSTRAP_PY
exit 0
'''

def build(root: Path, output: Path):
    paths=[]
    for folder in ['workbench','assets','tests']:
        paths += [p for p in (root/folder).rglob('*') if p.is_file() and not p.is_symlink()
                  and '__pycache__' not in p.parts and p.suffix!='.pyc']
    paths += [root/n for n in ['install.py','swb.py','README_COMMANDS.md','LICENSE','build_single.py']]
    bio=io.BytesIO()
    with zipfile.ZipFile(bio,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(paths):
            info=zipfile.ZipInfo(p.relative_to(root).as_posix(),date_time=(2026,9,21,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(statmode() << 16)
            z.writestr(info,p.read_bytes())
    data=bio.getvalue();digest=hashlib.sha256(data).hexdigest()
    encoded='\n'.join(textwrap.wrap(base64.b64encode(data).decode(),100))
    text=HEADER.replace('@DIGEST@',digest)+"\n: <<'SWB_EMBEDDED_RESOURCES_V1'\n"+encoded+'\nSWB_EMBEDDED_RESOURCES_V1\n'
    output.write_text(text,encoding='utf-8');output.chmod(0o755)
    print(f'{output}: {output.stat().st_size} bytes, payload sha256={digest}, members={len(paths)}')

def statmode():return 0o100644

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',nargs='?',type=Path,default=Path('install_speckit_upstream.sh'))
    parser.add_argument('--check',action='store_true',help='Check the tracked installer without rewriting it')
    args=parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory(prefix='swb-build-check-') as temp:
            generated=Path(temp)/'installer.sh'
            build(Path(__file__).resolve().parent,generated)
            if not args.output.is_file() or generated.read_bytes()!=args.output.read_bytes():
                parser.exit(1,'SpecKit distribution differs from maintained sources\n')
        print('SpecKit distribution matches maintained sources')
    else:
        build(Path(__file__).resolve().parent,args.output.absolute())
