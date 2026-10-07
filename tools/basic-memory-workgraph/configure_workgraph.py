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
SHARING_BEGIN = "<!-- basic-memory-github-sharing:begin -->"
SHARING_END = "<!-- basic-memory-github-sharing:end -->"
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


def prepare_configuration(codex_dir, project=None, mode=None, case_mode=None, skill_mode=None, correction_mode=None):
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
    for key, override, default, allowed in (
        ("caseMode", case_mode, "off", ("off", "reusable", "progressive")),
        ("correctionMode", correction_mode, "off", ("off", "scoped")),
        ("skillMode", skill_mode, "review", ("off", "review", "auto")),
    ):
        value = override if override is not None else auto_config.get(key, default)
        if value not in allowed:
            raise ValueError(f"{key} must be one of {', '.join(allowed)}")
        auto_config[key] = value

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
        entry = {"type": "command", "command": "python3 " + shlex.quote(str(hook_path)) + " " + action,
                 "timeout": 10}
        if action == "recall":
            entry["statusMessage"] = message
        hooks[event].append({"hooks": [entry]})
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
    # Reference documents are available to the agent without injecting them all
    # on every prompt. These are installation assets, not knowledge-graph notes.
    for source in sorted((SOURCE / "templates").rglob("*")):
        if source.is_file():
            changes.append((auto_dir / "templates" / source.relative_to(SOURCE / "templates"),
                            source.read_text(encoding="utf-8")))
    for name in ("workgraph_tools.py", "workgraph_sequence.py", "workgraph_github.py", "requirements-export.txt"):
        changes.append((auto_dir / name, (SOURCE / name).read_text(encoding="utf-8")))
    # This entrypoint applies only to explicit memory sharing requests. It never
    # grants sharing permission or schedules uploads from automatic save hooks.
    agents_path = codex_dir / "AGENTS.md"
    agents = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    workflow = auto_dir / "templates/GITHUB_SHARING.md"
    block = (SHARING_BEGIN + "\n"
             "メモリをGitHub経由で共有・送信・取り込み・更新する依頼では、作業前に\n"
             "次の手順書を読み、該当する手順だけを適用する。英語の同等表現も対象。\n"
             "『メモリを共有して』『共有メモリを取り込んで』等は、共有方式が未指定なら\n"
             "設定済みの共有先を確認し、複数の方式・対象があれば必要な一点だけ確認する。\n"
             "自動保存・一般のGitHub操作・Cloudアップロードの依頼にはこの経路を強制しない。\n"
             "共有許可とレビューを自動付与せず、未設定・未ログインなら必要な接続支援を提案する。\n"
             "既存の許可を再利用するが、PRマージ・公開・共有範囲の拡大を推測しない。\n"
             "Workflow file (JSON-quoted absolute path): " + json.dumps(str(workflow), ensure_ascii=False) + "\n"
             + SHARING_END)
    if agents.count(SHARING_BEGIN) != agents.count(SHARING_END) or agents.count(SHARING_BEGIN) > 1:
        raise ValueError("Malformed Basic Memory sharing AGENTS block; preserve and repair manually")
    if SHARING_BEGIN in agents:
        begin, end = agents.index(SHARING_BEGIN), agents.index(SHARING_END) + len(SHARING_END)
        if agents.index(SHARING_END) < begin:
            raise ValueError("Malformed Basic Memory sharing AGENTS block")
        agents = agents[:begin] + block + agents[end:]
    else:
        agents = agents + ("\n" if agents and not agents.endswith("\n") else "") + ("\n" if agents else "") + block + "\n"
    changes.append((agents_path, agents))
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
    message = (f"Configured {codex_dir}: project={selected_project}, mode={selected_mode}, "
               f"correction={auto_config['correctionMode']}, case={auto_config['caseMode']}, skill={auto_config['skillMode']}, checkpointOnCompact=false")
    return changes, message


def configure(codex_dir, project=None, mode=None, case_mode=None, skill_mode=None, correction_mode=None):
    changes, message = prepare_configuration(codex_dir, project, mode, case_mode, skill_mode, correction_mode)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    for path, content in changes:
        write_file(path, content, stamp)
    print(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-dir", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--project", default=os.environ.get("MEMORY_PROJECT"))
    parser.add_argument("--mode", default=os.environ.get("BM_AUTO_MODE"))
    parser.add_argument("--case-mode", default=os.environ.get("BM_CASE_MODE"))
    parser.add_argument("--skill-mode", default=os.environ.get("BM_SKILL_MODE"))
    parser.add_argument("--correction-mode", default=os.environ.get("BM_CORRECTION_MODE"))
    args = parser.parse_args()
    try:
        configure(args.codex_dir.expanduser().resolve(), args.project, args.mode,
                  args.case_mode, args.skill_mode, args.correction_mode)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        parser.exit(1, f"Configuration failed: {exc}\n")


if __name__ == "__main__":
    main()
