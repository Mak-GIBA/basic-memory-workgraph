# SpecKit Upstream：インストール・更新・解除

[概要と収録ツール](README.md) · [使い方](usage.md) · [docs一覧](../README.md)

## 前提条件

- Linux / WSL2、Bash、Python 3.11以上。
- 通常の組み立てには、GitHubの固定版スクリプトを取得できる通信環境。GitHubへのログインは不要。
- SpecKit CLIも導入する場合は、そのPythonのvenv・pip機能とPyPIへの接続。
- Skillを使うためのCodex環境。Codex自体はインストールしません。

sudoは使わず通常ユーザーで実行します。必要なら`PYTHON_BIN`でPython実行ファイルを指定できます。
リポジトリの取得方法は[トップREADME](../../README.md)を参照してください。
以下はスクリプトのあるディレクトリで実行します。

配布版2.0.5は、固定版へ同梱の更新資材を適用する組み立て用スクリプトです。
2026-10-10に組み立ての停止原因を修正し、オフライン組み立て・両ツールの自己テストと、このPCでの更新・診断を確認しました。
[検証結果](../design-research/validation.md)に、同梱試験、組み立て、実環境への更新の範囲を分けて記載しています。

## ユーザー共通環境への導入

```bash
# 組み立て予定の表示。引数なしでも同じ
bash install_speckit_upstream.sh --dry-run

# 組み立て・検証が成功した後に導入する
bash install_speckit_upstream.sh --apply

# 配布物の8つのCodex入口を確認する
bash install_speckit_upstream.sh --list-skills
```

`--dry-run`は通信・導入先の変更・既存配置の検査を行いません。
予定表示の成功だけでは、実導入の可否や編集済み資材の有無は判断できません。
`--version`は配布スクリプトの版、`--list-skills`は配布物の入口を表示し、導入済みの版や状態は調べません。

導入できた後に、現在のターミナルでCLIを見つけられるようにします。

```bash
export PATH="$HOME/.local/bin:$PATH"
speckit-workbench doctor
```

別のPythonを使う場合の例です。パスは実在するものに置き換えます。

```bash
PYTHON_BIN=/absolute/path/python3.12 bash install_speckit_upstream.sh --dry-run
```

組み立て後の導入処理で既存の`specify`がなければ、専用venvを作り、`specify-cli==1.0.8`と依存パッケージを取得します。
既存CLIがある場合は`version`と`init --help`で必要な機能を確認し、非対応なら停止します。
この確認は完全な互換性や配布元の認証を保証するものではありません。

## 組み立てとオフライン利用

コミット`d3f46e0d591b45cb2423317030a489b91566e891`の元インストーラー2本を取得・照合し、
同梱の更新資材からDesign Research 2.4.0とUpstream 2.0.5を組み立てます。
両ツールの検証が成功した場合に、指定した側の導入処理へ進みます。
`--doctor`・`--self-test`・`--extract`も、配布スクリプトから呼ぶ場合は先に組み立てます。

再配布用の通常インストーラーを生成する操作です。出力先は未使用または空のディレクトリにします。

```bash
bash install_speckit_upstream.sh --build-only ./offline-installers
```

成功した場合は両スクリプトとビルドログを出力します。この操作では導入しません。
組み立てと導入の確認範囲は[検証結果](../design-research/validation.md)を参照してください。

通信せず組み立てるには、固定コミットの元スクリプト2本を用意します。
更新用ラッパーや編集済みの同名スクリプトは代用できません。

```bash
bash install_speckit_upstream.sh \
  --base-dir /absolute/path/pinned-base --offline --build-only ./offline-installers

# 生成に成功した後、SpecKit CLIの取得・互換性確認も省略して導入
bash ./offline-installers/install_speckit_upstream.sh --apply --skip-specify
```

