#!/usr/bin/env python3
"""Install policy and hooks without touching Basic Memory projects or notes."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import tempfile


SOURCE = Path(__file__).resolve().parent
MANAGED_HOOKS = (
    "basic_memory_recall.py", "basic_memory_auto_remember.py",
    "basic_memory_workgraph_recall.py", "basic_memory_workgraph_save.py",
    "basic_memory_workgraph.py",
)


def read_object(path):
    value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def write_file(path, content, stamp):
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak." + stamp))
    # Replace each file atomically, including when a hook reads it during setup.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(content)
        temporary = Path(tmp.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def configure(codex_dir, project=None, mode=None):
    policy = (SOURCE / "memory-policy.md").read_text(encoding="utf-8").strip()
    hook_source = (SOURCE / "hooks/basic_memory_workgraph.py").read_text(encoding="utf-8")
    if not policy:
        raise ValueError("Empty memory policy")
    config_path = codex_dir / "basic-memory.json"
    hooks_path = codex_dir / "hooks.json"
    auto_dir = codex_dir / "basic-memory-workgraph"
    config = read_object(config_path)
    hook_config = read_object(hooks_path)
    auto_config = read_object(auto_dir / "config.json")
    bm = config.setdefault("basicMemory", {})
    hooks = hook_config.setdefault("hooks", {})
    if not isinstance(bm, dict) or not isinstance(hooks, dict):
        raise ValueError("basicMemory and hooks must be objects")
    selected_project = project if project is not None else bm.get("primaryProject", "codex-memory")
    selected_mode = mode if mode is not None else auto_config.get("mode", "smart")
    if not isinstance(selected_project, str) or not selected_project.strip():
        raise ValueError("primaryProject must be a nonempty string")
    if selected_mode not in ("smart", "always", "off"):
        raise ValueError("BM_AUTO_MODE must be smart, always, or off")

    bm["primaryProject"] = selected_project
    for key, value in {
        "secondaryProjects": [], "teamProjects": {}, "rememberFolder": "corrections",
        "recallTimeframe": "365d", "captureEvents": True, "sessionProfile": "general",
    }.items():
        bm.setdefault(key, value)
    bm["checkpointOnCompact"] = False
    bm["placementConventions"] = policy
    auto_config["mode"] = selected_mode

    # Remove only our command entries, preserving siblings and group metadata.
    for event in ("UserPromptSubmit", "Stop"):
        kept = []
        for group in hooks.get(event, []):
            remaining = [entry for entry in group.get("hooks", []) if not any(
                name in entry.get("command", "") for name in MANAGED_HOOKS
            )]
            if remaining:
                kept.append({**group, "hooks": remaining})
        hooks[event] = kept
    hook_path = codex_dir / "hooks/basic_memory_workgraph.py"
    for event, action, message in (
        ("UserPromptSubmit", "recall", "Searching Basic Memory Work Knowledge Graph"),
        ("Stop", "save", "Evaluating reusable Basic Memory knowledge"),
    ):
        hooks[event].append({"hooks": [{
            "type": "command", "command": "python3 " + shlex.quote(str(hook_path)) + " " + action,
            "timeout": 10, "statusMessage": message,
        }]})
    hook_config.setdefault("description", "User hooks including Basic Memory Work Knowledge Graph")

    # Validate and prepare all content before changing any existing file.
    dumps = lambda value: json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    changes = [
        (auto_dir / "memory-policy.md", policy + "\n"),
        (auto_dir / "config.json", dumps(auto_config)),
        (config_path, dumps(config)),
        (hook_path, hook_source),
        (hooks_path, dumps(hook_config)),
    ]
    # Already-running sessions may still have the previous command paths cached.
    for action in ("recall", "save"):
        legacy = codex_dir / "hooks" / f"basic_memory_workgraph_{action}.py"
        if legacy.exists():
            wrapper = (
                "#!/usr/bin/env python3\n"
                "import sys\nfrom basic_memory_workgraph import main\n\n"
                "if __name__ == '__main__':\n"
                f"    sys.argv[1:] = [{action!r}]\n    main()\n"
            )
            changes.append((legacy, wrapper))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    for path, content in changes:
        write_file(path, content, stamp)
    print(f"Configured {codex_dir}: project={selected_project}, mode={selected_mode}, checkpointOnCompact=false")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-dir", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--project", default=os.environ.get("MEMORY_PROJECT"))
    parser.add_argument("--mode", default=os.environ.get("BM_AUTO_MODE"))
    args = parser.parse_args()
    try:
        configure(args.codex_dir.expanduser().resolve(), args.project, args.mode)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        parser.exit(1, f"Configuration failed: {exc}\n")


if __name__ == "__main__":
    main()
