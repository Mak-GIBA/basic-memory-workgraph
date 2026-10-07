#!/usr/bin/env bash
set -euo pipefail

# Work Knowledge Graphの追加hooks・共有用入口・補助CLIと設定を解除する。
# Basic Memory本体・公式plugin・保存済みMarkdown・schemaは削除しない。

CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
HOOKS_JSON="$CODEX_HOME_DIR/hooks.json"

if [[ -f "$HOOKS_JSON" ]]; then
  cp -a "$HOOKS_JSON" "$HOOKS_JSON.bak.$(date +%Y%m%d-%H%M%S)"

  python3 - "$HOOKS_JSON" <<'PY'
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
hooks = data.get("hooks", {})

for event in ("UserPromptSubmit", "Stop"):
    kept = []
    for group in hooks.get(event, []):
        remaining = [h for h in group.get("hooks", [])
                     if "basic_memory_workgraph" not in h.get("command", "")]
        if remaining:
            kept.append({**group, "hooks": remaining})
    if kept:
        hooks[event] = kept
    else:
        hooks.pop(event, None)

data["hooks"] = hooks
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
fi

# Remove only our sharing entrypoint, preserving other AGENTS instructions.
python3 - "$CODEX_HOME_DIR/AGENTS.md" <<'PY'
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

path = Path(sys.argv[1])
begin = "<!-- basic-memory-github-sharing:begin -->"
end = "<!-- basic-memory-github-sharing:end -->"
if path.exists():
    original = path.read_text(encoding="utf-8")
    if original.count(begin) == 1 and original.count(end) == 1:
        first, last = original.index(begin), original.index(end) + len(end)
        if original.index(end) > first:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            shutil.copy2(path, path.with_name(path.name + ".bak." + stamp))
            path.write_text(original[:first] + original[last:], encoding="utf-8")
        else:
            raise SystemExit("Malformed memory sharing AGENTS block; preserve and repair manually")
    elif begin in original or end in original:
        raise SystemExit("Malformed memory sharing AGENTS block; preserve and repair manually")
PY

rm -f "$CODEX_HOME_DIR/hooks/basic_memory_workgraph.py"
rm -f "$CODEX_HOME_DIR/hooks/basic_memory_workgraph_recall.py"
rm -f "$CODEX_HOME_DIR/hooks/basic_memory_workgraph_save.py"
rm -rf "$CODEX_HOME_DIR/basic-memory-workgraph"

echo "Work Knowledge Graphの追加hooks・共有用入口・補助CLIと設定を解除しました。"
echo "Basic Memory本体、公式Codex plugin、保存済みKnowledgeは残っています。"
echo "Codexを再起動し、/hooks で確認してください。"
