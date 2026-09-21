#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Basic Memory + Codex Work Knowledge Graph セットアップ
# Linux / WSL2
#
# 目的:
#   過去の仕事・修正・ルール・手順・検査を
#   Basic Memory の Knowledge Graph として自動蓄積し、
#   次回の仕事で関連事例を2〜3 hop辿って再利用する。
#
# 使い方:
#   chmod +x install_basic_memory_workgraph.sh
#   bash install_basic_memory_workgraph.sh
#
# 保存先を変える:
#   MEMORY_PROJECT=work-memory \
#   MEMORY_DIR="$HOME/knowledge/work-memory" \
#   bash install_basic_memory_workgraph.sh
#
# 自動記憶:
#   BM_AUTO_MODE=smart   # 推奨
#   BM_AUTO_MODE=always  # 毎ターン
#   BM_AUTO_MODE=off     # 自動保存しない
# ============================================================

MEMORY_PROJECT="${MEMORY_PROJECT:-codex-memory}"
MEMORY_DIR="${MEMORY_DIR:-$HOME/knowledge/codex-memory}"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
BM_AUTO_MODE="${BM_AUTO_MODE:-smart}"

log() { printf '\n[%s] %s\n' "bm-workgraph" "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

command -v python3 >/dev/null || die "python3 が必要です。"
command -v codex >/dev/null || die "codex CLI が必要です。"
command -v curl >/dev/null || die "curl が必要です。"

mkdir -p "$CODEX_HOME_DIR" "$MEMORY_DIR"

# ------------------------------------------------------------
# STEP 1: uv / uvx
# ------------------------------------------------------------
export PATH="$HOME/.local/bin:$PATH"

# uv だけが PATH 上にリンクされている場合、同梱の uvx も公開する。
# Basic Memory の公式 plugin は bm ではなく uvx から MCP を起動する。
if command -v uv >/dev/null 2>&1 && ! command -v uvx >/dev/null 2>&1; then
  UVX_COMPANION="$(python3 - "$(command -v uv)" <<'PY'
from pathlib import Path
import sys

print(Path(sys.argv[1]).resolve().with_name("uvx"))
PY
)"
  if [ -x "$UVX_COMPANION" ] && \
     [ ! -e "$HOME/.local/bin/uvx" ] && [ ! -L "$HOME/.local/bin/uvx" ]; then
    log "既存の uvx を ~/.local/bin にリンクします"
    mkdir -p "$HOME/.local/bin"
    ln -s "$UVX_COMPANION" "$HOME/.local/bin/uvx"
  fi
fi

if ! command -v uv >/dev/null 2>&1 || ! command -v uvx >/dev/null 2>&1; then
  log "uv / uvx を導入します"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
command -v uv >/dev/null || die "uv が PATH 上にありません。"
command -v uvx >/dev/null || die "uvx が PATH 上にありません。Basic Memory MCP の起動に必要です。"
UV_VERSION="$(uv --version)" || die "uv を実行できません。"
UVX_VERSION="$(uvx --version)" || die "uvx を実行できません。"
log "uv: $UV_VERSION"
log "uvx: $UVX_VERSION"

# ------------------------------------------------------------
# STEP 2: Basic Memory CLI
# ------------------------------------------------------------
log "Basic Memory を導入/更新します"
uv python install 3.12 >/dev/null

if command -v bm >/dev/null 2>&1; then
  uv tool upgrade basic-memory >/dev/null || true
else
  uv tool install --python 3.12 basic-memory >/dev/null
fi

export PATH="$HOME/.local/bin:$PATH"
command -v bm >/dev/null || die "bm CLI が見つかりません。"
log "Basic Memory: $(bm --version | head -n1)"

# bm hook surface が無い古い版の場合だけ更新
if ! bm hook --help >/dev/null 2>&1; then
  log "Codex Hook対応版へ更新します"
  uv tool install --force --prerelease=allow --python 3.12 basic-memory >/dev/null
fi
bm hook --help >/dev/null 2>&1 || die "bm hook が利用できません。"

# ------------------------------------------------------------
# STEP 3: Basic Memory 公式 Codex plugin
# ------------------------------------------------------------
log "Basic Memory 公式 Codex plugin を導入します"
bm install codex --yes

# ------------------------------------------------------------
# STEP 4: Knowledge project
# ------------------------------------------------------------
log "Memory project: $MEMORY_PROJECT -> $MEMORY_DIR"
mkdir -p "$MEMORY_DIR"

