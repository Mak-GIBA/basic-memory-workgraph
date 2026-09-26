#!/usr/bin/env python3
"""Update an existing local installation from this checkout, without downloading code."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import tempfile

from configure_workgraph import prepare_configuration, read_object, write_file
from install_schemas import prepare_schemas
from workgraph_tools import no_symlink, yaml


def basic_memory_config():
    if os.environ.get("BASIC_MEMORY_CONFIG_DIR"):
        return Path(os.environ["BASIC_MEMORY_CONFIG_DIR"]) / "config.json"
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]) / "basic-memory/config.json"
    return Path.home() / ".basic-memory/config.json"


def resolve_installation(codex_dir, registry_path, project=None, memory_dir=None):
    codex_dir = no_symlink(codex_dir)
    config = read_object(codex_dir / "basic-memory.json")
    bm = config.get("basicMemory")
    if not isinstance(bm, dict):
        raise ValueError("No existing Basic Memory installation; run the installer first")
    selected = project if project is not None else bm.get("primaryProject")
    if not isinstance(selected, str) or not selected.strip():
        raise ValueError("The existing installation has no valid primaryProject")
    registry = read_object(no_symlink(registry_path))
    projects = registry.get("projects", {})
    if not isinstance(projects, dict) or selected not in projects:
        raise ValueError(f"Project is not registered locally: {selected}")
    entry = projects[selected]
    if isinstance(entry, str):  # Older Basic Memory registries used path strings.
        registered_path = entry
    elif isinstance(entry, dict) and entry.get("mode", "local") == "local":
        registered_path = entry.get("path")
    else:
        raise ValueError("Only existing local Basic Memory projects support this update path")
    if not isinstance(registered_path, str) or not registered_path.strip():
        raise ValueError("Registered project has no valid local path")
    registered = Path(registered_path).expanduser()
    if not registered.is_absolute():
        raise ValueError("Registered project path must be absolute")
    registered = no_symlink(registered)
    if memory_dir is not None and no_symlink(memory_dir) != registered:
        raise ValueError("MEMORY_DIR/--memory-dir does not match the registered project path")
    if not registered.is_dir():
        raise ValueError("Registered memory directory does not exist")
    return codex_dir, selected, registered


def apply_update(changes):
    """Preflight all targets and roll back files if a write fails; retain backups."""
    pending = []
    for path, content in changes:
        no_symlink(path)
        if path.exists() and not path.is_file():
            raise ValueError(f"Update target is not a regular file: {path}")
        original = path.read_bytes() if path.exists() else None
        if original == content.encode():
            continue
        permissions = stat.S_IMODE(path.stat().st_mode) if original is not None else None
        pending.append((path, content, original, permissions))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    touched = []
    try:
        for path, content, original, permissions in pending:
            current = path.read_bytes() if path.exists() else None
            if current != original:
                raise ValueError("Update target changed during installation; retry after other writers finish")
            touched.append((path, original, permissions))
            write_file(path, content, stamp)
    except (OSError, ValueError):
        for path, original, permissions in reversed(touched):
            if original is None:
                path.unlink(missing_ok=True)
            else:
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(original)
                try:
                    temporary.chmod(permissions)
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
        raise
    return [str(path) for path, _, _, _ in pending]


def update(args):
    if yaml is None:
        raise ValueError("--update requires PyYAML; install requirements-export.txt in the Python environment")
    codex, project, memory = resolve_installation(
        args.codex_dir, args.basic_memory_config, args.project, args.memory_dir)
    # All parsing/validation precedes mutation, including malformed hook settings.
    config_changes, message = prepare_configuration(
        codex, project, args.mode, args.case_mode, args.skill_mode)
    schema_changes, preserved = prepare_schemas(memory)
    changes = config_changes + schema_changes
    for path, _ in changes:
        no_symlink(path)
        if path.exists() and not path.is_file():
            raise ValueError(f"Update target is not a regular file: {path}")
    changed = [str(path) for path, content in changes
               if not path.exists() or path.read_bytes() != content.encode()]
    if not args.dry_run:
        changed = apply_update(changes)
    return {"dry_run": args.dry_run, "project": project, "memory_dir": str(memory),
            "configuration": message, "changed": changed, "preserved": preserved}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-dir", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--basic-memory-config", type=Path, default=basic_memory_config())
    parser.add_argument("--project", default=os.environ.get("MEMORY_PROJECT"))
    parser.add_argument("--memory-dir", type=Path, default=os.environ.get("MEMORY_DIR"))
    parser.add_argument("--mode", default=os.environ.get("BM_AUTO_MODE"))
    parser.add_argument("--case-mode", default=os.environ.get("BM_CASE_MODE"))
    parser.add_argument("--skill-mode", default=os.environ.get("BM_SKILL_MODE"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = update(args)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        parser.exit(1, f"Update failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["preserved"]:
        parser.exit(2)


if __name__ == "__main__":
    main()
