# SpecKit Upstream：インストール・更新・解除

[概要と収録ツール](README.md) · [使い方](usage.md) · [docs一覧](../README.md)

## 前提条件

- Linux / WSL2、Bash、Python 3.11以上。
- SpecKit CLIも導入する場合は、そのPythonのvenv・pip機能とPyPIへの接続。
- Skillを使うためのCodex環境。Codex自体はインストールしません。

sudoは使わず通常ユーザーで実行します。必要なら`PYTHON_BIN`でPython実行ファイルを指定できます。
リポジトリの取得方法は[トップREADME](../../README.md)を参照してください。
このスクリプトは単体でも利用できます。以下はスクリプトのあるディレクトリで実行します。

## ユーザー共通環境への導入

```bash
# 導入予定の表示。引数なしでも同じ
bash install_speckit_upstream.sh --dry-run

# 実際に導入する
bash install_speckit_upstream.sh --apply

# 現在のターミナルでCLIを見つけられるようにする
export PATH="$HOME/.local/bin:$PATH"
speckit-workbench doctor
```

別のPythonを使う場合の例です。パスは実在するものに置き換えます。

```bash
PYTHON_BIN=/absolute/path/python3.12 bash install_speckit_upstream.sh --dry-run
```

独自資材はファイル内から一時領域に展開します。既存の`specify`がなければ、
専用venvを作って`specify-cli==1.0.8`と依存パッケージを取得します。
既存CLIがある場合は`version`と`init --help`で必要な機能を確認し、非対応なら停止します。
この確認は完全な互換性や配布元の認証を保証するものではありません。

オフラインで独自資材だけを準備する場合は次を使います。

```bash
bash install_speckit_upstream.sh --apply --skip-specify
```

`--skip-specify`はCLIの取得・互換性確認を省略します。後で公式統合を初期化するには、
対応する`specify`が必要です。文書だけのプロジェクト準備には`attach --docs-only`を使えます。

## オプション

| オプション | 動作 |
|---|---|
| `--dry-run`、または指定なし | 導入予定を表示。永続的なインストール先は変更しない |
| `--apply` | ユーザー共通環境へ導入 |
| `--update` | 管理済みで未編集のWorkbench資材を更新対象にする。適用には`--apply`を併用 |
| `--skip-specify` | SpecKit CLIを取得せず、独自資材だけを対象にする |
| `--doctor` | グローバル環境を読み取り専用で診断。単独使用 |
| `--self-test` | 一時環境でオフラインのモックテスト。単独使用 |
| `--extract DIRECTORY` | 読めるソースを指定先へ展開。インストールとは別の書き込み操作で、単独使用 |
| `--help` / `-h` | ヘルプを表示 |

## 配置先

以下は既定のユーザー共通配置です。

| 場所 | 内容 |
|---|---|
| `~/.local/bin/speckit-workbench` | Workbenchの起動用スクリプト |
| `~/.local/bin/specify` | このインストーラーでSpecKitを用意した場合の起動用スクリプト |
| `~/.local/share/speckit-workbench/releases/1.2.1/` | Workbenchコード、テンプレート、参照資料、ガイド |
| `~/.local/share/speckit-workbench/tooling/specify-1.0.8/` | 必要な場合に作成するSpecKit専用venv |
| `~/.local/share/speckit-workbench/backups/` | 更新時のバックアップ |
| `~/.config/speckit-workbench/install.json` | 管理対象とハッシュ等の導入記録 |
| `~/.agents/skills/upstream-*/` | 8つのSkillとエージェントメタデータ |
| `~/.agents/skills/speckit-workbench/` | 共通入口のSkill |

`XDG_DATA_HOME`、`XDG_CONFIG_HOME`、`SWB_BIN_DIR`、`SWB_SKILL_DIR`を指定できます。
いずれも絶対パスを使用します。`SWB_SKILL_DIR`は共通入口自体の保存先で、8つのSkillはその兄弟フォルダーに配置されます。
既定外へ置いた場合は、Codexの探索設定に合っていることを確認してください。
診断・更新・解除時も同じ環境変数を使い、`SWB_BIN_DIR`を変えた場合はその場所をPATHに含めます。

グローバル導入ではECC、Basic Memory、hooks、Codexの`config.toml`、`AGENTS.md`、
アプリのコード、DB、Gitリモートは変更しません。作業プロジェクトの文書配置は次の段階で行います。

## プロジェクトを準備する

