# インストール・更新・解除

[docs一覧](../README.md) · [概要と収録ツール](README.md) · [使い方](usage.md)

## 前提条件

- Linux / WSL2 / macOS、Bash、Python 3.10以上。調査CLIはホスト単位のロックにUnix向け機能を使います。
- Skillを利用するCodex環境と、配置先への書き込み権限。
- 文献の実検索を行う場合はネットワーク接続。導入自体には不要です。

Python標準ライブラリで動き、pip・npmによる依存導入やLLM APIキーは不要です。
Codex本体、ブラウザー・PDFツール、MCPはインストーラーに含みません。
[トップREADME](../../README.md#はじめに)の手順で取得し、リポジトリのルートで実行します。
スクリプト単体を保存した場合は、その保存先で実行してください。

## 初回導入

**引数なしで実際にインストールします。** 予定だけを確認するには`--dry-run`を使います。

```bash
bash install_design_research.sh --dry-run --json
bash install_design_research.sh
bash install_design_research.sh --status --json
bash install_design_research.sh --doctor --json
```

既定では`${CODEX_HOME:-~/.codex}/skills/design-research/`に配置します。
前のGitHub Project Directorの既定値`~/.agents/skills/`とは異なります。

特定のプロジェクトへ導入する場合は、通常実行の代わりに次を使います。
`/path/to/repo`は実際のプロジェクトへ置き換えてください。

```bash
bash install_design_research.sh --project /path/to/repo
bash install_design_research.sh --project /path/to/repo --status --json
```

この場合は`PROJECT/.codex/skills/design-research/`を作成します。
別のSkill探索先を使う場合は`--skills-dir PATH`で親ディレクトリを指定します。
導入後にSkillが見つからない場合は、新しいCodexセッションを開始してください。

## オプション

| オプション・環境変数 | 既定値 | 動作 |
|---|---|---|
| `--help` / `-h` | — | ヘルプを表示 |
| `--version` | — | インストーラーの版を表示 |
| `--skills-dir PATH` | 未指定 | Skill探索先の親ディレクトリを指定 |
| `--project PATH` | 未指定 | `PATH/.codex/skills`を親ディレクトリとして使用 |
| `CODEX_HOME` | `~/.codex` | 上記2つが未指定の場合に、その下の`skills`を使用 |
| `PYTHON_BIN` | `python3` | Python 3.10以上のコマンド／パスを指定 |
| `--dry-run` | 無効 | 導入・更新・解除の予定だけを表示 |
| `--update` | 無効 | 管理対象Skillを配布資材へ置き換え |
| `--force` | 無効 | 編集済みの管理対象Skillもバックアップ後に置き換え・解除。単独では更新を意味する |
| `--uninstall` | 無効 | 管理対象Skillをバックアップ先へ移動して解除 |
| `--status` | 無効 | 所有情報・版・ファイルハッシュに基づく導入状態を表示 |
| `--doctor` | 無効 | Python、Codex CLIの有無、任意環境変数の有無などをオフラインで診断 |
| `--self-test` | 無効 | 一時ディレクトリで内蔵テストを実行 |
| `--print-mcp-config` | 無効 | 任意のMCP設定例を表示。登録や設定変更はしない |
| `--extract DIR` | 未指定 | 埋め込みSkillを未使用または空のディレクトリへ展開 |
| `--json` | 無効 | 通常の結果表示をJSONのみにする。MCP設定例の表示はTOMLのまま |

`--project`と`--skills-dir`は併用できません。
`--update`・`--uninstall`・`--status`・`--doctor`・`--self-test`・`--print-mcp-config`・`--extract`は相互排他です。
`--dry-run`は導入・更新・解除にのみ使えます。`--force`も診断・状態表示・テスト・設定例表示・展開には使えません。
既定以外の配置先を選んだ場合、更新・解除・状態確認にも同じ指定を付けます。

## 取得元・配置・変更内容

| 対象 | 取得元・版 | 配置・変更 |
|---|---|---|
| Skill・補助コード・資料・雛形 | スクリプト内の圧縮JSON、v1.1.0。資材全体と各ファイルのSHA-256を照合 | 選択した親ディレクトリの`design-research/` |
| 所有情報 | 導入時に生成 | Skill内の`.design-research-install.json` |
| 更新・解除時のバックアップ | 以前のSkillディレクトリ全体 | Skill親ディレクトリの1階層上にある`.design-research-backups/<配置先の識別子>/<日時とID>/` |

既定のバックアップ先は`${CODEX_HOME:-~/.codex}/.design-research-backups/`配下です。
導入はネットワーク通信をせず、MCP・`config.toml`・hooks・既存の他のSkillを変更しません。
調査を始めるときの出力や通信・キャッシュは[使い方](usage.md)を参照してください。

導入せずに資料を読むには次のように展開します。例のパスが空か未使用であることを確認してください。
この操作は展開先へ書き込みます。

```bash
bash install_design_research.sh --extract /tmp/design-research-review
```

展開先に`SKILL.md`、`agents/`、`scripts/`、`references/`、`templates/`が作成されます。
導入処理そのものはシェルスクリプト内のPythonを確認してください。

## 導入確認

`--status --json`で`state: "installed"`、`version: "1.1.0"`、`modified: false`を確認します。
未導入は`absent`、所有情報を認識できない既存ディレクトリは`unmanaged`です。
`modified`は管理対象の変更・欠落に加えて追加ファイルも検出します。Pythonキャッシュは除外します。
状態表示は`absent`でも正常終了するため、終了コードだけでは導入済みか判断できません。

`--doctor`は導入済みファイルを検査する機能ではありません。
Codex CLIと任意の`SEMANTIC_SCHOLAR_API_KEY`・`CROSSREF_MAILTO`の有無を示しますが、
APIへ接続せず、認証や検索の成功を保証しません。キーの値は表示しません。

## 更新・再実行

引数なしの再実行は既存の管理対象Skillを保持します。版が違う場合や編集がある場合も自動で更新しません。
新しい配布スクリプトを取得したら、次で更新します。

```bash
bash install_design_research.sh --update --dry-run --json
bash install_design_research.sh --update
bash install_design_research.sh --status --json
```

ローカル編集や追加ファイルがあると通常の更新・解除は停止します。
内容を確認したうえで`--update --force`を指定すると、旧ディレクトリ全体をバックアップ先へ移し、
新しい配布資材だけを有効な配置先へ置きます。**追加ファイルやローカル編集はバックアップに残り、更新後のSkillへ自動で引き継がれません。**
所有情報のない同名ディレクトリは`--force`でも上書きしません。

同時実行はロックで拒否し、導入前後に資材と配置先を確認します。
新しい配置への切り替えが失敗した場合は、移動済みの旧ディレクトリを戻す処理があります。
失敗時はエラーと実際の配置・バックアップを確認してから再実行してください。

## 解除

```bash
bash install_design_research.sh --uninstall --dry-run --json
bash install_design_research.sh --uninstall
```

管理対象Skillのディレクトリ全体をバックアップ先へ移動します。ファイル単位の削除ではありません。
編集や追加がある場合は停止し、`--uninstall --force`を明示した場合にそれらも含めて退避します。
調査成果物、文献キャッシュ、バックアップは解除後も残ります。自動復元用の専用オプションはありません。

## 困ったとき

| 状況 | 確認・対処 |
|---|---|
| Pythonエラー | Python 3.10以上を用意し、必要なら`PYTHON_BIN`を指定 |
| 資材チェックサムの不一致 | スクリプトの欠損・変更を確認し、元の配布物を再取得 |
| `unmanaged`または上書き拒否 | 同名ディレクトリと所有情報を確認し、既存内容を保護して配置を整理 |
| ローカル編集で停止 | 差分・追加ファイルを確認。置き換え・退避を望む場合のみ`--force`を使用 |
| シンボリックリンクで停止 | 親ディレクトリも含め、実ディレクトリの配置先を使用 |
| ロックが残っている | 実行中のインストーラーがないことを確認してから残存ロックを扱う |
| Skillが見えない | 配置先と`SKILL.md`を確認し、新しいCodexセッションを開始 |
| 検索失敗・キャッシュなし | [使い方](usage.md)の通信許可・取得範囲・オフラインの説明を確認 |
