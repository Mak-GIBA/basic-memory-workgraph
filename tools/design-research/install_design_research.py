#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import stat
import subprocess
import sys
import tempfile
import uuid
import zlib

NAME = "design-research"
OWNER = "basic-memory-workgraph/design-research"
VERSION = "2.0.0"
MANIFEST = ".design-research-install.json"
PAYLOAD_MARKER = b"\n__DESIGN_RESEARCH_PAYLOAD__\n"
PAYLOAD_SHA256 = "__PAYLOAD_SHA256__"
REQUIRED_FILES = frozenset({
    "SKILL.md", "scripts/research.py", "scripts/literature.py", "scripts/dossier.py",
    "scripts/gan-harness.sh", "scripts/harness.py", "scripts/runtime.py",
    "scripts/evidence.py", "scripts/report.py", "references/evidence-format.md"
})

class InstallError(Exception):
    pass

def fail(message: str) -> None:
    raise InstallError(message)

def safe_path(path: Path) -> Path:
    """Reject symlinks in existing path components instead of resolving through them."""
    path = Path(os.path.abspath(path.expanduser()))
    for node in [*reversed(path.parents), path]:
        if node.is_symlink():
            fail(f"Refusing symlink path: {node}")
        if node.exists() and node != path and not node.is_dir():
            fail(f"Not a directory: {node}")
    return path

def load_payload(installer: Path) -> tuple[dict, dict[str, bytes]]:
    try:
        raw = installer.read_bytes()
    except OSError as exc:
        fail(f"Cannot read installer: {exc}")
    if PAYLOAD_MARKER not in raw:
        fail("Embedded payload marker is missing; installer may be truncated.")
    encoded = b"".join(raw.split(PAYLOAD_MARKER, 1)[1].split())
    try:
        compressed = base64.b64decode(encoded, validate=True)
    except Exception:
        fail("Embedded payload is not valid base64.")
    if hashlib.sha256(compressed).hexdigest() != PAYLOAD_SHA256:
        fail("Embedded payload checksum mismatch; restore a clean installer copy.")
    try:
        payload = json.loads(zlib.decompress(compressed).decode("utf-8"))
    except Exception:
        fail("Embedded payload cannot be decoded.")
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        fail("Unsupported embedded payload schema.")
    if payload.get("name") != NAME or payload.get("version") != VERSION:
        fail("Embedded payload identity/version mismatch.")
    raw_files = payload.get("files")
    if not isinstance(raw_files, dict) or not REQUIRED_FILES.issubset(raw_files):
        fail("Embedded skill payload is incomplete.")
    decoded: dict[str, bytes] = {}
    for rel, meta in raw_files.items():
        if not isinstance(rel, str) or not rel or rel.startswith("/") or ".." in Path(rel).parts or "\\" in rel:
            fail(f"Unsafe embedded path: {rel!r}")
        if not isinstance(meta, dict) or not isinstance(meta.get("sha256"), str) or not isinstance(meta.get("data_b64"), str):
            fail(f"Invalid embedded metadata for {rel}")
        try:
            data = base64.b64decode(meta["data_b64"], validate=True)
        except Exception:
            fail(f"Invalid embedded file encoding: {rel}")
        if hashlib.sha256(data).hexdigest() != meta["sha256"]:
            fail(f"Embedded file checksum mismatch: {rel}")
        if meta.get("mode") not in (0o644, 0o755):
            fail(f"Unsupported embedded file mode: {rel}")
        decoded[rel] = data
    return payload, decoded

