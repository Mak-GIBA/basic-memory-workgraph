# インストール・更新・解除

[docs一覧](../README.md) · [概要](README.md) · [使い方](usage.md) · [検証結果](validation.md)

## 前提条件

- Linux／WSL2／macOS、Bash、Python 3.11以上、配置先への書き込み権限。
- 通常の組み立てには、GitHubの固定版スクリプトを取得できる通信環境。
- 研究ハーネスには、認証済みCodex CLIと動作するコマンド用サンドボックス、対象に必要な検証ツール。

配布版2.5.0の組み立てと独自資材はPython標準ライブラリで動きます。GitHubへのログインは不要です。
Codex本体、アプリのテスト依存、ブラウザー、MCP、別のLLM APIキーは導入しません。macOSの実機確認は未実施です。
必要なら`PYTHON_BIN`でPythonの実行ファイルを指定します。

2026-10-10に組み立ての停止原因を修正し、オフライン組み立て・両ツールの自己テストと、このPCでの更新・診断を確認しました。
[検証結果](validation.md)に、同梱試験、組み立て、実環境への更新の範囲を分けて記載しています。

## 初回導入

[トップREADME](../../README.md#はじめに)からスクリプトを取得し、その保存先で実行します。
引数なしのDesign Researchスクリプトは実際に導入します。

```bash
# まず組み立てと導入の予定を確認
bash install_design_research.sh --dry-run

# 新規導入
bash install_design_research.sh

# 配布物の入口一覧を確認
bash install_design_research.sh --list-skills
```

新規のユーザー共通配置は`~/.agents/skills/design-research/`です。
導入後はCodexの新しいセッションで`$design-research`を選べるか確認します。
`--list-skills`は配布物の入口を列挙し、現在の導入状態は調べません。`--version`も配布スクリプトの版を表示します。

プロジェクトだけで使う場合は次を指定します。パスは実際の対象へ置き換えてください。

```bash
bash install_design_research.sh --project /absolute/path/repo
```

新規配置は`PROJECT/.agents/skills/design-research/`です。
独自配置には`--skills-dir PATH`でSkillを置く親ディレクトリを指定します。
更新・状態確認・解除にも同じ配置先の指定を付けます。`--project`と`--skills-dir`は併用しません。

## 組み立てとオフライン利用

配布スクリプトは、コミット`d3f46e0d591b45cb2423317030a489b91566e891`の元インストーラー2本を取得し、SHA-256を照合します。
この固定版へ同梱の更新資材を適用して両ツールを組み立て、指定した側の導入処理を実行します。
通常は組み立ての際に通信します。`--status`や`--doctor`などの操作でも、配布スクリプトから呼ぶ場合は先に組み立てます。

`--dry-run`は組み立て予定を表示するだけで、ダウンロード・導入先の変更・既存の導入先の検査を行いません。
その成功だけで、実導入の可否や編集済みファイルの有無は判断できません。

再配布用の通常インストーラーを作る場合は次を使います。出力先は未使用または空のディレクトリを指定します。

```bash
bash install_design_research.sh --build-only ./offline-installers
```

成功した場合の出力には`install_design_research.sh`、`install_speckit_upstream.sh`とビルドログが含まれます。この操作では導入しません。
組み立てと導入の確認範囲は[検証結果](validation.md)を参照してください。
生成されたDesign Researchインストーラーの導入処理は通信せずに動きます。実際の研究で資料を取得する通信は別途必要です。

通信せず組み立てる場合は、固定コミットの元スクリプト2本を`/absolute/path/pinned-base/`へ用意します。
以前の更新用ラッパーや、編集した同名スクリプトは代用できません。

```bash
bash install_design_research.sh \
  --base-dir /absolute/path/pinned-base --offline --build-only ./offline-installers

# 生成に成功した後のスクリプトから導入
bash ./offline-installers/install_design_research.sh --update
```

`--offline`だけでは組み立てできず、`--base-dir`が必要です。
生成されたUpstreamインストーラーでSpecKit CLIの取得も省略する場合は`--skip-specify`を付けます。
配布版に`--skip-specify`を付けるだけでは、固定版ベースの取得通信は省略されません。

## 既存版からの更新

```bash
bash install_design_research.sh --dry-run --update
bash install_design_research.sh --update
```

引数なしの再実行は既存の管理対象Skillを保持します。更新には`--update`を指定します。
旧版の`~/.codex/skills`、`CODEX_HOME/skills`、プロジェクトの`.codex/skills`に既存配置が1つあれば再利用し、自動移動や重複導入はしません。
同名Skillが複数あれば、表示された候補から対象を確認し、`--skills-dir`で親を明示します。

管理対象の編集・欠落・追加を検出した場合は通常の更新・解除を止めます。
内容を確認して`--update --force`を使うと、旧ディレクトリ全体をコピーしてハッシュを照合し、新版へ切り替えます。
ローカルでの編集と追加ファイルはバックアップへ残り、新版へ自動では引き継がれません。所有情報のない同名ディレクトリは上書きしません。

2.3.0の5つのショートカットSkillは、未編集で管理元を確認できるものだけを更新時にバックアップへ退避します。
編集済み・管理外のフォルダーは保持します。現在の推奨入口は`$design-research`で、内部工程の機能はこの入口から使えます。
既存の研究資料・過去runは導入更新だけでは変更しません。[任意の資料移行](usage.md#既存資料を1報告書へ移行する)

## 状態確認と診断

```bash
bash install_design_research.sh --status --json
bash install_design_research.sh --doctor --json
```

この配布スクリプトでは、診断前の組み立てに通信が発生し得ます。
オフラインで診断する場合は、生成済みの通常インストーラーを使うか、`--base-dir PATH --offline`を添えます。

状態表示では`state: "installed"`、`version: "2.5.0"`、`modified: false`を確認します。

2.5.0は主要指標の契約に加え、責任別の保存単位・実測後の詳細説明・項目別レビューを新規runへ追加します。既存runの契約、過去の保存版、
ユーザー編集の保護と標準バックアップは維持します。管理対象が未編集なら通常の`--update`で更新できます。
MCP登録・モデル設定・個人のhooksは変更しません。
未導入は`absent`、所有情報を認識できない既存フォルダーは`unmanaged`です。追加ファイルも変更として検出し、Pythonキャッシュは除きます。
状態表示は未導入でも正常終了するため、終了コードだけで導入済みとは判断しません。

| doctorの項目 | 確認する内容 |
|---|---|
| `installed_integrity` | 導入済みSkillの所有情報・ファイルの整合性 |
| `installed_harness_ready` | 現在の版のハーネス資材が導入されているか |
| `harness_environment_ready` | Codex CLI、構造化execの引数、コマンド用サンドボックスの起動 |
| `ready` | ハーネスと実行環境が揃っているか |

準備不足は終了コード2で示します。ハーネスの診断はモデルを呼び出さず、学術APIにも接続しません。
認証・モデル応答・実API検索・Codex画面からの実行成功は別途確認します。サンドボックスに問題があればホスト環境を修復して再診断します。

## オプション

| 組み立て用のオプション | 動作 |
|---|---|
| `--help`／`-h`、`--version` | ヘルプ／配布版を表示 |
| `--dry-run` | 組み立て予定を表示。通信・導入先変更・導入先検査なし |
| `--list-skills` | 配布物のCodex入口を列挙。導入状態は検査しない |
| `--base-dir DIR` | 指定された固定版の元スクリプト2本を使用 |
| `--offline` | ベース取得の通信を禁止。組み立てには`--base-dir`が必要 |
| `--build-only DIR` | 両ツールの通常インストーラーとログを生成。導入なし |
| `--extract-bundle DIR` | 更新資材とテストを指定先へ展開。通信・導入なし |
| `--bundle-self-test` | 同梱パッケージのオフライン契約テストを実行 |

`--list-skills`・`--build-only`・`--extract-bundle`・`--bundle-self-test`は1つずつ使い、導入用の引数とは組み合わせません。
`--dry-run --build-only DIR`では生成予定だけを表示します。

| 組み立て後へ渡すオプション・環境変数 | 動作 |
|---|---|
| `--skills-dir PATH`／`--project PATH` | 独自配置／プロジェクト配置を選択 |
| `--update`／`--force` | 管理対象を更新／編集済みの管理対象をバックアップ後に更新・解除 |
| `--uninstall` | バックアップ後に管理対象を解除 |
| `--status`／`--doctor` | 導入状態／実行環境を確認 |
| `--self-test` | 組み立て後のインストーラーの内蔵テストを実行 |
| `--extract DIR` | 組み立て後のSkill資材を未使用・空のディレクトリへ展開 |
| `--print-mcp-config` | 任意のMCP設定例を表示。登録しない |
| `--json` | 結果をJSONで表示。MCP設定例はTOML |
| `PYTHON_BIN` | 使用するPython 3.11以上。既定は`python3` |
| `CODEX_HOME` | 既存配置を探す際に`CODEX_HOME/skills`も確認 |

組み立て後の操作モードは相互排他です。診断・テスト・展開と更新・解除を同時に指定しません。

<a id="資材とバックアップ"></a>
<a id="展開して確認する解除する"></a>

## 資材・バックアップ・解除

| 対象 | 保存先・扱い |
|---|---|
| Skill・Bash・Python・資料 | 選んだSkill親の`design-research/`。資材と各ファイルのSHA-256を照合 |
| 所有情報 | Skill内の`.design-research-install.json` |
| バックアップ | Skill親の1階層上の`.design-research-backups/<配置先の識別子>/<日時とID>/` |

新規のユーザー共通配置では、バックアップは`~/.agents/.design-research-backups/`配下です。
切り替えは配置先と同じ親の一時ディレクトリで行い、失敗時は旧配置を戻します。別のファイルシステムのバックアップ先へもコピーで退避します。
同時実行と、親を含むシンボリックリンクの配置先は拒否します。

```bash
bash install_design_research.sh --dry-run --uninstall
bash install_design_research.sh --uninstall
```

編集済み資材を解除する場合は、内容を確認して`--uninstall --force`を使います。
研究成果物・キャッシュ・バックアップは残ります。自動復元専用のオプションはありません。
インストーラーは個人の`config.toml`、hooks、MCP、Workgraphの保存設定を変更しません。

<a id="困ったとき"></a>

## 困ったとき・資材を読む

```bash
# 組み立て用の更新資材を、通信せず展開・検査
bash install_design_research.sh --extract-bundle /tmp/design-research-upgrade
bash install_design_research.sh --bundle-self-test
```

展開先は未使用または空のディレクトリにします。展開は指定先へ書き込みます。
`--extract-bundle`は更新元のコード・資料・テスト、`--extract`は組み立て後のSkill資材を確認するための操作です。
リポジトリ内の`tools/design-research/`だけで、この組み立て版全体を再生成することはできません。[保守と検証](../development.md#design-researchの埋め込み資料)

| 状況 | 対処 |
|---|---|
| 組み立ての自己テストで停止 | 導入は行われない。[現在の検証結果](validation.md)とエラーを確認 |
| Pythonの条件で停止 | Python 3.11以上と`PYTHON_BIN`を確認 |
| 固定版取得に失敗 | 接続先・通信環境を確認。オフラインでは正しい元スクリプト2本を用意 |
| チェックサム不一致 | 元スクリプトの版・欠損・変更を確認。更新用ラッパーをベースにしない |
| 同名Skillが複数／`unmanaged` | 所有情報を確認し、対象の親を`--skills-dir`で明示 |
| 編集で更新が止まる | 差分とバックアップ方針を確認してから`--force`を検討 |
| 旧ショートカットが残る | 保持された編集・所有情報を確認し、現在の入口は`$design-research`を使用 |
| Skillが表示されない | 実際の配置先と`SKILL.md`を確認し、Codexの新しいセッションで再確認 |
| 調査・検証で停止 | [停止と再開](usage.md#停止と再開)で状態・根拠・再開可否を確認 |
