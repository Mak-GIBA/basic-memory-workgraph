#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Basic Memory + Codex Work Knowledge Graph セットアップ
# Linux / WSL2
#
# 目的:
#   再利用知識・継続的好みと、有効化時は文脈付き修正指示を
#   Basic Memory に保存し、次回の初回出力から再利用する。
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
#   BM_CORRECTION_MODE=scoped # 文脈付き修正指示の保存（既定off）
#   BM_CASE_MODE=reusable # 結果のある有用な具体事例（既定off）
#   BM_CASE_MODE=progressive # 未完了の改善シーケンスと採用推定も段階的に保存
#   BM_SKILL_MODE=auto    # 検証済みSkillの登録（既定review）
# ============================================================

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKGRAPH_DIR="$SCRIPT_DIR/tools/basic-memory-workgraph"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"

log() { printf '\n[%s] %s\n' "bm-workgraph" "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

command -v python3 >/dev/null || die "python3 が必要です。"

case "${1:-}" in
  --update)
    shift
    exec python3 "$WORKGRAPH_DIR/update_workgraph.py" --codex-dir "$CODEX_HOME_DIR" "$@"
    ;;
  --configure-only)
    [[ $# -eq 1 ]] || die "--configure-only に追加の引数は指定できません。"
    python3 "$WORKGRAPH_DIR/configure_workgraph.py" --codex-dir "$CODEX_HOME_DIR"
    log "設定とフックを更新しました。新しいCodexセッションで反映を確認してください。"
    exit 0
    ;;
  --help|-h)
    echo "Usage: bash install_basic_memory_workgraph.sh [--configure-only | --update [--dry-run]]"
    echo "--update: 登録済みの保存先を検出し、設定・hooks・CLI・スキーマを更新。コード取得やパッケージ更新は行いません。"
    echo "--configure-only: 設定とフックだけを更新。既存の保存先とモードを維持。"
    echo "MEMORY_PROJECT / BM_AUTO_MODE / BM_CORRECTION_MODE / BM_CASE_MODE / BM_SKILL_MODE で設定を指定します。"
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

case "${BM_CORRECTION_MODE:-off}" in off|scoped) ;; *) die "BM_CORRECTION_MODE は off / scoped です。" ;; esac
case "${BM_CASE_MODE:-off}" in off|reusable|progressive) ;; *) die "BM_CASE_MODE は off / reusable / progressive です。" ;; esac
case "${BM_SKILL_MODE:-review}" in off|review|auto) ;; *) die "BM_SKILL_MODE は off / review / auto です。" ;; esac

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

SCHEMA_RESULT=0
python3 "$WORKGRAPH_DIR/install_schemas.py" --memory-dir "$MEMORY_DIR" || SCHEMA_RESULT=$?
[[ "$SCHEMA_RESULT" -eq 0 || "$SCHEMA_RESULT" -eq 2 ]] || die "スキーマ更新に失敗しました。"

# ------------------------------------------------------------
# STEP 7: 共通ポリシー / Codex設定 / 追加Hook
# ------------------------------------------------------------
python3 "$WORKGRAPH_DIR/configure_workgraph.py" \
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

  事例・Skillの実効モード:
    $CODEX_HOME_DIR/basic-memory-workgraph/config.json
  BM_CASE_MODE: off / reusable（未設定時off）
  BM_SKILL_MODE: off / review / auto（未設定時review）
  共有・JSONL・Skill登録CLIにはPyYAMLが必要です。READMEの導入手順を参照してください。

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

if [[ "$SCHEMA_RESULT" -eq 2 ]]; then
  log "設定更新は完了しましたが、個別確認が必要なスキーマ・索引を保持しています。上の表示を確認してください。"
  exit 2
fi
