#!/usr/bin/env python3
"""Deterministically embed the maintained upgrade sources in both bootstraps."""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent


def bundle():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(ROOT.rglob("*")):
            if path.is_symlink():
                raise ValueError("Refusing linked package source: " + str(path))
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            info = zipfile.ZipInfo("codex_interface_upgrade/" + path.relative_to(ROOT).as_posix(),
                                   date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, path.read_bytes(), compresslevel=9)
    return buffer.getvalue()


def render(component, data):
    template = (ROOT / "bootstrap.py").read_text("utf-8")
    template = template.replace("@COMPONENT@", component).replace("@BUNDLE_SHA256@", hashlib.sha256(data).hexdigest())
    encoded = base64.b64encode(data).decode("ascii")
    return ("#!/usr/bin/env bash\n# Managed research workflow assembly; generated from tools/design-research-upgrade.\n"
            "set -euo pipefail\n" + '"${PYTHON_BIN:-python3}" -B - "$0" "$@" <<\'CODEX_RESEARCH_BOOTSTRAP\'\n' +
            template + "CODEX_RESEARCH_BOOTSTRAP\nexit $?\n__CODEX_RESEARCH_BUNDLE__\n" +
            "\n".join(encoded[i:i+100] for i in range(0, len(encoded), 100)) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT.parents[1])
    args = parser.parse_args()
    data = bundle()
    for component, name in (("design-research", "install_design_research.sh"), ("upstream", "install_speckit_upstream.sh")):
        path = args.out / name
        expected = render(component, data)
        if args.check:
            if not path.is_file() or path.read_bytes() != expected:
                raise SystemExit("Stale bootstrap: " + str(path))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
            path.chmod(0o755)


if __name__ == "__main__":
    main()
