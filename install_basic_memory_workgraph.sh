#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Basic Memory + Codex Work Knowledge Graph セットアップ
# Linux / WSL2
#
# 目的:
#   案件をまたいで役立つ検証済みの知識と、明示的な継続的好みだけを
#   Basic Memory に保存し、次回の仕事で再利用する。
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

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"

log() { printf '\n[%s] %s\n' "bm-workgraph" "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

command -v python3 >/dev/null || die "python3 が必要です。"

case "${1:-}" in
  --configure-only)
    [[ $# -eq 1 ]] || die "--configure-only に追加の引数は指定できません。"
    python3 "$SCRIPT_DIR/configure_workgraph.py" --codex-dir "$CODEX_HOME_DIR"
    log "設定とフックを更新しました。新しいCodexセッションで反映を確認してください。"
    exit 0
    ;;
  --help|-h)
    echo "Usage: bash install_basic_memory_workgraph.sh [--configure-only]"
    echo "--configure-only: 設定とフックだけを更新。既存の保存先とモードを維持。"
    echo "MEMORY_PROJECT / BM_AUTO_MODE を指定した場合は、その値を使用します。"
    exit 0
    ;;
  "") [[ $# -eq 0 ]] || die "不正な引数です。" ;;
  *) die "不明な引数: $1" ;;
esac

MEMORY_PROJECT="${MEMORY_PROJECT:-codex-memory}"
MEMORY_DIR="${MEMORY_DIR:-$HOME/knowledge/codex-memory}"
BM_AUTO_MODE="${BM_AUTO_MODE:-smart}"
case "$BM_AUTO_MODE" in
  smart|always|off) ;;
  *) die "BM_AUTO_MODE は smart / always / off のいずれかです。" ;;
esac

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
if bm install codex --help >/dev/null 2>&1; then
  bm install codex --yes
else
  # bm install が無い版では、公式 installer と同じ Codex CLI 操作を行う。
  log "bm install 未対応のため、Codex CLI から直接導入します"
  codex plugin marketplace add --help >/dev/null 2>&1 \
    || die "この Codex CLI は plugin marketplace に未対応です。Codex CLI を更新してください。"
  codex plugin marketplace add basicmachines-co/basic-memory
  codex plugin add codex@basic-memory
fi

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
- Automatically save only verified transferable knowledge or explicit lasting preferences.
- Search before creating a new entity; duplicates without new evidence require no write.
- Do not automatically create work diaries, Cases, or session checkpoints.
- Preserve conditions and exceptions.
- Do not infer success from silence.
- A graph connection is evidence of relevance, not proof that an old rule applies.
EOF

# ------------------------------------------------------------
# STEP 7: 共通ポリシー / Codex設定 / 追加Hook
# ------------------------------------------------------------
python3 "$SCRIPT_DIR/configure_workgraph.py" \
  --codex-dir "$CODEX_HOME_DIR" --project "$MEMORY_PROJECT" --mode "$BM_AUTO_MODE"

# ------------------------------------------------------------
# STEP 8: Status
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
    再利用候補を共通基準で評価。該当なしなら保存しない

[6] 自動保存モード
  $BM_AUTO_MODE

  smart  : 好み・教訓の候補があるとき評価（推奨）
  always : 毎ターン評価（保存基準は同じ）
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
   "Evaluating reusable Basic Memory knowledge"
   を確認して trust

4. 新しい会話で:
   \$bm-status

5. 動作確認:
   「PDF翻訳で『図をそのまま』と指定した場合は、
     原図を再生成しないでください。
     今後もこの好みを適用してください。」

6. 次の新しい会話:
   「PDF翻訳をします。
     過去の似たCaseと関連Rule/Workflow/Validationを
     Basic Memoryから確認してから進めてください。」

============================================================
EOF
