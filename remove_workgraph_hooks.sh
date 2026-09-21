#!/usr/bin/env bash
set -euo pipefail

# 今回追加したWork Knowledge Graph自動Hookだけを解除する。
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

rm -f "$CODEX_HOME_DIR/hooks/basic_memory_workgraph.py"
rm -f "$CODEX_HOME_DIR/hooks/basic_memory_workgraph_recall.py"
rm -f "$CODEX_HOME_DIR/hooks/basic_memory_workgraph_save.py"
rm -rf "$CODEX_HOME_DIR/basic-memory-workgraph"

echo "Work Knowledge Graph用の追加Hookだけを解除しました。"
echo "Basic Memory本体、公式Codex plugin、保存済みKnowledgeは残っています。"
echo "Codexを再起動し、/hooks で確認してください。"
