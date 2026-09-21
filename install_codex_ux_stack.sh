#!/usr/bin/env bash
set -euo pipefail

# Codex UX Stack Installer (idempotent / safe mode)
#
# Default behavior:
#   - If already installed/configured -> SKIP
#   - If missing -> install
#
# Options:
#   --deep   : also install ux-critique
#   --force  : reinstall/update even if already present
#
# Installs:
#   1) OpenAI Product Design plugin
#   2) OpenAI Build Web Apps plugin
#   3) Vercel web-design-guidelines skill
#   4) Microsoft Playwright MCP
# Optional:
#   5) Thecsiz ux-critique skill

WITH_DEEP=0
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --deep)  WITH_DEEP=1 ;;
    --force) FORCE=1 ;;
    -h|--help)
      cat <<'EOF'
Usage:
  bash install_codex_ux_stack.sh
  bash install_codex_ux_stack.sh --deep
  bash install_codex_ux_stack.sh --force
  bash install_codex_ux_stack.sh --deep --force

Options:
  --deep   Also installs the third-party ux-critique skill.
  --force  Reinstall/update components even if they are already present.

Default behavior is safe/idempotent:
  existing components are skipped.
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

info() { printf '\n\033[1;34m[UX-SETUP]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }
skip() { printf '\033[1;33m[SKIP]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

command -v codex >/dev/null 2>&1 || die "Codex CLI が見つかりません。先に Codex CLI をインストールしてください。"
command -v node  >/dev/null 2>&1 || die "Node.js が見つかりません。Node.js 20+ をインストールしてください。"
command -v npx   >/dev/null 2>&1 || die "npx が見つかりません。Node.js/npm を確認してください。"

NODE_MAJOR="$(node -p "Number(process.versions.node.split('.')[0])")"
if [ "$NODE_MAJOR" -lt 20 ]; then
  die "Node.js 20+ が必要です。現在: $(node -v)"
fi

if ! codex plugin --help >/dev/null 2>&1; then
  die "この Codex CLI は plugin コマンドに未対応です。Codex CLI を最新版へ更新してください。"
fi

if ! codex mcp --help >/dev/null 2>&1; then
  die "この Codex CLI は mcp コマンドに未対応です。Codex CLI を最新版へ更新してください。"
fi

plugin_installed() {
  local name="$1"
  codex plugin list --json 2>/dev/null \
    | grep -Eq "\"name\"[[:space:]]*:[[:space:]]*\"${name}\""
}

install_openai_plugin() {
  local name="$1"

  if plugin_installed "$name" && [ "$FORCE" -eq 0 ]; then
    skip "OpenAI plugin '${name}' already installed."
    return
  fi

  if plugin_installed "$name" && [ "$FORCE" -eq 1 ]; then
    info "OpenAI plugin '${name}' を更新/再インストールします (--force)..."
    codex plugin remove "${name}" --json >/dev/null 2>&1 || true
  else
    info "OpenAI plugin '${name}' をインストールしています..."
  fi

  if codex plugin add "${name}@openai-curated" --json >/dev/null 2>&1; then
    ok "'${name}' をインストールしました。"
    return
  fi

  info "openai-curated marketplace を登録して再試行します..."
  codex plugin marketplace add openai/plugins --json >/dev/null 2>&1 || true

  codex plugin add "${name}@openai-curated" --json >/dev/null \
    || die "'${name}' のインストールに失敗しました。Codex を更新し、ネットワーク接続を確認してください。"

  ok "'${name}' をインストールしました。"
}

skill_installed_global() {
  local skill="$1"

  # Prefer the skills CLI listing.
  if npx -y skills@latest list --global --agent codex 2>/dev/null \
      | grep -Fq "$skill"; then
    return 0
  fi

  # Fallback for standard Codex skill directory.
  [ -d "$HOME/.codex/skills/$skill" ]
}

mcp_installed() {
  local name="$1"
  codex mcp get "$name" --json >/dev/null 2>&1
}

info "1/4 Product Design plugin"
install_openai_plugin "product-design"

info "2/4 Build Web Apps plugin"
install_openai_plugin "build-web-apps"

info "3/4 Vercel web-design-guidelines skill"
if skill_installed_global "web-design-guidelines" && [ "$FORCE" -eq 0 ]; then
  skip "web-design-guidelines already installed."
else
  if skill_installed_global "web-design-guidelines" && [ "$FORCE" -eq 1 ]; then
    info "web-design-guidelines を更新/再インストールします (--force)..."
  else
    info "web-design-guidelines をインストールします..."
  fi

  npx -y skills@latest add vercel-labs/agent-skills \
    --skill web-design-guidelines \
    --agent codex \
    --global \
    --yes

  ok "web-design-guidelines をインストールしました。"
fi

info "4/4 Playwright MCP"
if mcp_installed "playwright" && [ "$FORCE" -eq 0 ]; then
  skip "Playwright MCP already configured."
else
  if mcp_installed "playwright" && [ "$FORCE" -eq 1 ]; then
    info "Playwright MCP を再登録します (--force)..."
    codex mcp remove playwright >/dev/null 2>&1 || true
  else
    info "Playwright MCP を設定します..."
  fi

  codex mcp add playwright -- npx -y "@playwright/mcp@latest" >/dev/null
  ok "Playwright MCP を設定しました。"
fi

if [ "$WITH_DEEP" -eq 1 ]; then
  command -v git >/dev/null 2>&1 || die "--deep には git が必要です。"

  info "Optional: ux-critique"

  UX_DEST="$HOME/.codex/skills/ux-critique"

  if [ -d "$UX_DEST" ] && [ "$FORCE" -eq 0 ]; then
    skip "ux-critique already installed."
  else
    if [ -d "$UX_DEST" ] && [ "$FORCE" -eq 1 ]; then
      info "ux-critique を更新/再インストールします (--force)..."
      rm -rf "$UX_DEST"
    else
      info "ux-critique をインストールします..."
    fi

    TMP_DIR="$(mktemp -d)"
    trap 'rm -rf "$TMP_DIR"' EXIT

    git clone --depth 1 https://github.com/Thecsiz/ux-critique.git "$TMP_DIR/ux-critique" >/dev/null 2>&1

    SRC="$TMP_DIR/ux-critique"
    DEST="$UX_DEST"

    mkdir -p "$DEST"/{agents,references,scripts,facets,kb}

    cp "$SRC"/LICENSE "$SRC"/LICENSE-MIT "$SRC"/LICENSE-CC-BY-4.0 "$SRC"/THIRD_PARTY_NOTICES.md "$DEST/"
    cp "$SRC"/skills/ux-critique/SKILL.md "$DEST/"
    cp "$SRC"/skills/ux-critique/kb-ids.json "$DEST/"
    cp "$SRC"/skills/ux-critique/agents/openai.yaml "$DEST/agents/"
    cp "$SRC"/skills/ux-critique/references/*.md "$DEST/references/"
    cp "$SRC"/skills/ux-critique/scripts/*.js "$DEST/scripts/"
    cp -R "$SRC"/skills/ux-critique/facets/. "$DEST/facets/"
    cp -R "$SRC"/kb/. "$DEST/kb/"

    ok "ux-critique を $DEST にインストールしました。"
  fi
fi

info "インストール確認"

printf '\n--- Codex plugins ---\n'
codex plugin list || true

printf '\n--- MCP servers ---\n'
codex mcp list || true

printf '\n--- Codex skills ---\n'
npx -y skills@latest list --global --agent codex 2>/dev/null || true

cat <<'EOF'

============================================================
Codex UX stack setup complete.
============================================================

Default behavior:
  installed components are skipped.

To force reinstall/update:
  bash install_codex_ux_stack.sh --force

To include ux-critique:
  bash install_codex_ux_stack.sh --deep

To update everything including ux-critique:
  bash install_codex_ux_stack.sh --deep --force

Codex を一度終了し、新しいセッションを開始してください。
EOF