if ! bm project list 2>/dev/null | grep -Fq "$MEMORY_PROJECT"; then
  bm project add "$MEMORY_PROJECT" "$MEMORY_DIR"
else
  log "project '$MEMORY_PROJECT' は既に登録されています"
fi

# ------------------------------------------------------------
# STEP 5: Work Knowledge Graph のフォルダ
# ------------------------------------------------------------
mkdir -p \
  "$MEMORY_DIR/cases" \
  "$MEMORY_DIR/corrections" \
  "$MEMORY_DIR/rules" \
  "$MEMORY_DIR/workflows" \
  "$MEMORY_DIR/validations" \
  "$MEMORY_DIR/artifacts" \
  "$MEMORY_DIR/projects" \
  "$MEMORY_DIR/schemas"

# ------------------------------------------------------------
# STEP 6: Schema notes
# ------------------------------------------------------------

cat > "$MEMORY_DIR/schemas/Case.md" <<'EOF'
---
title: Case
type: schema
entity: Case
version: 1
schema:
  task_type: string, kind of work performed
  status?: string, accepted / rejected / unverified / partial
  belongs_to?: Project, project or scope
  received?(array): Correction, explicit user corrections
  used?(array): Workflow, workflows used
  validated_by?(array): Validation, checks applied
  produced?(array): Artifact, output artifacts
  learned?(array): Rule, rules learned from the case
settings:
  validation: warn
---

# Case

A concrete past task. Preserve the conditions, what happened, and outcome.
EOF

cat > "$MEMORY_DIR/schemas/Correction.md" <<'EOF'
---
title: Correction
type: schema
entity: Correction
version: 1
schema:
  instruction: string, what the user explicitly corrected
  reason?: string, why the previous result was inadequate
  occurred_in?: Case, originating case
  generalized_to?(array): Rule, reusable rules derived from this correction
settings:
  validation: warn
---

# Correction

An explicit user correction. Do not infer corrections from silence.
EOF

cat > "$MEMORY_DIR/schemas/Rule.md" <<'EOF'
---
title: Rule
type: schema
entity: Rule
version: 1
schema:
  trigger: string, conditions where the rule applies
  action: string, behavior to perform
  exception?(array): string, when not to apply the rule
  learned_from?(array): Case, evidence cases
  implemented_by?(array): Workflow, workflows implementing the rule
  validated_by?(array): Validation, checks verifying the rule
settings:
  validation: warn
---

# Rule

A reusable conditional rule generalized from evidence.
EOF

cat > "$MEMORY_DIR/schemas/Workflow.md" <<'EOF'
---
title: Workflow
type: schema
entity: Workflow
version: 1
schema:
  steps(array): string, ordered or practical work steps
  used_in?(array): Case, cases where this workflow was used
  implements?(array): Rule, rules implemented by this workflow
  checked_by?(array): Validation, checks for this workflow
settings:
  validation: warn
---

# Workflow

A reusable way of doing work.
EOF

cat > "$MEMORY_DIR/schemas/Validation.md" <<'EOF'
---
title: Validation
type: schema
entity: Validation
version: 1
schema:
  check(array): string, checks to perform
  validates_rule?(array): Rule, rules checked
  validates_workflow?(array): Workflow, workflows checked
settings:
  validation: warn
---

# Validation

A verification procedure. Never mark an unperformed check as PASS.
EOF

cat > "$MEMORY_DIR/schemas/Artifact.md" <<'EOF'
---
title: Artifact
type: schema
entity: Artifact
version: 1
schema:
  kind: string, pdf / docx / pptx / code / report / other
  location?: string, stable path or reference if safe to store
  produced_by?: Case, originating case
settings:
  validation: warn
---

# Artifact

A produced file or deliverable. Do not store secrets in paths or metadata.
EOF

cat > "$MEMORY_DIR/schemas/Project.md" <<'EOF'
---
title: Project
type: schema
entity: Project
version: 1
schema:
  scope: string, what this project represents
settings:
  validation: warn
---

# Project

A project, repository, workstream, or durable scope.
EOF

cat > "$MEMORY_DIR/Work-Knowledge-Graph.md" <<'EOF'
---
title: Work Knowledge Graph
type: note
tags: [knowledge-graph, workflow, memory]
---

# Work Knowledge Graph

## Node Types
- [[Case]]
- [[Correction]]
- [[Rule]]
- [[Workflow]]
- [[Validation]]
- [[Artifact]]
- [[Project]]

