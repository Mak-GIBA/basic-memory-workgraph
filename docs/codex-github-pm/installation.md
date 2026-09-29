# インストール・更新・解除

[docs一覧](../README.md) · [概要と収録ツール](README.md) · [使い方](usage.md)

## 前提条件

- Linux / WSL2 / macOS、Bash、Python 3.10以上、Codex CLI。
- ユーザーのSkill配置先への書き込み権限。既定では管理者権限は不要です。
- GitHubを操作する場合は、対象にアクセスできるGitHub CLIまたは既存GitHub MCPの認証とネットワーク接続。
- 任意の`gh`自動取得はLinux／macOSのamd64・arm64に対応します。

[トップREADMEの取得手順](../../README.md#はじめに)でリポジトリを取得し、ルートで以下を実行します。
スクリプト単体を保存した場合は、その保存先で実行してください。
Skillだけの配置はオフラインで可能です。Codex本体は導入しません。

## 初回導入

**引数なしで実際にインストールします。** 予定だけを確認する場合は`--dry-run`を付けます。

```bash
bash install_codex_github_pm.sh --dry-run
bash install_codex_github_pm.sh
bash install_codex_github_pm.sh --doctor
```

GitHub CLIがなく、あわせて導入したい場合は通常実行の代わりに次を使います。

```bash
bash install_codex_github_pm.sh --install-gh
```

`gh`が未導入の場合だけ、公式リリースと公開チェックサムを取得・照合し、バイナリを配置します。
既存の`gh`は更新しません。既定の配置先`~/.local/bin`がPATHにない場合は追加してください。
CLI経由で使う場合、未認証なら利用者が`gh auth login --hostname github.com`を実行します。
認証情報を会話へ貼る必要はありません。

## オプション

| オプション・環境変数 | 既定値 | 動作 |
|---|---|---|
| `--help` / `-h` | — | 単一ファイル版のヘルプを表示 |
| `--dry-run` | 無効 | 導入・更新・解除の予定を表示。永続的な書き込みと依存取得をしない |
| `--force` | 無効 | 管理対象の既存Skillをバックアップ後に更新。解除時は編集済みの管理対象ファイルも削除 |
| `--doctor` | 無効 | Skill・CLI・認証の読み取り専用診断 |
| `--uninstall` | 無効 | このインストーラーが管理するファイルを解除 |
| `--install-gh` | 無効 | PATH上に`gh`がない場合に公式バイナリを取得 |
| `--gh-version X.Y.Z` | 適用時の公式最新版 | 任意取得する`gh`の版を固定。`vX.Y.Z`も指定可能 |
| `--skills-dir PATH` | `~/.agents/skills` | Skillを置く親ディレクトリを指定 |
| `--bin-dir PATH` | `~/.local/bin` | 任意取得する`gh`の配置先 |
| `--hostname HOST` | `github.com` | `--doctor`のCLI認証確認先。通常利用時の接続先を切り替える設定ではない |
| `--self-test` | — | 一時環境で内蔵のオフラインテストを実行 |
| `--extract DIRECTORY` | — | 読める形式の埋め込みソースを、未使用または空のディレクトリへ展開 |
| `PYTHON_BIN` | 対応するPythonを自動検出 | 実行するPython 3.10以上のコマンド／パスを指定 |

`--gh-version`には`--install-gh`が必要です。
`--doctor`は`--force`・`--uninstall`・`--install-gh`と併用できません。
`--uninstall`と`--install-gh`も併用できません。`--self-test`と`--extract DIRECTORY`はそれぞれ単独で使います。
独自の`--skills-dir`を使った場合は、診断・更新・解除にも同じ指定が必要です。

## 取得元・配置・変更内容

| 対象 | 取得元・バージョン方針 | 配置・設定変更 |
|---|---|---|
| Skillと参照資料・補助スクリプト | スクリプト内のZIP、v1.1.0。展開前に埋め込みSHA-256を照合 | `~/.agents/skills/github-project-director/` |
| 所有情報 | 導入時に生成。管理対象ファイルとハッシュを記録 | Skill内の`.github-pm-install.json` |
| GitHub CLI | 指定時のみ`cli/cli`の公式GitHub Releases。指定版または取得時の最新版 | `~/.local/bin/gh` |
| 更新・解除のバックアップ | 操作前のSkill全体をZIP化 | Skill親ディレクトリの`.github-project-director.backup-<ID>.zip` |

Skillはユーザー共通で使います。インストーラーはプロジェクト内のファイル、`AGENTS.md`、
Codexの`config.toml`・hooks、Basic Memory、ECC、SpecKit、GitHubデータを変更しません。
GitHub MCPやトークンの登録、ログイン、権限の追加も行いません。
通常導入は依存をダウンロードしませんが、`--doctor`はCLIの認証状態を確認します。

導入前に内容を読む場合は次のように展開できます。これは展開先へ書き込みますが、Skillの導入は行いません。
例のパスが空または未使用であることを確認してください。

```bash
bash install_codex_github_pm.sh --extract /tmp/github-pm-review
```

展開先の`README_EXTRACTED.md`、`scripts/install_github_pm.py`、
`skills/github-project-director/`、`tests/test_github_project_director.py`を参照できます。

## 導入確認

```bash
bash install_codex_github_pm.sh --doctor
```

CLI利用時は`installed: true`、`version: "1.1.0"`、`modified: []`、
`gh: true`、`authenticated: true`、`projects_cli: true`、`codex: true`を確認します。
`modified`は管理対象ファイルの変更・欠落です。利用者が追加したファイルの一覧ではありません。

診断の終了コード0は「Skillがあり、管理対象ファイルに変更がなく、CLI認証が成功」を意味します。
CLI認証がないなど条件を満たさなければ2、所有情報の不正など実行エラーは1です。
既存GitHub MCPだけで利用する場合、CLI認証がなくてもSkillを利用できることがありますが、診断は2になります。
`mcp_server_names`は名前の一覧にすぎず、MCP認証・利用可能な操作の証明ではありません。

`projects_cli: true`はコマンドのヘルプを確認した結果で、個別Projectへのアクセス権を保証しません。
Projectsの利用権限は対象と認証方式に応じて別途確認します。
[公式Projects資料](https://cli.github.com/manual/gh_project) · [公式認証確認資料](https://cli.github.com/manual/gh_auth_status)

導入後は新しいCodexセッションを開始し、`$github-project-director`を呼び出してください。
実際の利用例は[使い方](usage.md)にあります。

## 更新・再実行

通常の再実行は管理対象の既存Skillをスキップし、ローカル編集も保持します。
更新するときは新しい配布スクリプトを取得して、次を実行します。

```bash
bash install_codex_github_pm.sh --force --dry-run
bash install_codex_github_pm.sh --force
bash install_codex_github_pm.sh --doctor
```

`--force`は旧Skill全体をZIPへバックアップしてから配布ファイルを更新します。
配布対象のローカル編集は上書きされます。利用者が追加したファイルは保持しますが、
新しい配布ファイルと衝突すると停止します。所有情報のない同名ディレクトリは強制指定でも上書きしません。
配置先の親を含むシンボリックリンクは拒否します。

同時実行はロックで拒否します。既存Skillの置き換えに失敗した場合は旧配置への復元を試みます。
任意の`gh`導入が先に成功した後でSkill導入が失敗すると、`gh`は残り得ます。
失敗後はエラーと配置先を確認し、無条件に強制実行やロック削除を繰り返さないでください。

## 解除

```bash
bash install_codex_github_pm.sh --uninstall --dry-run
bash install_codex_github_pm.sh --uninstall
```

SkillをZIPへバックアップし、所有情報に記録されたファイルと所有情報を削除します。
利用者の追加ファイル、`gh`、認証設定、バックアップは残します。
管理対象に編集がある場合は停止します。編集内容も削除すると決めた場合は、
`--uninstall --force`でバックアップ後に解除できます。

## 困ったとき

| 状況 | 確認・対処 |
|---|---|
| Pythonの要件エラー | Python 3.10以上を用意し、必要なら`PYTHON_BIN`を指定 |
| 埋め込みチェックサムが一致しない | ファイルの欠損・変更を確認し、配布スクリプトを再取得 |
| `Unmanaged path exists` | 同名の既存Skillを確認。自動上書きできないため、内容を保護して配置を整理 |
| シンボリックリンクのエラー | 実ディレクトリの配置先を指定し、Codexからの検出も確認 |
| `gh`がPATH外に存在する | バイナリのあるディレクトリをPATHへ追加。自動導入による上書きはしない |
| 導入済みSkillに対する`--install-gh`がスキップされる | 更新も行うなら`--force --install-gh`。Skillを保持するなら別途CLIを導入 |
| `authenticated: false` | 利用するホストとCLI認証を確認。MCPの認証とは別に扱う |
| Projectsを読めない／変更できない | 対象Projectと認証方式に合った権限を確認。取得失敗を空の一覧と解釈しない |
| CodexでSkillが見えない | 新しいセッションを開始し、配置先と`SKILL.md`の存在を確認 |
