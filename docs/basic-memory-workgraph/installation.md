# Basic Memory Workgraph：インストール・更新・解除

[概要](README.md) · [導入](installation.md) · [使い方](usage.md) · [共有](sharing.md) · [仕組み](reference.md) · [困ったとき](troubleshooting.md) · [docs一覧](../README.md)

ターミナルのコマンドは、特に指定がなければこのリポジトリのルートで実行します。
「Codexへの依頼例」はCodexの会話欄に入力します。

## 実行前に確認すること

このインストーラーはリポジトリ内のPythonコード・方針・テンプレートを使うため、リポジトリ一式が必要です。
引数なしの初回導入は実際に書き込みます。初回導入用のdry-runはなく、`--dry-run`は`--update`と併用します。
Codexのplugin導入機能を使える環境と、外部配布元への接続も必要です。

| 取得・準備する対象 | 処理 |
|---|---|
| uv / uvx | 不足時にAstralのinstallerを取得・実行。既存uvに対応するuvxを公開する場合もある |
| Python 3.12 | `uv python install 3.12`で用意する |
| Basic Memory | uv toolで導入。既存版にはupgradeを試み、hook未対応ならprereleaseを許可した再導入を行う場合がある |
| Basic Memory公式plugin | `bm install codex`、未対応ならCodexのmarketplace操作で導入する |
| Workgraph | このリポジトリのコード・方針・スキーマを配置する |

初回導入はBasic Memory本体やpluginの版を固定していません。通信先にはAstral、Python・Pythonパッケージの配布元、
pluginの配布元が含まれます。`--update`はローカルのWorkgraph更新で、外部パッケージの更新とは別です。
配置するファイルと設定は[リファレンス](reference.md)に記載しています。
共通`AGENTS.md`には、メモリ共有・取り込みの依頼で共有手順を読む管理ブロックを追加します。
GitHub共有CLIも配置しますが、共有先の設定や送信はインストール時には行いません。
GitHub経由で使うときだけgit・gh・ログインが必要です。これらの導入・接続は別途案内します。
初回導入全体の一括ロールバックはなく、途中で停止すると先に導入した外部ツール等は残ります。

<a id="start"></a>

## 初回インストール

Codex CLI、Python 3、`curl` を使えるLinux / WSL2環境が必要です。
Gitで取得する場合は次のように実行します。すでにリポジトリがあれば、そのディレクトリへ移動します。

```bash
git clone https://github.com/Mak-GIBA/basic-memory-workgraph.git
cd basic-memory-workgraph
bash install_basic_memory_workgraph.sh
```

installerは `uv` / `uvx`、Basic Memory、公式Codex plugin、保存プロジェクト、
スキーマ、設定と追加hooksを用意します。ECCの設定は変更しません。

### 導入直後の状態

| 項目 | 既定値 |
|---|---|
| Basic Memoryプロジェクト | `codex-memory` |
| Markdownの保存先 | `~/knowledge/codex-memory/` |
| Codex設定先 | `~/.codex/`。`CODEX_HOME` 指定時はその場所 |
| 再利用知識の自動評価 | `smart`：候補があるとき評価 |
| 文脈付き修正指示の自動保存 | `off`：明示保存依頼時のみ |
| 具体事例の自動保存 | `off`：明示的に依頼した事例のみ |
| Skill化 | `review`：価値を判断するところまで。自動登録しない |
| 共有・学習利用 | どちらも未許可 |

保存先を変えて新規導入する場合は、プロジェクト名とディレクトリをセットで指定します。

```bash
MEMORY_PROJECT=work-memory \
MEMORY_DIR="$HOME/knowledge/work-memory" \
bash install_basic_memory_workgraph.sh
```