## Relation Conventions
- `belongs_to [[Project]]`
- `received [[Correction]]`
- `generalized_to [[Rule]]`
- `learned_from [[Case]]`
- `used [[Workflow]]`
- `implements [[Rule]]`
- `validated_by [[Validation]]`
- `produced [[Artifact]]`
- `related_to [[Case]]`

## Principles
- Current user instructions override older memory.
- Search before creating a new entity.
- Preserve conditions and exceptions.
- Do not infer success from silence.
- A graph connection is evidence of relevance, not proof that an old rule applies.
EOF

# ------------------------------------------------------------
# STEP 7: Codex Basic Memory config
# ------------------------------------------------------------
BM_CONFIG="$CODEX_HOME_DIR/basic-memory.json"
if [[ -f "$BM_CONFIG" ]]; then
  cp -a "$BM_CONFIG" "$BM_CONFIG.bak.$(date +%Y%m%d-%H%M%S)"
fi

python3 - "$BM_CONFIG" "$MEMORY_PROJECT" <<'PY'
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
project = sys.argv[2]

data = {}
if path.exists():
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}

cfg = data.setdefault("basicMemory", {})
cfg.update({
    "primaryProject": project,
    "secondaryProjects": cfg.get("secondaryProjects", []),
    "teamProjects": cfg.get("teamProjects", {}),
    "rememberFolder": cfg.get("rememberFolder", "corrections"),
    "recallTimeframe": cfg.get("recallTimeframe", "365d"),
    "checkpointOnCompact": True,
    "captureEvents": True,
    "sessionProfile": cfg.get("sessionProfile", "general"),
    "placementConventions": (
        "Use a Work Knowledge Graph. "
        "Store concrete tasks in cases/, explicit corrections in corrections/, "
        "reusable conditional rules in rules/, reusable procedures in workflows/, "
        "verification procedures in validations/, output references in artifacts/, "
        "and durable scopes in projects/. "
        "Use typed wiki-link relations and search before creating duplicates. "
        "Preserve trigger conditions and exceptions. "
        "Never infer user acceptance from silence."
    ),
})
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

# ------------------------------------------------------------
# STEP 8: Additional Codex hooks
# ------------------------------------------------------------
HOOK_DIR="$CODEX_HOME_DIR/hooks"
mkdir -p "$HOOK_DIR"

# ---- Recall Hook ----
cat > "$HOOK_DIR/basic_memory_workgraph_recall.py" <<'PY'
#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        print("{}")
        return

    prompt = str(event.get("prompt") or "")
    turn_id = str(event.get("turn_id") or "unknown")

    state_dir = Path(os.path.expanduser("~/.codex/basic-memory-workgraph/state"))
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{turn_id}.json").write_text(
        json.dumps({"prompt": prompt}, ensure_ascii=False),
        encoding="utf-8",
    )

    if len(prompt.strip()) < 8:
        print("{}")
        return

    context = r"""
Basic Memory contains a Work Knowledge Graph.

Before substantial work:

1. Search for similar `Case` nodes and directly relevant `Rule` / `Workflow` nodes.
2. For promising Cases, read the note and use Basic Memory graph context/build_context
   at depth 2 or 3 when useful.
3. Inspect connected:
   - Correction
   - Rule
   - Workflow
   - Validation
   - Artifact
   - Project
4. Compare the old Case conditions with the current request.
5. Apply only compatible Rules and Workflows.
6. Current user instructions always override older memory.
7. A graph path means "potentially relevant", not "automatically applicable".
8. Avoid exposing irrelevant private memory.

For substantial tasks, briefly keep track of:
- reused Case(s)
- applicable Rule(s)
- Workflow(s) reused
- old conditions that do NOT apply this time
""".strip()

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context
        }
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
PY
chmod +x "$HOOK_DIR/basic_memory_workgraph_recall.py"

# ---- Auto Save Hook ----
cat > "$HOOK_DIR/basic_memory_workgraph_save.py" <<'PY'
#!/usr/bin/env python3
import json, os, re, sys
from pathlib import Path

KEYWORDS = re.compile(
    r"(修正|直して|ではなく|もっと|今後|次から|覚え|記憶|ルール|方針|決め|"
    r"失敗|原因|教訓|好み|優先|毎回|必ず|二度と|"
    r"remember|preference|from now on|next time|instead|decision|lesson|correction)",
    re.IGNORECASE,
)

