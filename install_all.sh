#!/usr/bin/env bash
# Install the selected repository tools through their maintained installers.
# Requires this repository. No arguments previews; --apply performs installation.
set -euo pipefail

BULK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BULK_TOOLS=(workgraph ux-stack speckit github-pm design-research ecc office yomiyasu herdr)
BULK_SCRIPTS=(install_basic_memory_workgraph.sh install_codex_ux_stack.sh
  install_speckit_upstream.sh install_codex_github_pm.sh install_design_research.sh
  install_codex_ecc.sh install_codex_office.sh install_codex_yomiyasu.sh install_herdr.sh)
BULK_DESCRIPTIONS=("Basic Memory・Workgraph" "OOUI・UI/UX設計と画像付き検証"
  "SpecKit上流工程" "GitHubのIssue・PR・Projects管理" "コアロジックの調査・改善"
  "ECCと必要時に読む入口" "PDF・Word・PowerPointの編集" "日本語の段落構成・推敲" "HerdrとBash設定")
BULK_MODE=preview
BULK_EXPLICIT_MODE=
BULK_ONLY=
BULK_LIST=0

bulk_error() { printf '[codex-tools] ERROR: %s\n' "$*" >&2; exit 2; }

bulk_help() {
  cat <<'HELP'
Usage: bash install_all.sh [--apply | --dry-run] [--only TOOL[,TOOL...]]
       bash install_all.sh --list

  --apply      選択したツールを一括導入
  --dry-run    実行予定の表示だけ（引数なしも同じ。子スクリプトは起動しない）
  --only IDS   対象をIDで選択。カンマ区切り・複数回の指定が可能
  --list       ツールIDと説明を表示
  --help, -h   ヘルプを表示

例:
  bash install_all.sh --apply
  bash install_all.sh --only ux-stack,yomiyasu --apply

リポジトリ一式が必要です。全ツールの標準導入はLinux / WSL2向けです。
各ツールの前提条件・取得元・設定変更はdocs/installation.mdを参照してください。
既存ツールの版や任意機能の変更は個別インストーラーで指定します。
HELP
}

bulk_known_tool() {
  local candidate
  for candidate in "${BULK_TOOLS[@]}"; do
    [[ "$candidate" == "$1" ]] && return 0
  done
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) bulk_help; exit 0 ;;
    --apply|--dry-run)
      if [[ -n "$BULK_EXPLICIT_MODE" && "$BULK_EXPLICIT_MODE" != "$1" ]]; then
        bulk_error "--apply と --dry-run は併用できません。"
      fi
      BULK_EXPLICIT_MODE="$1"
      [[ "$1" == --apply ]] && BULK_MODE=apply
      shift
      ;;
    --only)
      [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || bulk_error "--only にツールIDを指定してください。"
      [[ "$2" =~ ^[a-z][a-z0-9-]*(,[a-z][a-z0-9-]*)*$ ]] || bulk_error "--only はツールIDをカンマ区切りで指定してください。"
      IFS=',' read -r -a requested_tools <<< "$2"
      for requested_tool in "${requested_tools[@]}"; do
        bulk_known_tool "$requested_tool" || bulk_error "不明なツールID: $requested_tool（--listで確認）"
      done
      BULK_ONLY="${BULK_ONLY:+$BULK_ONLY,}$2"
      shift 2
      ;;
    --list) BULK_LIST=1; shift ;;
    *) bulk_error "不明なオプション: $1（--helpで確認）" ;;
  esac
done

if [[ "$BULK_LIST" -eq 1 ]]; then
  [[ "$BULK_MODE" != apply ]] || bulk_error "--list と --apply は併用できません。"
  for i in "${!BULK_TOOLS[@]}"; do
    printf '%-16s %s\n' "${BULK_TOOLS[$i]}" "${BULK_DESCRIPTIONS[$i]}"
  done
  exit 0
fi

bulk_selected() { [[ -z "$BULK_ONLY" || ",$BULK_ONLY," == *",$1,"* ]]; }

# Validate the entire selection before any installer can change the environment.
for i in "${!BULK_TOOLS[@]}"; do
  bulk_selected "${BULK_TOOLS[$i]}" || continue
  [[ -f "$BULK_ROOT/${BULK_SCRIPTS[$i]}" ]] || bulk_error "不足するインストーラー: ${BULK_SCRIPTS[$i]}"
  case "${BULK_TOOLS[$i]}" in
    workgraph)
      for helper in configure_workgraph.py update_workgraph.py install_schemas.py; do
        [[ -f "$BULK_ROOT/tools/basic-memory-workgraph/$helper" ]] || bulk_error "tools/basic-memory-workgraph/を含むリポジトリ一式が必要です。"
      done
      ;;
    ecc)
      [[ -f "$BULK_ROOT/tools/ecc-on-demand/install_ecc.py" ]] || bulk_error "tools/ecc-on-demand/を含むリポジトリ一式が必要です。"
      ;;
  esac
done

bulk_codex_root="${CODEX_HOME:-$HOME/.codex}"
bulk_successes=0
bulk_failures=0
bulk_results=()
for i in "${!BULK_TOOLS[@]}"; do
  tool="${BULK_TOOLS[$i]}"
  bulk_selected "$tool" || continue
  bulk_command=(bash "$BULK_ROOT/${BULK_SCRIPTS[$i]}")
  case "$tool" in
    workgraph)
      # Existing Workgraph settings and Memory locations must survive reruns.
      if [[ -e "$bulk_codex_root/basic-memory-workgraph" || -L "$bulk_codex_root/basic-memory-workgraph" ]]; then
        bulk_command+=(--update)
      fi
      ;;
    speckit|ecc|office|yomiyasu) bulk_command+=(--apply) ;;
  esac
  printf '[codex-tools] %s:' "$tool"
  printf ' %q' "${bulk_command[@]}"
  printf '\n'
  if [[ "$BULK_MODE" == preview ]]; then
    continue
  fi
  if "${bulk_command[@]}"; then
    bulk_successes=$((bulk_successes + 1))
    bulk_results+=("$tool: OK")
  else
    code=$?
    bulk_failures=$((bulk_failures + 1))
    bulk_results+=("$tool: INCOMPLETE (exit $code)")
    if [[ "$code" -eq 130 || "$code" -eq 143 ]]; then
      printf '[codex-tools] INTERRUPTED: %s\n' "$tool" >&2
      printf '%s\n' "${bulk_results[@]}"
      exit "$code"
    fi
  fi
done

if [[ "$BULK_MODE" == preview ]]; then
  printf '[codex-tools] PREVIEW: 表示のみ。導入は --apply を指定してください。\n'
  exit 0
fi
printf '%s\n' "${bulk_results[@]}"
if [[ "$bulk_failures" -gt 0 ]]; then
  printf '[codex-tools] INCOMPLETE: 成功 %s / 未完了 %s。原因を解消して再実行できます。\n' "$bulk_successes" "$bulk_failures" >&2
  exit 1
fi
printf '[codex-tools] COMPLETE: %sツールの導入処理が完了しました。\n' "$bulk_successes"