`--offline`だけでは組み立てできず、`--base-dir`が必要です。
配布版に`--skip-specify`を付けるだけでは、ベース取得の通信は省略されません。
生成済みの通常インストーラーでは、`--skip-specify`によりSpecKit CLIの取得・互換性確認を省けます。
後で公式統合を初期化するには対応する`specify`が必要です。文書だけのプロジェクト準備には`attach --docs-only`を使えます。
共通の組み立ての詳細は[Design Researchの導入手順](../design-research/installation.md#組み立てとオフライン利用)も参照してください。

## オプション

| 組み立て用のオプション | 動作 |
|---|---|
| `--help` / `-h`、`--version` | ヘルプ / 配布版を表示 |
| `--dry-run`、または指定なし | 組み立て予定を表示。通信・導入先変更・導入先検査なし |
| `--list-skills` | 配布物の8つのCodex入口を列挙。導入状態は検査しない |
| `--base-dir DIR` | 指定された固定版の元スクリプト2本を使用 |
| `--offline` | ベース取得の通信を禁止。組み立てには`--base-dir`が必要 |
| `--build-only DIR` | 両ツールの通常インストーラーとログを生成。導入なし |
| `--extract-bundle DIR` | 更新資材とテストを展開。通信・導入なし |
| `--bundle-self-test` | 同梱パッケージのオフライン契約テストを実行 |

`--list-skills`・`--build-only`・`--extract-bundle`・`--bundle-self-test`は1つずつ使い、導入用の引数とは組み合わせません。
`--dry-run --build-only DIR`は生成予定だけを表示します。

| 組み立て後へ渡すオプション | 動作 |
|---|---|
| `--apply` | ユーザー共通環境へ導入 |
| `--update` | 管理済みで未編集の資材を更新対象にする。適用には`--apply`を併用 |
| `--skip-specify` | SpecKit CLIの取得・互換性確認を省略 |
| `--doctor` | グローバル環境を読み取り専用で診断。単独使用 |
| `--self-test` | 組み立て後のインストーラーの内蔵テストを実行。単独使用 |
| `--extract DIR` | 組み立て後の読みやすいソースを展開。導入とは別の書き込み操作で、単独使用 |

## 配置先

以下は既定のユーザー共通配置です。

| 場所 | 内容 |
|---|---|
| `~/.local/bin/speckit-workbench` | Workbenchの起動用スクリプト |
| `~/.local/bin/specify` | このインストーラーでSpecKitを用意した場合の起動用スクリプト |
| `~/.local/share/speckit-workbench/releases/2.0.5/` | Workbenchコード、テンプレート、参照資料、ガイド |
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
導入後はCodexを再起動し、`$upstream-`の入力候補と、`speckit-workbench doctor`の導入版・配置先を確認してください。

2.0.5では、単一の`$design-research`入口への引き渡し、研究テーマの分割・統合、新規・変更設計のv2対応を使います。
新規プロジェクトの雛形は3文書です。既存資料・承認履歴は保持し、attach再実行やSkill更新だけでは移行しません。任意移行は[使い方](usage.md#既存資料を3文書へ移行する)を参照してください。
既存文書の本文・要件・根拠を変更した場合は、通常どおり再レビューします。
Design Researchは別途[導入・更新](../design-research/installation.md)します。SpecKitの更新だけではDesign Researchは導入・更新されません。

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
| 組み立ての自己テストで停止 | 導入は行われない。[現在の検証結果](../design-research/validation.md)とエラーを確認 |
| Pythonの条件で停止 | Python 3.11以上を用意し、必要なら`PYTHON_BIN`を指定 |
| `speckit-workbench`が見つからない | `~/.local/bin`または指定した`SWB_BIN_DIR`をPATHへ追加 |
| 既存specifyが未対応 | CLIの版と`init --help`を確認。インストーラーは自動更新しない |
| 編集済み資材と競合する | 差分と管理記録を確認。`--update`で強制上書きはできない |
| Skillが表示されない | Codexの再起動、配置先、Skillの有効・無効設定を確認 |
| `.specify`の競合・統合不足 | メッセージに示された既存統合を確認。文書だけ必要なら`--docs-only`を検討 |
| gateで承認の古さを指摘された | 最新内容をレビューし、対象IDの明示承認を取り直す |

```bash
# 通信せずに、組み立て用の更新元とテストを読む
bash install_speckit_upstream.sh --extract-bundle /tmp/speckit-upstream-upgrade
bash install_speckit_upstream.sh --bundle-self-test

# 以下は先に組み立てるため、通信が発生し得る
bash install_speckit_upstream.sh --doctor
bash install_speckit_upstream.sh --extract /tmp/speckit-upstream-source
bash install_speckit_upstream.sh --self-test
```

展開先は存在しないか空のディレクトリにします。
`--extract-bundle`は更新元、`--extract`は組み立て後の資材を読む操作です。
導入済みCLIの診断には`speckit-workbench doctor`を使い、配布スクリプトの組み立てを経由する診断と区別します。
埋め込みSHA-256は資材の破損を検出しますが、配布者を認証するものではありません。
同梱試験、組み立て後の内蔵試験、実Codexや外部CLIを含む動作確認は、それぞれ検証範囲が異なります。