def should_run(mode: str, prompt: str, answer: str) -> bool:
    if mode == "off":
        return False
    if mode == "always":
        return True
    if KEYWORDS.search(prompt):
        return True
    return len(prompt) >= 120 or len(answer) >= 1800

def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        print("{}")
        return

    # Stop継続は1回だけ
    if bool(event.get("stop_hook_active")):
        print("{}")
        return

    cfg_path = Path(os.path.expanduser("~/.codex/basic-memory-workgraph/config.json"))
    mode = "smart"
    if cfg_path.exists():
        try:
            mode = json.loads(cfg_path.read_text(encoding="utf-8")).get("mode", "smart")
        except Exception:
            pass

    turn_id = str(event.get("turn_id") or "unknown")
    answer = str(event.get("last_assistant_message") or "")
    state = Path(os.path.expanduser(f"~/.codex/basic-memory-workgraph/state/{turn_id}.json"))

    prompt = ""
    if state.exists():
        try:
            prompt = json.loads(state.read_text(encoding="utf-8")).get("prompt", "")
        except Exception:
            pass

    if not should_run(mode, prompt, answer):
        print("{}")
        return

    reason = r"""
Before finishing this turn, perform ONE Basic Memory Work Knowledge Graph persistence pass.

First:
- Search existing Basic Memory notes before creating anything.
- Reuse/update existing entities when they represent the same concept.
- Do not save anything if this turn produced no durable reusable knowledge.

Node types:
- Case: a concrete past task and its conditions/outcome
- Correction: an explicit user correction
- Rule: a reusable conditional rule
- Workflow: a reusable procedure that worked
- Validation: a verification/checking procedure
- Artifact: a safe reference to a produced deliverable
- Project: a durable project/workstream scope

Preferred folders:
- Case -> cases/
- Correction -> corrections/
- Rule -> rules/
- Workflow -> workflows/
- Validation -> validations/
- Artifact -> artifacts/
- Project -> projects/

Typed relation conventions:
- Case belongs_to [[Project]]
- Case received [[Correction]]
- Case used [[Workflow]]
- Case validated_by [[Validation]]
- Case produced [[Artifact]]
- Case learned [[Rule]]
- Correction occurred_in [[Case]]
- Correction generalized_to [[Rule]]
- Rule learned_from [[Case]]
- Rule implemented_by [[Workflow]]
- Rule validated_by [[Validation]]
- Workflow used_in [[Case]]
- Workflow implements [[Rule]]
- Workflow checked_by [[Validation]]
- Artifact produced_by [[Case]]
- related_to [[...]] only when a more specific relation is not appropriate

Persistence policy:
1. Preserve the conditions that made a correction or workflow valid.
2. Preserve exceptions. Do not turn a one-off instruction into a global Rule.
3. Create a `Correction` only from an explicit user correction, not from silence.
4. Create a `Rule` only when the lesson is reusable beyond the single Case.
5. Create a `Workflow` only when there is an actual procedure worth reusing.
6. Create a `Validation` only for a real check or verification procedure.
7. Do not mark a Case as accepted/successful unless:
   - the user explicitly accepted it, or
   - objective verification actually passed.
   Otherwise use `unverified` or `partial`.
8. Prefer a small connected graph over many isolated notes.
9. Use observations such as:
   - [task_type]
   - [status]
   - [trigger]
   - [action]
   - [exception]
   - [instruction]
   - [reason]
   - [steps]
   - [check]
10. Do NOT persist:
   - passwords/tokens/credentials
   - personal secrets
   - irrelevant raw transcripts
   - long tool output
   - temporary IDs/paths unless they are essential and safe
   - unverified guesses as facts
11. Current user instructions always override older memory.
12. After writing/updating notes, read back the changed nodes once and verify
    the intended typed relations were stored.

For a substantial task with explicit correction, the usual minimal graph is:

Case -> Correction -> Rule
Case -> Workflow -> Validation

Do NOT force all node types to exist if they add no value.

After this single persistence pass, finish the turn normally.
Do not start another persistence pass for this continuation.
""".strip()

    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))

if __name__ == "__main__":
    main()
PY
chmod +x "$HOOK_DIR/basic_memory_workgraph_save.py"

# ------------------------------------------------------------
# STEP 9: Auto mode config
# ------------------------------------------------------------
AUTO_DIR="$CODEX_HOME_DIR/basic-memory-workgraph"
mkdir -p "$AUTO_DIR/state"

