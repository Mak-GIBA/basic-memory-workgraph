# Codex UX Stack：インストール・更新・解除

[概要と収録ツール](README.md) · [使い方](usage.md) · [docs一覧](../README.md)

## 前提条件

- Linux / WSL2、Bash、Codex CLI。
- `codex plugin`と`codex mcp`を使える環境。
- Node.js 20以上と`npx`。これはこのインストーラーが検査する条件です。
- `--deep`を使う場合はGit。
- pluginカタログ、npm、Skillの配布元へのネットワーク接続。任意追加ではGitHubにも接続します。

リポジトリ一式の取得方法は[トップREADME](../../README.md)を参照してください。
以下のコマンドはリポジトリのルートで実行します。通常ユーザーで利用します。

## 初回導入

```bash
# ヘルプの表示だけ
bash install_codex_ux_stack.sh --help

# 標準の4ツールを実際に導入・登録
bash install_codex_ux_stack.sh
```

ux-critiqueも導入する場合は、代わりに次を実行します。標準の4ツールも対象です。

```bash
bash install_codex_ux_stack.sh --deep
```

**dry-run機能はありません。引数なしでも実際に変更します。**
既存のplugin・Skill・MCP登録が検出された場合は、通常はその項目をスキップします。
スキップは配置・登録の検出に基づき、動作や全ファイルの整合性を保証する検査ではありません。

## オプション

| オプション | 動作 |
|---|---|
| なし | 標準4ツールのうち不足するものを導入・登録 |
| `--deep` | 第三者Skillのux-critiqueを追加 |
| `--force` | 検出済みの対象も再導入・再登録 |
| `--deep --force` | ux-critiqueを含めて再導入 |
| `--help` / `-h` | ヘルプを表示して終了 |

ここでの`--deep`は「追加ツールも入れる」という指定です。
導入後にux-critiqueへ渡すレビュー深度の`--deep`とは別です。

## 取得元・変更内容

| 対象 | スクリプトが行う処理 | 配置・設定 |
|---|---|---|
| Product Design | `product-design@openai-curated-remote`を追加 | Codex CLIが管理するplugin環境 |
| Build Web Apps | `build-web-apps@openai-curated-remote`を追加 | Codex CLIが管理するplugin環境 |
| web-design-guidelines | `skills@latest`で`vercel-labs/agent-skills`から指定Skillを取得 | `--global --agent codex`の配置先。実際の場所はskills CLIの一覧で確認 |
| Playwright MCP | `playwright`という名前で`npx -y @playwright/mcp@latest`を登録 | CodexのMCP設定 |
| ux-critique | `Thecsiz/ux-critique`を一時ディレクトリにcloneして資材をコピー | `~/.codex/skills/ux-critique/` |

インストーラーは外部ツールのバージョンを固定しません。MCPのパッケージ取得は、登録後の起動時にも発生し得ます。
ux-critiqueにはSkill、エージェントメタデータ、参照資料、スクリプト、知識ベース、ライセンス類を配置します。

ux-critiqueの保存先はスクリプト内で`$HOME/.codex/skills/ux-critique`に固定されており、
`CODEX_HOME`へ置き換える処理はありません。pluginとMCPの設定先はCodex CLI側の設定に従います。
このスクリプトはWorkgraphのhooksや保存方針、アプリのコードを編集しません。

## 導入確認

```bash
codex plugin list
codex mcp get playwright --json
npx -y skills@latest list --global --agent codex
```

`npx`による一覧取得でもCLIのダウンロードが起きる場合があります。
`--deep`でコピーしたux-critiqueは、Codex側のSkill候補と保存先でも確認してください。

Codexを終了して新しいセッションを開始し、pluginとSkillを利用します。
実際のブラウザー操作は[使い方](usage.md)の例で別途確認します。
末尾の一覧コマンドは失敗しても処理を継続するため、完了メッセージだけで全機能の動作確認済みとは判断しません。

## 更新・再実行

```bash
# 不足分だけを導入
bash install_codex_ux_stack.sh

# 標準構成を再導入・再登録
bash install_codex_ux_stack.sh --force

# 任意追加を含めて再導入
bash install_codex_ux_stack.sh --deep --force
```

`--force`はpluginを一度削除して追加し、Playwright MCPも削除して登録し直します。
独自のMCP起動オプションがある場合は事前に控えてください。
`--deep --force`では既存のux-critiqueフォルダーを削除してから再配置するため、手動編集は失われます。
一括バックアップ・ロールバック機能はなく、途中で失敗すると先に成功した導入分は残ります。

## 解除

一括アンインストール機能はありません。不要な項目だけ個別に解除します。

```bash
codex plugin remove product-design@openai-curated-remote
codex plugin remove build-web-apps@openai-curated-remote
codex mcp remove playwright
```

Skillは導入先と手動編集の有無を確認して個別に削除します。
web-design-guidelinesはskills CLIの管理対象とリンク先を確認し、CLIの削除手順に従ってください。
ux-critiqueはこのスクリプトがコピーした`~/.codex/skills/ux-critique/`が対象です。
MCP登録の削除はnpmキャッシュやブラウザーの削除ではありません。作成済みアプリや成果物も残ります。

<a id="troubleshooting"></a>

## 困ったとき

| 状況 | 確認・対処 |
|---|---|
| pluginが見つからない | `codex plugin list --available --json`で配布名・利用可否を確認。スクリプトは`openai-curated-remote`を指定している |
| `plugin` / `mcp`コマンドに未対応 | 対応するCodex CLIを用意する |
| Node.jsの条件で停止 | `node --version`、`command -v node`、`command -v npx`を確認する |
| Skillが候補に出ない | Codexを再起動し、導入先とSkillの有効・無効設定を確認する |
| Playwright MCPが起動しない | 登録された起動コマンド、Node.js、通信、ブラウザーとOS依存関係を[公式資料](https://github.com/microsoft/playwright-mcp)で確認する |
| 途中まで導入して止まった | エラーと一覧を確認し、原因を直して再実行。`--force`は既存内容を置き換える範囲を確認してから使う |

配布カタログは環境や時期によって変わります。別marketplaceへ推測で切り替える前に、実際の一覧を確認してください。