すでに導入済みなら、[アップデート](#update)を使ってください。
引数なしの通常installerは、保存先を省略すると上記の既定値を使います。

### Codex側で確認する

新しいCodexセッションを開始し、`/plugins` で `codex@basic-memory` を確認します。
`/hooks` では `basic_memory_workgraph.py recall`（UserPromptSubmit）と
`basic_memory_workgraph.py save`（Stop）の2コマンドを確認し、必要なtrust設定を行います。
反映されない場合はCodexを再起動します。Stopの判定だけで「保存評価中」とは表示しません。

導入後は、[日常の使い方](usage.md#daily)に進めます。

<a id="python-tools"></a>

### 更新・共有・Skill登録に使うPython環境を準備する

`--update`、共有・JSONL出力・Skill登録CLIにはPyYAMLが必要です。
フックと `--configure-only` はPython標準ライブラリだけで動作します。

依存を分離して導入するには、リポジトリで次を実行します。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r tools/basic-memory-workgraph/requirements-export.txt
source .venv/bin/activate
python3 -c 'import yaml; print(yaml.__version__)'
```

以降のコマンド例は、この環境を有効にした状態で使えます。新しいターミナルでは
リポジトリに移動して `source .venv/bin/activate` を再実行してください。
`venv` 自体が利用できない場合は、OSのPython環境にvenv機能を用意してください。
Skill自動登録を使う場合も、登録CLIを実行するPythonからPyYAMLを参照できる必要があります。

<a id="update"></a>

## アップデート

**改定版のコードを取得してから、既存環境へ適用する**という2段階です。
更新コマンド自体はGit操作やコードのダウンロードを行いません。

### 手順1：リポジトリを新しい版にする

Gitで取得している場合は、まずローカルの変更を確認します。

```bash
git status --short
```

変更がないことを確認し、公開済みの改定版を取得する場合:

```bash
git pull --ff-only
```

自分やCodexの未コミット変更がある場合は、先に内容を確認して保存・整理してください。
手元で修正した版を適用したいだけなら、Gitで取得する手順は不要です。
Gitを使わない場合は、改定版のリポジトリ一式を配置してください。

### 手順2：更新内容を確認して適用する

初回のみ[Python環境の準備](#python-tools)を済ませます。その後、リポジトリで実行します。

```bash
source .venv/bin/activate

# 更新予定を確認する。この段階では書き込まない。
bash install_basic_memory_workgraph.sh --update --dry-run

# 更新を適用する。
bash install_basic_memory_workgraph.sh --update
```

`primaryProject` とBasic Memoryの登録情報から、既存の保存先を自動検出します。
設定・hooks・CLI・参照資料・スキーマ・Graph索引を更新し、現在の各モード、他のhooks、
通常のMemoryノートを保持します。Basic Memory本体やpluginのパッケージ更新は行いません。

適用後は、新しいCodexセッションを開始してください。

### 更新結果の読み方

コマンドはJSONで結果を表示します。

| 項目 | 意味 |
|---|---|
| `dry_run` | `true` なら確認のみ |
| `project` / `memory_dir` | 検出した更新先 |
| `configuration` | 適用する保存先とモード |
| `changed` | 更新したファイル。dry-runでは更新予定のファイル |
| `preserved` | 上書きせず保持したスキーマ・索引と、その理由 |

`changed: []` は更新する差分がない状態です。
終了コードは、直後に `echo $?` で確認できます。

| 終了コード | 状態 | 対処 |
|---|---|---|
| `0` | 更新成功、または変更なし | 新しいCodexセッションで利用する |
| `1` | 入力・依存・処理のエラー | エラーメッセージを確認する |
| `2` | カスタマイズ等により保持したファイルがある | `preserved` の内容を確認する |

**終了コード2は「更新が全部失敗した」という意味ではありません。** 実更新では安全に更新できる
設定等は反映され、個別編集があるスキーマ・索引は保持されます。dry-runでは何も変更しません。

`preserved` の `path` が現在のファイル、`template` が改定版の参考ファイルです。
自分の編集を残すならそのまま保持できます。新しい定義が必要なら、差分を確認して必要部分を
取り込んでください。自動で強制上書きするオプションはありません。

変更前のファイルは `.bak.*` にバックアップします。書き込み中のエラーでは変更済みファイルを
復元し、バックアップを残します。同じ版を再実行しても、差分がなければバックアップを増やしません。

### 用途ごとのコマンド

| 用途 | コマンド | 保存済みスキーマへの変更 |
|---|---|---|
| 初回導入 | `bash install_basic_memory_workgraph.sh` | 作成・更新する |
| 既存環境の更新 | `bash install_basic_memory_workgraph.sh --update` | 既知の旧版を安全に更新する |
| モード変更・policyやhooksの反映 | `bash install_basic_memory_workgraph.sh --configure-only` | 変更しない |

保存先を個別指定したい場合や、スキーマだけを更新したい場合は[更新の詳細](#update-details)を参照してください。

<a id="update-details"></a>

### 更新の詳細

Basic Memory登録ファイルの探索順は次のとおりです。先に該当した設定先を使います。

1. `BASIC_MEMORY_CONFIG_DIR` 指定時：その配下の `config.json`
2. `XDG_CONFIG_HOME` 指定時：その配下の `basic-memory/config.json`
3. どちらも未指定：`~/.basic-memory/config.json`

明示的に別の登録ファイルを使う場合:

```bash
bash install_basic_memory_workgraph.sh --update \
  --basic-memory-config "/path/to/basic-memory/config.json" --dry-run
```

`MEMORY_PROJECT` / `--project` で別の登録済みローカルプロジェクトを選べます。
`MEMORY_DIR` / `--memory-dir` を指定する場合は、登録済みパスと一致する必要があります。
未登録・保存先不明・cloudプロジェクトを推測して更新しません。

スキーマだけを更新する場合は、登録済みのMarkdown保存先を指定します。

```bash
python3 tools/basic-memory-workgraph/install_schemas.py --memory-dir "$HOME/knowledge/codex-memory"
```

スキーマは、管理対象のYAML項目と本文を過去の配布版と比較して移行します。
Basic Memoryが追加した `permalink`、日時、管理対象外の追加メタデータは保持します。
定義の変更・追加、本文編集、移行で失われる可能性があるコメントは、カスタマイズとして保持・通知します。
最新の内容なら再整形もしません。通常installerも同じ処理を使います。

<a id="uninstall"></a>

## 解除する

リポジトリで実行します。

```bash
bash tools/basic-memory-workgraph/remove_workgraph_hooks.sh
```

追加hooksとその設定・状態・CLIコピー、共通AGENTSのメモリ共有用管理ブロックを解除します。
GitHub共有profileと取り込みの指紋も解除対象です。受信ノートとGitHubのデータは残ります。
取り込み状態を失った保存先へ再設定すると上書きを防ぐため停止するので、再導入前に必要な設定・状態を退避してください。
Basic Memory、公式plugin、保存済みノート、スキーマ、登録済みSkillと管理manifest、
`basic-memory.json` は残ります。共通policyとcheckpoint無効設定も残ります。