cat > "$AUTO_DIR/config.json" <<EOF
{
  "mode": "$BM_AUTO_MODE"
}
EOF

# ------------------------------------------------------------
# STEP 10: hooks.json へ安全に追加
# ------------------------------------------------------------
HOOKS_JSON="$CODEX_HOME_DIR/hooks.json"
if [[ -f "$HOOKS_JSON" ]]; then
  cp -a "$HOOKS_JSON" "$HOOKS_JSON.bak.$(date +%Y%m%d-%H%M%S)"
fi

python3 - "$HOOKS_JSON" \
  "$HOOK_DIR/basic_memory_workgraph_recall.py" \
  "$HOOK_DIR/basic_memory_workgraph_save.py" <<'PY'
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
recall = str(Path(sys.argv[2]).resolve())
save = str(Path(sys.argv[3]).resolve())

data = {}
if path.exists():
    data = json.loads(path.read_text(encoding="utf-8"))

hooks = data.setdefault("hooks", {})

# 旧版の今回作成した自動Hookだけを除去し、二重実行を防ぐ。
for event in ("UserPromptSubmit", "Stop"):
    kept = []
    for group in hooks.get(event, []):
        commands = [
            h.get("command", "")
            for h in group.get("hooks", [])
        ]
        if any(
            ("basic_memory_recall.py" in c) or
            ("basic_memory_auto_remember.py" in c) or
            ("basic_memory_workgraph_" in c)
            for c in commands
        ):
            continue
        kept.append(group)
    if kept:
        hooks[event] = kept
    else:
        hooks.pop(event, None)

hooks.setdefault("UserPromptSubmit", []).append({
    "hooks": [{
        "type": "command",
        "command": f'python3 "{recall}"',
        "timeout": 10,
        "statusMessage": "Searching Basic Memory Work Knowledge Graph"
    }]
})

hooks.setdefault("Stop", []).append({
    "hooks": [{
        "type": "command",
        "command": f'python3 "{save}"',
        "timeout": 10,
        "statusMessage": "Updating Basic Memory Work Knowledge Graph"
    }]
})

data["hooks"] = hooks
data["description"] = data.get(
    "description",
    "User hooks including Basic Memory Work Knowledge Graph recall and persistence"
)

path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

# ------------------------------------------------------------
# STEP 11: Status
# ------------------------------------------------------------
log "Basic Memory の状態を確認します"
bm project list || true
bm hook status --harness codex --project-dir "$PWD" || true

cat <<EOF

============================================================
Basic Memory Work Knowledge Graph セットアップ完了
============================================================

[1] Knowledgeの名前
  $MEMORY_PROJECT

[2] Markdownの正本
  $MEMORY_DIR

[3] 主なフォルダ
  $MEMORY_DIR/cases
  $MEMORY_DIR/corrections
  $MEMORY_DIR/rules
  $MEMORY_DIR/workflows
  $MEMORY_DIR/validations
  $MEMORY_DIR/artifacts
  $MEMORY_DIR/projects
  $MEMORY_DIR/schemas

[4] Codex設定
  $CODEX_HOME_DIR/basic-memory.json

[5] 追加したHook
  UserPromptSubmit:
    過去のCaseを検索 → 2〜3 hopでRule/Workflow/Validationを参照

  Stop:
    今回の修正・手順・結果をKnowledge Graphへ保存するか判定

[6] 自動保存モード
  $BM_AUTO_MODE

  smart  : 修正/判断/大きな仕事で実行（推奨）
  always : 毎ターン実行
  off    : 自動保存を停止

------------------------------------------------------------
次にやること
------------------------------------------------------------

1. Codexを完全に終了して再起動

2. Codexで:
   /plugins

   codex@basic-memory が有効か確認

3. Codexで:
   /hooks

   Basic Memory公式Hookと
   "Searching Basic Memory Work Knowledge Graph"
   "Updating Basic Memory Work Knowledge Graph"
   を確認して trust

4. 新しい会話で:
   \$bm-status

5. 動作確認:
   「PDF翻訳で『図をそのまま』と指定した場合は、
     原図を再生成しないでください。
     今回の修正を次回に再利用できる事例として記憶してください。」

6. 次の新しい会話:
   「PDF翻訳をします。
     過去の似たCaseと関連Rule/Workflow/Validationを
     Basic Memoryから確認してから進めてください。」

============================================================
EOF