以下の`/absolute/path/app`を、存在する作業フォルダーに置き換えます。空フォルダーも使えます。
`APP`はそのプロジェクトの項目IDの接頭辞です。

```bash
# 追加予定を確認する
speckit-workbench attach --project /absolute/path/app --system APP --mode existing

# 対象を確認して適用する
speckit-workbench attach --project /absolute/path/app --system APP --mode existing --apply
```

新規開発では`--mode new`を使います。利用可能なmodeは`new`、`existing`、`change`、`bug`、`refactor`です。
Codexから`$upstream-existing`等を呼び出した場合も、必要に応じてこの準備を案内します。

公式資材がない場合は空の一時領域で`specify init`を実行し、`.specify/`と公式の`speckit-*` Skillを転送します。
標準ではbug extensionと独自の追記用presetもその一時領域で準備します。公式CLIの実行に伴う通信が発生する場合があります。
既存のSpecKit統合は変更せず、不足や不明な構成があれば停止・案内します。競合する既存ファイルを強制上書きしません。

| attachの追加オプション | 用途 |
|---|---|
| `--docs-only` | 公式CLIの初期化を行わず、Workbench文書・設定だけを追加 |
| `--without-bug` | 新規公式統合でbug extensionを省略 |
| `--docs-dir docs/upstream` | 文書の保存先。`docs/`配下を指定 |
| `--approval-profile normal` | 承認段階の粒度。`small` / `normal` / `critical`から選択 |

attachは雛形の配置であり、仕様の策定・承認・アプリの実装はまだ行いません。
Workbench導入済みの同じプロジェクトへ再実行しても、既存文書・初期モード・承認profileは保持します。
文書の使い方と保存先は[利用ガイド](usage.md)を参照してください。

## 更新と導入確認

```bash
bash install_speckit_upstream.sh --dry-run --update
bash install_speckit_upstream.sh --apply --update
speckit-workbench doctor
speckit-workbench doctor --project /absolute/path/app
speckit-workbench commands
```

更新対象は未編集の管理資材だけです。手動編集したSkill等は`--update`でも上書きせず停止します。
同一内容の再実行はスキップし、SpecKit本体は自動更新しません。旧リリースとバックアップは残ります。
導入後はCodexを再起動し、`$upstream-`の入力候補を確認してください。

1.2.0以前からの更新では、通常のMarkdown本文を固定していない旧承認が`LEGACY_APPROVAL_UNBOUND`になります。
文書・承認履歴を消さずに、`$upstream-review`で内容を再確認し、明示承認後に`$upstream-approve`、gateを実施します。
`gate --write`だけでは解決しません。既存プロジェクトへのattach再実行は不要です。

## 解除

```bash
# 削除予定だけを確認
speckit-workbench uninstall

# 管理された未編集ファイルを削除
speckit-workbench uninstall --apply
```

プロジェクトの文書、SpecKit CLI・専用venv、バックアップは残ります。
編集済み資材は削除せず保持します。空のSkillフォルダーが残る場合があります。
既定外の配置先を使った場合は、解除時にも同じ環境変数が必要です。

## 困ったとき・資材を読む

| 状況 | 確認・対処 |
|---|---|
| Pythonの条件で停止 | Python 3.11以上を用意し、必要なら`PYTHON_BIN`を指定 |
| `speckit-workbench`が見つからない | `~/.local/bin`または指定した`SWB_BIN_DIR`をPATHへ追加 |
| 既存specifyが未対応 | CLIの版と`init --help`を確認。インストーラーは自動更新しない |
| 編集済み資材と競合する | 差分と管理記録を確認。`--update`で強制上書きはできない |
| Skillが表示されない | Codexの再起動、配置先、Skillの有効・無効設定を確認 |
| `.specify`の競合・統合不足 | メッセージに示された既存統合を確認。文書だけ必要なら`--docs-only`を検討 |
| gateで承認の古さを指摘された | 最新内容をレビューし、対象IDの明示承認を取り直す |

```bash
# グローバル導入をせずに、保存済みスクリプトから診断
bash install_speckit_upstream.sh --doctor

# 読めるソースを展開する。指定先は存在しないか空のディレクトリ
bash install_speckit_upstream.sh --extract /tmp/speckit-upstream-source

# SpecKitとの境界をモックにしたローカルテスト
bash install_speckit_upstream.sh --self-test
```

埋め込みSHA-256は資材の破損を検出しますが、配布者を認証するものではありません。
自己テストは実Codexからの利用や外部CLIの取得・初期化を含む一連の動作確認とは異なります。
