# インストール・更新・解除

[docs一覧](../README.md) · [概要](README.md) · [使い方](usage.md) · [検証結果](validation.md)

## 前提条件

- Linux / WSL2 / macOS、Bash、Python 3.10以上、配置先への書き込み権限。
- ハーネスには、認証済みCodex CLIと動作するコマンド用サンドボックス。
- 文献・公開資料を実際に調べる場合は通信環境。

Python標準ライブラリで動くため、pip・npm・ECC・別のLLM APIキーの導入は不要です。
Codex本体やアプリ側のテスト依存、ブラウザー、MCPは含みません。
この版の制御テストはLinuxで確認しています。macOSの実機確認は未実施です。

[トップREADME](../../README.md#はじめに)から取得し、保存先で次を実行します。
スクリプト単体でも使えます。**引数なしで実際にインストールします**。

## 初回導入

```bash
bash install_design_research.sh --dry-run --json
bash install_design_research.sh
bash install_design_research.sh --status --json
bash install_design_research.sh --doctor --json
```

新規のユーザー共通配置は `~/.agents/skills/design-research/` です。
導入結果には、実際の配置先とBashで呼び出す診断コマンドを表示します。
導入後にSkillが見つからない場合はCodexを再起動してください。

プロジェクトだけで使う場合は、通常の導入の代わりに次を指定します。
`/path/to/repo`は実際の対象へ置き換えてください。

```bash
bash install_design_research.sh --project /path/to/repo
```

新規配置は `PROJECT/.agents/skills/design-research/` です。
独自の配置先を使う場合は、`--skills-dir PATH`でSkillを置く親ディレクトリを指定します。
更新・解除・診断にも、選んだ配置先の指定を付けます。

## 既存版からの更新

旧版の `~/.codex/skills`、`CODEX_HOME/skills`、プロジェクトの `.codex/skills` に
既存のDesign Researchが1つあれば、その場所を再利用します。
新しい場所へ重複して導入しません。旧配置の自動移動も行いません。
現在のCodexでSkillが見つかるかは、更新後に確認してください。

```bash
bash install_design_research.sh --update --dry-run --json
bash install_design_research.sh --update
bash install_design_research.sh --status --json
```

引数なしの再実行は既存の管理対象Skillを保持します。更新には `--update` が必要です。
候補の配置先に同名Skillが複数あれば停止し、候補を表示します。
`--skills-dir`で更新対象の親を明示してください。

管理対象のファイルに編集・欠落・追加がある場合は、通常の更新・解除を止めます。
確認後に `--update --force` を指定すると、旧ディレクトリ全体をコピーして
ハッシュを照合し、新しい資材へ切り替えます。
**ローカル編集と追加ファイルはバックアップに残り、新版へ自動で引き継がれません**。
所有情報のない同名ディレクトリは `--force` でも上書きしません。

## 状態確認と診断

`--status --json` の `state: "installed"`、`version: "2.0.1"`、`modified: false` を確認します。
未導入は `absent`、所有情報を認識できない既存ディレクトリは `unmanaged` です。
追加ファイルも変更として検出します。Pythonキャッシュは除きます。
状態表示は未導入でも正常終了するため、終了コードだけでは導入済みか判断できません。

`--doctor --json` は、導入状態と実行環境を分けて表示します。

| 項目 | 確認する内容 |
|---|---|
| `installed_integrity` | 導入済みSkillの所有情報・ファイルの整合性 |
| `installed_harness_ready` | 現在の版のハーネス資材が導入されているか |
| `harness_environment_ready` | Codex CLI、構造化execの引数、コマンド用サンドボックスの起動 |
| `ready` | 現在のハーネスと実行環境が揃っているか |

準備が整っていない場合は終了コード2を返します。診断はモデルを呼び出さず、学術APIにも接続しません。
認証・モデル応答・実API検索・Codex画面からの実行成功まで保証するものではありません。
旧版のファイルが整合していても、新しいハーネスが未導入なら準備完了にはしません。
サンドボックスに問題があれば実行を止め、制限を外して続行しません。

## オプション

| オプション・環境変数 | 動作 |
|---|---|
| `--help` / `-h`、`--version` | ヘルプ／版を表示 |
| `--skills-dir PATH` | Skill配置先の親を明示 |
| `--project PATH` | プロジェクト内の配置先を選択。新規は `.agents/skills` |
| `CODEX_HOME` | 既存配置を探す際に `CODEX_HOME/skills` も確認 |
| `PYTHON_BIN` | 使用するPython 3.10以上。既定は `python3` |
| `--dry-run` | 導入・更新・解除の予定を表示。配置先・バックアップへ書き込まない |
| `--update` | 管理対象Skillを新版へ置き換え |
| `--force` | 編集済みの管理対象もバックアップ後に更新・解除。単独なら更新扱い |
| `--uninstall` | バックアップ後、管理対象Skillを解除 |
| `--status` | 導入状態を表示 |
| `--doctor` | 導入済み資材とハーネスの実行環境を診断 |
| `--self-test` | 一時ディレクトリで内蔵テストを実行 |
| `--print-mcp-config` | 任意のMCP設定例を表示。登録・変更は行わない |
| `--extract DIR` | 埋め込み資材を未使用／空のディレクトリへ展開 |
| `--json` | 結果をJSONで表示。MCP設定例はTOML |

`--project` と `--skills-dir` は併用できません。
操作モードの `--update`・`--uninstall`・`--status`・`--doctor`・`--self-test`・
`--print-mcp-config`・`--extract` は相互排他です。
`--dry-run` と `--force` は、診断・状態表示・テスト・設定例表示・展開には使えません。

## 資材とバックアップ

| 対象 | 保存先・扱い |
|---|---|
| Skill・Bash・Python・資料 | 選んだSkill親の `design-research/`。埋め込み資材全体と各ファイルのSHA-256を照合 |
| 所有情報 | Skill内の `.design-research-install.json` |
| バックアップ | Skill親の1階層上の `.design-research-backups/<配置先の識別子>/<日時とID>/` |

新規のユーザー共通配置では、バックアップは `~/.agents/.design-research-backups/` 配下です。
更新・解除時は旧資材をコピーし、バックアップが別のファイルシステムでも退避できる形にしています。
新しい資材を検査した後、配置先と同じ親の一時ディレクトリを使って切り替えます。
切り替えに失敗した場合は旧配置を戻します。失敗時は表示された配置先・バックアップを確認してください。
同時実行はロックで拒否し、親を含むシンボリックリンクの配置先も拒否します。

導入は通信せず、`config.toml`、hooks、MCP、他のSkillを変更しません。
研究・レビュー成果物は利用先プロジェクトに保存され、更新・解除の対象に含めません。
Skillによる検証・実験のMemory保存は、既存のBasic Memory Workgraphを使う任意機能です。
このインストーラーはWorkgraphの導入や設定・保存方針の変更を行いません。

## 展開して確認する・解除する

```bash
bash install_design_research.sh --extract /tmp/design-research-inspection
bash install_design_research.sh --self-test --json
```

展開先は未使用か空にしてください。展開はその場所へ書き込みます。
`SKILL.md`、`agents/`、`scripts/`、`references/`、`templates/` を確認できます。
保守用の正本は [tools/design-research](../../tools/design-research/) です。
配布物を使う側には、正本ディレクトリの同梱は不要です。

```bash
bash install_design_research.sh --uninstall --dry-run --json
bash install_design_research.sh --uninstall
```

編集済みの解除は、内容を確認したうえで `--uninstall --force` を使います。
成果物・キャッシュ・バックアップは残ります。自動復元専用のオプションはありません。

## 困ったとき

| 状況 | 対処 |
|---|---|
| Pythonエラー | Python 3.10以上を用意し、必要なら `PYTHON_BIN` を指定 |
| チェックサム不一致 | 配布物の欠損・変更を確認し、元の配布スクリプトを取得 |
| 同名Skillが複数／`unmanaged` | 候補と所有情報を確認し、対象の親を `--skills-dir` で明示。管理外の内容は保護 |
| 編集で更新が止まる | 差分を確認し、置き換える場合だけ `--force` を使用 |
| Skillが表示されない | 実際の配置先と `SKILL.md` を確認し、Codexを再起動 |
| サンドボックス起動失敗 | ホストのCodex実行環境を確認し、doctorを再実行。実行制限を外して回避しない |
| 調査・検証で停止 | [使い方](usage.md#停止と再開)で状態・根拠・再開可否を確認 |

2.0.1は新規topicを1報告書にまとめます。更新だけでは既存資料を移行しません。[任意の移行](usage.md#既存資料を1報告書へ移行する)を参照してください。