def tree_hashes(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir() or root.is_symlink():
        fail(f"Expected a real directory: {root}")
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if "__pycache__" in rel.parts or path.suffix == ".pyc":
            continue
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            fail(f"Refusing non-regular installed path: {path}")
        if path.is_file() and rel.as_posix() != MANIFEST:
            out[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out

def payload_hashes(payload: dict) -> dict[str, str]:
    return {rel: meta["sha256"] for rel, meta in payload["files"].items()}

def inspect_target(target: Path) -> dict:
    if not target.exists():
        return {"state": "absent", "target": str(target)}
    if not target.is_dir() or target.is_symlink():
        fail(f"Target is not a regular directory: {target}")
    marker = target / MANIFEST
    if marker.is_symlink():
        fail(f"Refusing symlink manifest: {marker}")
    try:
        data = json.loads(marker.read_text("utf-8"))
    except (OSError, ValueError):
        return {"state": "unmanaged", "target": str(target)}
    if (not isinstance(data, dict) or data.get("owner") != OWNER or data.get("schema_version") != 1
            or not isinstance(data.get("files"), dict) or not data["files"]):
        return {"state": "unmanaged", "target": str(target)}
    actual = tree_hashes(target)
    return {"state": "installed", "target": str(target), "version": data.get("version"),
            "modified": actual != data["files"], "files": len(actual)}

@contextlib.contextmanager
def install_lock(root: Path):
    lock = root / ".design-research-install.lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        fail(f"Install lock exists: {lock}. Verify that no installer is running before removing a stale lock.")
    try:
        (lock / "owner.json").write_text(json.dumps({"pid": os.getpid(), "started": dt.datetime.now(dt.timezone.utc).isoformat()}), "utf-8")
        yield
    finally:
        shutil.rmtree(lock, ignore_errors=True)

def backup_location(root: Path) -> Path:
    key = hashlib.sha256(str(root / NAME).encode()).hexdigest()[:12]
    base = safe_path(root.parent / ".design-research-backups" / key)
    if base == root or root in base.parents:
        fail("Backup directory would overlap the skill root.")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return base / f"{stamp}-{uuid.uuid4().hex[:10]}"

def write_payload(stage: Path, payload: dict, decoded: dict[str, bytes]) -> None:
    for rel, data in decoded.items():
        dest = stage / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        dest.chmod(payload["files"][rel]["mode"])
    if tree_hashes(stage) != payload_hashes(payload):
        fail("Staged files failed integrity verification.")

def perform(root: Path, payload: dict, decoded: dict[str, bytes], *, update=False, force=False, uninstall=False, dry_run=False) -> dict:
    root = safe_path(root)
    target = safe_path(root / NAME)
    if root.exists() and not root.is_dir():
        fail("Skill root must be a directory.")
    state = inspect_target(target)
    if state["state"] == "unmanaged":
        fail("An unmanaged design-research path already exists; it will not be overwritten, even with --force.")
    if uninstall and state["state"] == "absent":
        return {**state, "action": "skip", "reason": "not installed"}
    if state["state"] == "installed" and not (update or force or uninstall):
        if state.get("version") == VERSION and not state.get("modified"):
            return {**state, "action": "skip", "reason": "already installed"}
        return {**state, "action": "skip", "reason": "use --update to replace managed files"}
    if state.get("modified") and not force:
        fail("Installed files contain local edits. Review them; --force permits a backed-up replacement/removal of managed files only.")
    action = "uninstall" if uninstall else ("update" if state["state"] == "installed" else "install")
    backup = backup_location(root) if state["state"] == "installed" else None
    if dry_run:
        return {**state, "action": action, "dry_run": True, "backup": str(backup) if backup else None,
                "network": False, "config_changes": False}
    root.mkdir(parents=True, exist_ok=True)
    with install_lock(root):
        if inspect_target(target) != state:
            fail("Install target changed during preflight; retry after reviewing it.")
        if backup:
            backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            before = tree_hashes(target)
            shutil.copytree(target, backup)
            if tree_hashes(target) != before or tree_hashes(backup) != before:
                fail("Destination changed during backup; original files were preserved.")
        previous_live = root / (".design-research-old-" + uuid.uuid4().hex)
        stage = None if uninstall else Path(tempfile.mkdtemp(prefix=".design-research-stage-", dir=root))
        moved_old = False
        try:
            if not uninstall:
                write_payload(stage, payload, decoded)
                manifest = {"owner": OWNER, "schema_version": 1, "version": VERSION,
                            "installed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                            "files": payload_hashes(payload), "installer": "single-file"}
                (stage / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
            if backup:
                # Atomic swap/rollback remains on the destination filesystem.
                os.replace(target, previous_live)
                moved_old = True
            try:
                if not uninstall:
                    os.replace(stage, target)
            except BaseException:
                if moved_old and not target.exists():
                    os.replace(previous_live, target)
                raise
            if moved_old:
                shutil.rmtree(previous_live)
        finally:
            if stage is not None and stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
        if uninstall:
            return {"action": "uninstall", "target": str(target), "backup": str(backup)}
    return {"action": action, "target": str(target), "version": VERSION,
            "backup": str(backup) if backup else None, "network": False, "config_changes": False}

def extract_payload(destination: Path, payload: dict, decoded: dict[str, bytes]) -> dict:
    destination = safe_path(destination)
    if destination.exists() and any(destination.iterdir()):
        fail("--extract destination must be absent or empty.")
    destination.mkdir(parents=True, exist_ok=True)
    write_payload(destination, payload, decoded)
    return {"action": "extract", "destination": str(destination), "files": len(decoded)}

def doctor(root: Path) -> dict:
    codex = shutil.which("codex")
    checks = {"codex_cli": bool(codex), "structured_exec": False, "sandbox": False}
    errors = []
    if codex:
        try:
            r = subprocess.run([codex, "exec", "--help"], capture_output=True, text=True, timeout=20)
            checks["structured_exec"] = r.returncode == 0 and all(
                v in r.stdout for v in ("--json", "--output-schema", "--output-last-message", "--sandbox", "--ephemeral"))
            help_result = subprocess.run([codex, "sandbox", "--help"], capture_output=True, text=True, timeout=20)
            suffix = ["linux"] if "Commands:" in help_result.stdout and "linux" in help_result.stdout else []
            r = subprocess.run([codex, "-c", 'sandbox_mode="read-only"', "sandbox", *suffix,
                                "--", "/bin/true"], capture_output=True, text=True, timeout=15)
            checks["sandbox"] = r.returncode == 0
            if r.returncode:
                errors.append(r.stderr[-500:])
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(str(exc))
    installed = inspect_target(safe_path(root / NAME))
    integrity = installed["state"] == "installed" and not installed["modified"]
    harness_installed = integrity and installed.get("version") == VERSION and all(
        (root / NAME / name).is_file() for name in REQUIRED_FILES)
    if not harness_installed:
        errors.append("The current harness is not installed intact; install or use --update first.")
    return {"python": sys.version.split()[0], "supported_python": sys.version_info >= (3, 10),
            "codex_cli_found": codex is not None, "codex_cli": codex, "target": str(root / NAME),
            "installed": installed, "installed_integrity": integrity,
            "installed_harness_ready": harness_installed,
            "harness_environment_ready": all(checks.values()), "ready": harness_installed and all(checks.values()),
            "checks": checks, "errors": errors,
            "network_required_for_install": False, "mcp_configuration_modified": False,
            "semantic_scholar_key_present": bool(os.environ.get("SEMANTIC_SCHOLAR_API_KEY")),
            "crossref_mailto_present": bool(os.environ.get("CROSSREF_MAILTO")),
            "note": "The scholarly CLI works without Codex. Harness execution needs structured "
                    "Codex exec and a working command sandbox. Live research needs --allow-network."}

def run_self_test(payload: dict, decoded: dict[str, bytes]) -> dict:
    with tempfile.TemporaryDirectory(prefix="design-research-selftest-") as temp:
        base = Path(temp)
        root = base / "skills"
        first = perform(root, payload, decoded)
        if first.get("action") != "install":
            fail("Self-test install did not execute.")
        target = root / NAME
        if inspect_target(target).get("modified"):
            fail("Fresh install is unexpectedly modified.")
        for rel in (name for name in decoded if name.endswith(".py")):
            compile((target / rel).read_text("utf-8"), rel, "exec")
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.run([sys.executable, "-B", str(target / "scripts/research.py"), "providers"],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, env=env)
        if proc.returncode != 0 or '"no_required_mcp": true' not in proc.stdout:
            fail("Bundled research helper smoke test failed.")
        proc = subprocess.run(["bash", str(target / "scripts/gan-harness.sh"), "--help"],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, env=env)
        if proc.returncode or "research" not in proc.stdout:
            fail("Bundled harness Bash entry smoke test failed.")
        workspace_root = base / "workspace" / "docs" / "design-research"
        proc = subprocess.run([sys.executable, "-B", str(target / "scripts/research.py"), "init",
                               "--slug", "self-test", "--question", "Compare A and B", "--root", str(workspace_root)],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, env=env)
        if proc.returncode != 0 or not (workspace_root / "self-test" / ".internal" / "evidence.json").is_file():
            fail("Bundled workspace initializer smoke test failed.")
        skill_md = target / "SKILL.md"
        skill_md.write_text(skill_md.read_text("utf-8") + "\n<!-- self-test edit -->\n", "utf-8")
        try:
            perform(root, payload, decoded, update=True)
        except InstallError:
            pass
        else:
            fail("Self-test expected local-edit protection to reject update.")
        forced = perform(root, payload, decoded, update=True, force=True)
        if forced.get("action") != "update" or inspect_target(target).get("modified"):
            fail("Forced managed update failed in self-test.")
        removed = perform(root, payload, decoded, uninstall=True)
        if removed.get("action") != "uninstall" or target.exists():
            fail("Self-test uninstall failed.")
        return {"self_test": "passed", "version": VERSION, "network": False,
                "checks": ["payload", "install", "python_helpers", "harness_bash", "workspace_init", "edit_protection", "force_update", "uninstall"]}

def print_human_summary(result: dict) -> None:
    action = result.get("action")
    if action in {"install", "update"}:
        print("\nDesign Research installed.")
        print(f"  Skill: {result['target']}")
        print("  Invoke: use the design-research skill explicitly, e.g. '$design-research ...'")
        print("  Scholarly helper: <skill>/scripts/research.py providers")
        print("  GAN harness: bash <skill>/scripts/gan-harness.sh research|audit|run|resume|doctor")
        print("  Diagnose: bash " + shlex.quote(str(Path(result["target"]) / "scripts/gan-harness.sh")) +
              " doctor --project .")
        print("  Codex prompt: '$design-research インストール済みgan-harness.shで、目的に貢献するコアロジックを比較・検証して'")
        print("  Install performed no network access and did not modify MCP configuration.")
        print("  Start a new Codex session if the skill is not discovered in the current one.")
    elif action == "uninstall":
        print("\nDesign Research removed from the active skill directory.")
        print(f"  Backup: {result.get('backup')}")

def main(installer: Path, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Install the self-contained design-research Codex Skill (no companion files required).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:\n  bash install_design_research.sh\n  bash install_design_research.sh --dry-run\n  bash install_design_research.sh --self-test\n  bash install_design_research.sh --project /path/to/repo\n  bash install_design_research.sh --update\n  bash install_design_research.sh --uninstall\n  bash install_design_research.sh --extract /tmp/design-research-skill\n\nNew user scope: ~/.agents/skills/design-research\nNew project scope: PROJECT/.agents/skills/design-research\nExisting legacy placement is reused without duplicates.\nUse --skills-dir for another Agent Skills discovery directory.""",
    )
    dest = parser.add_mutually_exclusive_group()
    dest.add_argument("--skills-dir", type=Path, help="Explicit skill discovery directory")
    dest.add_argument("--project", type=Path, help="Install to PROJECT/.agents/skills; reuse existing legacy placement")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--update", action="store_true", help="Replace managed files; local edits require --force")
    mode.add_argument("--uninstall", action="store_true", help="Back up and remove this managed skill")
    mode.add_argument("--status", action="store_true", help="Inspect installation state")
    mode.add_argument("--doctor", action="store_true", help="Offline environment diagnostics")
    mode.add_argument("--self-test", action="store_true", help="Run offline tests in a temporary directory")
    mode.add_argument("--print-mcp-config", action="store_true", help="Print optional MCP examples; never register them")
    mode.add_argument("--extract", type=Path, metavar="DIR", help="Extract the embedded skill source for inspection")
    parser.add_argument("--force", action="store_true", help="Back up and replace edited MANAGED files (implies update)")
    parser.add_argument("--dry-run", action="store_true", help="Show planned install/update/uninstall without writing")
    parser.add_argument("--json", action="store_true", help="Print only machine-readable JSON")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        parser.error("Python 3.10+ is required")
    if args.force and (args.status or args.doctor or args.self_test or args.print_mcp_config or args.extract):
        parser.error("--force cannot be used with a read-only/extract operation")
    if args.dry_run and (args.self_test or args.extract or args.status or args.doctor or args.print_mcp_config):
        parser.error("--dry-run only applies to install/update/uninstall")
    payload, decoded = load_payload(installer)
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    if args.skills_dir:
        root = args.skills_dir
    else:
        candidates = ([args.project / ".agents/skills", args.project / ".codex/skills"] if args.project
                      else [Path.home() / ".agents/skills", codex_home / "skills", Path.home() / ".codex/skills"])
        candidates = list(dict.fromkeys(safe_path(p) for p in candidates))
        existing = [p for p in candidates if (p / NAME).exists() or (p / NAME).is_symlink()]
        if len(existing) > 1:
            fail("Multiple design-research locations exist; select the intended one with --skills-dir.")
        root = existing[0] if existing else candidates[0]
    try:
        root = safe_path(root)
        if args.self_test:
            result = run_self_test(payload, decoded)
        elif args.print_mcp_config:
            print(decoded["references/mcp-examples.toml"].decode("utf-8"), end="")
            return 0
        elif args.extract:
            result = extract_payload(args.extract, payload, decoded)
        elif args.doctor:
            result = doctor(root)
        elif args.status:
            result = inspect_target(safe_path(root / NAME))
        else:
            result = perform(root, payload, decoded, update=args.update or args.force,
                             force=args.force, uninstall=args.uninstall, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not args.json:
            print_human_summary(result)
        return 2 if args.doctor and not result["ready"] else 0
    except (InstallError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ERROR: installer path missing", file=sys.stderr)
        raise SystemExit(1)
    try:
        raise SystemExit(main(Path(sys.argv[1]).resolve(), sys.argv[2:]))
    except (InstallError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
