# インストール・更新・解除

[docs一覧](../README.md) · [概要](README.md) · [使い方](usage.md) · [記録方針と検証](behavior.md)

## 前提条件

- Linux / WSL2 / macOS、Bash、Python 3.10以上、Codex CLI。
- SkillとCodex共通指示の配置先への書き込み権限。既定の配置先では管理者権限は不要です。
- GitHub操作時には、対象にアクセスできるGitHub CLIまたは既存GitHub MCPの認証とネットワーク接続。

[トップREADMEの取得手順](../../README.md#はじめに)でリポジトリを取得し、ルートで実行します。
スクリプト単体を保存した場合は、その保存先で実行してください。
Skillの配置だけならオフラインで可能です。Codex本体は別途必要です。

## 初回導入

**引数なしで実際にインストールします。** 予定だけを確認する場合は`--dry-run`を付けます。

```bash
bash install_codex_github_pm.sh --dry-run
bash install_codex_github_pm.sh
```

これでユーザー共通のSkillと、GitHub関連の依頼でそれを読む共通AGENTSのルールが入ります。
既定のSkill配置先は`~/.agents/skills/github-project-director/`です。
共通ルールは通常`~/.codex/AGENTS.md`へ追加し、既存の文章と各プロジェクトのファイルを保持します。
配置先の詳細は[配置と共通ルール](#配置と共通ルール)にあります。

### GitHub CLIも導入する場合

`gh`がなく、あわせて導入したい場合は、通常のインストールの代わりに次を使います。

```bash
bash install_codex_github_pm.sh --install-gh
```

PATH上に`gh`がない場合だけ、公式リリースのバイナリを取得し、公開チェックサムを照合して配置します。
Linux／macOSのamd64・arm64に対応します。既存の`gh`は更新しません。
既定の配置先`~/.local/bin`がPATHにない場合は追加してください。
既存の導入にあとから追加する場合の注意は[困ったとき](#困ったとき)を参照してください。

## 利用を始める

導入後は、管理したいプロジェクトで**新しいCodexセッション**を開始します。

```text
このプロジェクトの進捗を確認して、残タスクを整理して。まず調査と提案だけ。
```

ログイン・接続手段・管理対象に不足があれば、Codexが必要な準備と不足情報を提案します。
こちらで準備を進めてよいか確認し、本人の認証操作が必要な箇所は案内します。
既に使えるGitHub MCPがあれば、それを利用できます。
詳しい会話例は[使い方](usage.md#ログインや管理対象が不足しているとき)を参照してください。

インストーラー自体はログイン、GitHub MCPの追加、トークン登録、権限の追加を行いません。
自分でCLIのログインを済ませる場合は、利用するホストを指定します。

```bash
gh auth login --hostname github.com
```

認証情報を会話へ貼る必要はありません。接続準備への許可と、Issue投稿などへの許可は別に扱います。

## 導入確認

```bash
bash install_codex_github_pm.sh --doctor
```

診断は読み取り専用です。主に次の項目を確認します。

| 出力 | 確認すること |
|---|---|
| `installed: true`、`version: "1.3.1"` | 現行Skillが配置されている |
| `modified: []` | 管理対象ファイルに変更・欠落がない。利用者の追加ファイルは対象外 |
| `guidance.valid: true` | 共通AGENTSの適用ルールが有効 |
| `gh: true`、`authenticated: true` | CLIが動作し、指定したホストの認証確認が成功 |
| `projects_cli: true` | Projectsコマンドのヘルプを確認できた。個別Projectのアクセス権は別途確認 |
| `codex: true` | PATH上にCodexがある |
| `mcp_server_names` | 登録されたMCPの名前。認証や操作能力の証明ではない |

終了コード0は、Skillがあり、管理対象ファイルに変更がなく、共通ルールが有効で、CLI認証が成功した状態です。
条件不足は2、所有情報の不正などの実行エラーは1です。
**MCPだけで利用する場合、CLI未認証による終了コード2でもSkillを利用できることがあります。**
実際の接続先・権限は、依頼する操作に合わせて確認してください。

自動適用されない場合は、会話欄で`$github-project-director`を明示して試します。
これはCodexへの作業手順であり、必ず起動するプログラムではありません。
起動しただけでIssueへ記録するわけでもありません。

## 更新・再実行

通常の再実行は既存の管理対象Skillをスキップし、ローカル編集も保持します。
更新時は新しい配布スクリプトを取得し、`--force`を使います。

```bash
bash install_codex_github_pm.sh --force --dry-run
bash install_codex_github_pm.sh --force
bash install_codex_github_pm.sh --doctor
```

旧Skill全体と既存の共通AGENTSを、それぞれZIPへバックアップしてから更新します。
v1.1.0からの更新でもこの手順で共通ルールを追加します。通常の再実行だけでは旧版を更新しません。
配布対象のローカル編集は上書きされます。利用者の追加ファイルは保持しますが、配布ファイルと衝突すると停止します。
所有情報のない同名ディレクトリは、`--force`でも上書きしません。

## 解除

```bash
bash install_codex_github_pm.sh --uninstall --dry-run
bash install_codex_github_pm.sh --uninstall
```

SkillをZIPへバックアップし、管理対象ファイル・所有情報・共通AGENTSの管理ブロックを削除します。
共通AGENTSの既存文章や後から追記した文章、利用者の追加ファイル、`gh`、認証設定、バックアップは残します。
このインストーラーが新規作成し、管理ブロック以外が残らない共通AGENTSだけはファイルごと削除します。

管理対象に編集がある場合は停止します。編集内容も削除すると決めた場合は、
`--uninstall --force`でバックアップ後に解除できます。

## 配置と共通ルール

| 対象 | 既定の配置先・役割 |
|---|---|
| Skill、参照資料、表示設定、補助スクリプト | `~/.agents/skills/github-project-director/`。スクリプト内のZIPから配置 |
| 共通の適用ルール | `$CODEX_HOME/AGENTS.md`。空でない`AGENTS.override.md`があればそちらを使用 |
| 所有情報 | Skill内の`.github-pm-install.json`。管理対象のハッシュと共通ルールの配置先を記録 |
| 任意取得するGitHub CLI | `~/.local/bin/gh`。`cli/cli`の公式GitHub Releasesから取得 |
| Skillのバックアップ | Skill親ディレクトリの`.github-project-director.backup-<ID>.zip` |
| 共通AGENTSのバックアップ | 共通指示ディレクトリの`.github-project-director.backup-guidance-<ID>.zip` |

Codex共通指示の配置先は、`--codex-home`、`CODEX_HOME`、`~/.codex`の順に選びます。
管理ブロックにはSkillの実際の絶対パスを記載し、再実行で重複登録しません。
更新・解除では記録済みの共通指示配置先を使います。移動する場合は解除後に再導入してください。
別のSkill配置先から同じ共通ルールを上書きすることはできません。
`--dry-run`の`global_guidance`で変更先を確認できます。

通常導入は依存をダウンロードせず、埋め込みSHA-256を照合して資材を展開します。
Codexの`config.toml`・hooks、Basic Memory、ECC、SpecKit、GitHubデータは変更しません。

### 更新・解除時の保護

配置先の親を含むシンボリックリンクを拒否し、Skillと共通指示の配置先のロックで同時実行を防ぎます。
更新途中の書き込み・置き換えが失敗した場合は、Skillと共通ルールを元に戻します。
他のプロセスが共通指示を書き換えた場合は上書きせず停止し、復元用バックアップを残します。
強制終了や復元時のディスク障害まで自動回復を保証する仕組みではありません。
`gh`の導入後にSkill導入が失敗すると、`gh`は残り得ます。
失敗後はエラーと配置先を確認し、無条件に強制実行やロック削除を繰り返さないでください。

## 詳細オプション

| オプション・環境変数 | 既定値 | 動作 |
|---|---|---|
| `--help` / `-h` | — | 単一ファイル版のヘルプを表示 |
| `--dry-run` | 無効 | 導入・更新・解除の予定を表示。永続的な書き込みや依存取得はしない |
| `--force` | 無効 | バックアップ後に既存Skillを更新。解除時は編集済みの管理対象ファイルも削除 |
| `--doctor` | 無効 | Skill・共通ルール・CLI・認証の読み取り専用診断 |
| `--uninstall` | 無効 | このインストーラーが管理するファイルを解除 |
| `--install-gh` | 無効 | PATH上に`gh`がない場合に公式バイナリを取得 |
| `--gh-version X.Y.Z` | 取得時の公式最新版 | 任意取得する`gh`の版を固定。`vX.Y.Z`も可 |
| `--skills-dir PATH` | `~/.agents/skills` | Skillを置く親ディレクトリ |
| `--codex-home PATH` | `CODEX_HOME`、未指定なら`~/.codex` | 共通AGENTSの配置先。更新・解除では記録済み配置先を再利用 |
| `--bin-dir PATH` | `~/.local/bin` | 任意取得する`gh`の配置先 |
| `--hostname HOST` | `github.com` | 診断時のCLI認証確認先。通常利用の接続先を切り替える設定ではない |
| `--self-test` | — | 一時環境で内蔵のオフラインテストを実行 |
| `--extract DIRECTORY` | — | 埋め込みソースを未使用または空のディレクトリへ展開 |
| `PYTHON_BIN` | 対応するPythonを自動検出 | Python 3.10以上のコマンド／パスを指定 |

`--gh-version`には`--install-gh`が必要です。
`--doctor`は`--force`・`--uninstall`・`--install-gh`と併用できません。
`--uninstall`と`--install-gh`も併用できません。`--self-test`と`--extract DIRECTORY`はそれぞれ単独で使います。
独自の`--skills-dir`を使った場合は、診断・更新・解除にも同じ指定が必要です。

## 配布内容を確認する

導入せずに内容を読む場合は、未使用または空のディレクトリへ展開します。展開先にはファイルを書き込みます。

```bash
bash install_codex_github_pm.sh --extract /tmp/github-pm-review
```

`README_EXTRACTED.md`、`scripts/install_github_pm.py`、`skills/github-project-director/`、
`tests/test_github_project_director.py`、`tests/behavioral-scenarios.md`を確認できます。
Skill内には操作・計画・文章の参照資料があります。検証の使い分けは[記録方針と検証](behavior.md)にあります。

## 困ったとき

| 状況 | 確認・対処 |
|---|---|
| Pythonの要件エラー | Python 3.10以上を用意し、必要なら`PYTHON_BIN`を指定 |
| 埋め込みチェックサムが一致しない | ファイルの欠損・変更を確認し、配布スクリプトを再取得 |
| `Unmanaged path exists` | 同名の既存Skillを確認し、内容を保護して配置を整理 |
| シンボリックリンクのエラー | 実ディレクトリの配置先を指定し、Codexからの検出も確認 |
| `gh`がPATH外にある | バイナリのあるディレクトリをPATHへ追加 |
| 導入済みSkillに対する`--install-gh`がスキップされる | 更新も行うなら`--force --install-gh`。Skillを保持するなら別途CLIを導入 |
| `authenticated: false` | 利用するホストとCLI認証を確認。MCPの認証とは別に扱う |
| Projectsを読めない／変更できない | 対象と認証方式に合った権限を確認。取得失敗を空の一覧と解釈しない |
| 共通ルールが編集されている | 意図して置き換え／解除する場合は`--force`でバックアップして実行 |
| 共通ルールが欠落・区切りが不正 | バックアップから管理ブロックを復元。不正な区切りは`--force`でも無視しない |
| 共通ルールが別のAGENTSに隠れている | 既存導入を解除後、再導入して有効な共通指示ファイルへ登録 |
| CodexでSkillが見えない | 新しいセッションを開始し、配置先と`SKILL.md`の存在を確認 |

CLIの権限・機能の確認には[公式Projects資料](https://cli.github.com/manual/gh_project)と
[公式認証確認資料](https://cli.github.com/manual/gh_auth_status)も参照できます。
これらの説明は2026-09-30に確認した公式資料と、配布物の実装に基づきます。
