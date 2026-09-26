# Basic Memory Work Knowledge Graph

Codexでの作業から、次の仕事にも役立つ知識をBasic Memoryへ蓄積するためのツールです。
成功した手順やユーザーの修正を振り返り、再利用できるルール・具体事例・Skillを関連付けます。

**導入直後は、再利用知識の自動評価が有効です。具体事例の自動保存とSkillの自動登録は、設定で有効にします。**
すべての会話を保存するものではありません。保存価値がなければ何も保存しません。

| やりたいこと | 読む場所 |
|---|---|
| 初めてこのPCに入れる | [初回インストール](#start) |
| すでに入っている版を更新する | [アップデート](#update) |
| 普段のCodexで使う | [日常の使い方](#daily) |
| 具体事例の保存・Skill自動登録を有効にする | [設定を変更する](#modes) |
| チームや別のPCへMemoryを渡す | [Memoryを共有する](#share) |
| ローカルLLM向けの事例データを出す | [学習用JSONLを出力する](#training) |
| 保存されない・更新で止まった | [困ったとき](#troubleshooting) |

以下の `bash` / `python3` コマンドは **Linux / WSL2のターミナル**で実行します。
特に記載がなければ、`install_basic_memory_workgraph.sh` があるリポジトリのルートが作業場所です。
「Codexへの依頼例」はCodexの会話欄へ入力してください。

<a id="start"></a>

## 1. 初回インストール

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
`/hooks` では次の2項目を確認し、必要なtrust設定を行います。反映されない場合はCodexを再起動します。

```text
Searching Basic Memory Work Knowledge Graph
Evaluating reusable Basic Memory knowledge
```

導入後は、[日常の使い方](#daily)に進めます。

<a id="python-tools"></a>

### 更新・共有・Skill登録に使うPython環境を準備する

`--update`、共有・JSONL出力・Skill登録CLIにはPyYAMLが必要です。
フックと `--configure-only` はPython標準ライブラリだけで動作します。

依存を分離して導入するには、リポジトリで次を実行します。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-export.txt
source .venv/bin/activate
python3 -c 'import yaml; print(yaml.__version__)'
```

以降のコマンド例は、この環境を有効にした状態で使えます。新しいターミナルでは
リポジトリに移動して `source .venv/bin/activate` を再実行してください。
`venv` 自体が利用できない場合は、OSのPython環境にvenv機能を用意してください。
Skill自動登録を使う場合も、登録CLIを実行するPythonからPyYAMLを参照できる必要があります。

<a id="update"></a>

## 2. アップデート

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

<a id="daily"></a>

## 3. 日常の使い方

通常は、Codexへいつもどおり作業を依頼します。作業前に関連Memoryを検索し、
成功した手順や修正から再利用できる知識が得られたら、保存するかを評価します。
保存はCodexが行います。hookは検索・評価を促す役割で、直接Memoryを書き込むものではありません。

### 過去の知識を使いたい

Codexへの依頼例:

```text
この作業に関係する過去のRule・Workflow・CaseをBasic Memoryで確認してから進めて。
今回にも当てはまる条件と、当てはまらない条件を区別して使ってください。
```

### 修正から得た教訓を残したい

```text
今回の修正から、別の案件でも使える教訓があればMemoryへ反映してください。
今回だけの条件を一般化せず、適用条件と検証結果も残してください。
```

例えば「異なる分母の数値を比較した → 分母の違いを指摘された → 分母を揃えて再計算した」
という流れなら、検証と追加価値がある場合に、条件付きのルールを残します。
単に「テストが通った」「作業が完了した」だけでは保存しません。

### 修正前後の具体事例も残したい

```text
このやり取りを、要求・初回出力・修正指示・改善後の結果が分かるCaseとして保存してください。
必要な部分を匿名化して残し、関連するRuleがあればリンクしてください。
共有や学習用出力はまだ許可しません。
```

これは、事例モードが `off` でも使える明示的な保存依頼です。
有用な事例の選別・保存を自動にしたい場合は、[事例保存の設定](#modes)を有効にします。

### 継続的な好みを覚えてほしい

```text
今後の案件でも、回答は日本語を基本にしてください。
英文作成を依頼した場合は英語で構いません。この好みを覚えてください。
```

「今回のボタンだけ青くして」のような単発の修正を、恒久的な好みと推測することはありません。
Plan/read-onlyモードでは、これらの依頼があっても書き込みを行いません。

### Memory・Case・Skillの違い

| 種類 | 残す内容 | 使い道 |
|---|---|---|
| 抽象Memory | 条件付きルール、再利用手順、確認方法 | 別タスクで判断・実行するときに使う |
| Case | 要求、初回出力、修正、改善、結果の具体的な対比 | 類似案件の比較、学習データ候補に使う |
| Skill | レビュー・検証済みの実行手順や補助資源 | 繰り返す仕事を実行しやすくする |

抽象MemoryとCaseは別々に保存価値を判断し、両方が存在する場合に関連付けます。
Skill化の背景や根拠はWorkflowに残し、登録したSkillへArtifactから辿れるようにします。

<a id="modes"></a>

## 4. 設定を変更する

モード変更は、リポジトリで `--configure-only` を実行します。
**指定した設定だけを変更し、省略した設定は維持します。** 変更後は新しいCodexセッションを開始してください。

### 有用な具体事例の自動保存を有効にする

```bash
BM_CASE_MODE=reusable bash install_basic_memory_workgraph.sh --configure-only
```

成功・修正インタラクションのうち、比較や学習に価値があるものを選別します。
会話全文を毎回保存する設定ではありません。

### Skillの作成・登録まで自動で行う

[Python環境](#python-tools)を用意し、次を実行します。

```bash
BM_SKILL_MODE=auto bash install_basic_memory_workgraph.sh --configure-only
```

利用可能な `skill-creator` 等で、既存Skillとの重複や、MemoryだけよりSkill化する価値があるかを
レビューします。検証まで通ったものだけ登録します。Creator不在・検証不能なら候補に留めます。
既存pluginや個人Skillは上書きしません。Workgraphが管理するSkillでも、ユーザー編集があれば自動更新を止めます。

両方まとめて有効にすることもできます。

```bash
BM_CASE_MODE=reusable BM_SKILL_MODE=auto \
bash install_basic_memory_workgraph.sh --configure-only
```

### 止める・元に戻す

```bash
# 事例の自動保存を止め、Skillはレビューまでにする。
BM_CASE_MODE=off BM_SKILL_MODE=review \
bash install_basic_memory_workgraph.sh --configure-only

# 事例保存・Skillレビューを含む自動処理をすべて止める。
BM_AUTO_MODE=off bash install_basic_memory_workgraph.sh --configure-only

# 自動評価を再開する。事例・Skillの設定は保存されていた値を使う。
BM_AUTO_MODE=smart bash install_basic_memory_workgraph.sh --configure-only
```

**`BM_AUTO_MODE=off` の間は、他のモードが有効でも自動処理は動きません。**
明示的な保存依頼は指定された範囲で扱えます。Skill登録CLIは `auto` 設定を要求します。

### 全設定と現在値の確認

| 設定 | 値 | 動作 |
|---|---|---|
| `BM_AUTO_MODE` | `smart`（既定） | 要求・回答に成功／修正／教訓等の候補があるとき評価 |
| | `always` | 毎ターン評価。保存基準は同じ |
| | `off` | 自動保存・事例保存・Skillレビューと登録を停止 |
| `BM_CASE_MODE` | `off`（既定） | 具体事例は明示保存依頼時のみ |
| | `reusable` | 有用な具体事例を選別して保存 |
| `BM_SKILL_MODE` | `off` | 自動Skillレビューを停止 |
| | `review`（既定） | Skill化の判断と理由まで |
| | `auto` | レビュー・検証後の登録まで |

現在の設定は次で確認できます。

```bash
cat "${CODEX_HOME:-$HOME/.codex}/basic-memory-workgraph/config.json"
```

新規導入時の内容は次のとおりです。更新時は既存の設定値を保持します。

```json
{
  "mode": "smart",
  "caseMode": "off",
  "skillMode": "review"
}
```

<a id="share"></a>

## 5. Memoryを共有する

共有は、**対象の確認 → 共有範囲の指定 → export → 相手側でimport**の順に行います。
ツールはローカルにファイルを出力します。送信・公開は行わないため、完成したフォルダを
Gitやファイル転送などで渡してください。

[Python環境](#python-tools)を有効にして実行します。以下の `rules/example.md` は例です。
**実在するノートの、Memory保存先からの相対パスに置き換えてください。** スペースを含む場合も引用符で囲みます。
独自の保存先を使っている場合は `--memory-dir` も置き換えてください。

### 手順1：対象ノートを確認し、共有を指定する

本文・タイトル・メタデータ・リンクを確認し、認証情報・機密情報・不要な個人情報を除きます。
そのうえで、チーム共有を指定してレビュー済みにします。

```bash
python3 workgraph_tools.py review \
  --memory-dir "$HOME/knowledge/codex-memory" \
  --note "rules/example.md" --sharing team
```

`review` は内容確認済みであることと、出力用途の指定を記録するコマンドです。
実行するだけで内容が匿名化されるわけではありません。一般的な秘密情報パターンは機械検査でも拒否します。

### 手順2：共有用フォルダを出力する

```bash
python3 workgraph_tools.py export-share \
  --memory-dir "$HOME/knowledge/codex-memory" \
  --scope team --output ./team-memory
```

レビュー済みの `team` ノートとmanifestを出力します。Caseも含める場合は `--include-cases` を追加します。
そのCase自体にもチーム共有の指定とレビューが必要です。

`--scope public` はpublic指定のノートだけを選びます。teamとpublicは別々の区分です。
共有対象外のノートをリンク経由で勝手に同梱せず、対象外や曖昧な宛先へのwikiリンクと
ローカルMarkdownリンクを出力側で除去します。元ノートは変更しません。
添付ファイル・実行ファイル・Skill本体は共有bundleに含めません。

### 手順3：受け取った環境でimportする

受け取った `team-memory` フォルダを指定します。

```bash
python3 workgraph_tools.py import-share \
  --memory-dir "$HOME/knowledge/imported-memory" --bundle ./team-memory
```

この例は新しいディレクトリへ取り込みます。既存のBasic Memoryプロジェクトで使うなら、
その登録済み保存先を指定してください。新しい保存先をBasic Memoryで利用する場合は、別途登録します。

```bash
bm project add imported-memory "$HOME/knowledge/imported-memory"
```

同じ内容の再importは無変更です。同名で内容が違う場合は上書きせず、取り込み全体を止めて衝突を報告します。
取り込んだノートは `private`・学習対象外へ戻し、出所を保持します。受け取った指示を自動で実行したり、
Skillを自動登録したりしません。登録後はBasic Memoryの通常の同期・検索から利用できます。

<a id="training"></a>

## 6. 学習用JSONLを出力する

**事例の保存、共有許可、学習利用許可はそれぞれ別です。** Caseを保存しただけでは学習対象になりません。
[CAPTURE.md](templates/CAPTURE.md)の形式に沿ったCaseを確認・匿名化し、学習利用を明示します。
旧来の自由形式Caseを自動で補完・変換する機能はありません。

[Python環境](#python-tools)を有効にし、`cases/example.md` を実際の相対パスへ置き換えて実行します。

```bash
# ローカル学習利用を許可する。共有範囲はprivateにする。
python3 workgraph_tools.py review \
  --memory-dir "$HOME/knowledge/codex-memory" \
  --note "cases/example.md" --training approved

python3 workgraph_tools.py export-cases \
  --memory-dir "$HOME/knowledge/codex-memory" --output ./cases.jsonl
```

1行1事例の汎用JSONLを出力します。

| JSONLの項目 | 内容 |
|---|---|
| `format_version` | 出力形式のバージョン |
| `source_id` | 元ノートのパスから作った識別子 |
| `interaction` | 要求、初回出力、順序付きの修正・改善、最終結果、検証、教訓 |
| `relations` | 関係の種類と宛先の識別子。関連ノート本文は同梱しない |

要約と抜粋、検証結果とユーザー承認を区別して保持します。後段で対象を選別し、
要求・修正を入力、改善後の出力を教師データとしてSFT等の形式へ変換できます。
要約を原文扱いしたり、不明な結果を成功扱いしたりしないでください。
このツールの担当は汎用JSONLまでで、SFT形式への変換、LoRA学習、モデルへの投入は含みません。

### 共有と学習の両方を許可したい場合

`review` は、省略すると共有範囲をprivate、学習利用をexcludedにします。
両方許可する場合は、一度のコマンドで両方を指定してください。

```bash
python3 workgraph_tools.py review \
  --memory-dir "$HOME/knowledge/codex-memory" \
  --note "cases/example.md" --sharing team --training approved
```

ノートの本文やメタデータを編集した後は、内容の指紋が変わるため再レビューが必要です。
自動保存で共有・学習の許可を付けることはありません。

<a id="troubleshooting"></a>

## 7. 困ったとき

| 状況 | 確認・対処 |
|---|---|
| 新機能が動かない | 新しいCodexセッションを開始し、`/plugins` と `/hooks` を確認する |
| 教訓が保存されない | `mode`、検証根拠、再利用価値、既存Memoryとの重複を確認する。価値がなければ保存しないのが正常 |
| 具体事例が増えない | 既定は `caseMode=off`。明示的に保存を依頼するか、`reusable` にする |
| Skillが作成されない | 既定は `skillMode=review`。`auto` でもCreator・検証・追加価値が必要 |
| `PyYAML` が必要と表示された | [Python環境の準備](#python-tools)を実行し、同じ環境でコマンドを使う |
| 更新で終了コード2になった | `preserved` を確認。対象を上書きせず保持した通知であり、全更新の失敗ではない |
| 保存先が見つからない／不一致 | `primaryProject` とBasic Memory登録情報を確認。[更新の詳細](#update-details)を参照 |
| exportの件数が0になった | 共有／学習用途の指定とレビュー状態を確認。編集後は再レビューが必要 |
| `Missing or stale privacy review` | 内容を確認して `review` を再実行する。共有・学習両方を許可するなら両引数を指定する |
| `Output already exists` | 既存の出力は上書きしないため、新しい `--output` を指定する |
| importで `conflicts` が返った | 同名ノートの差分を確認するか、別の保存先へ取り込む。既存ノートは上書きされない |
| 秘密情報の検査で拒否された | 内容を匿名化して再レビューする。検査を通っても人名・業務機密の確認は必要 |

共有・学習CLIでは `--dry-run` を付けると書き込みせず確認できます。
ただし、出力先がすでに存在する場合など、通常実行と同じ入力制約は適用されます。
CLIの終了コードは0が成功、1が入力・処理エラー、2が除外項目またはimport衝突ありです。
exportは安全に出力できた項目を出し、`skipped` に除外理由を表示します。

<a id="details"></a>

## 8. 保存方針・配置・仕組み

### 保存品質

正本は[memory-policy.md](memory-policy.md)です。抽象Memoryの自動保存は、以下をすべて満たす知識に限ります。

| 基準 | 内容 |
|---|---|
| 再利用性 | 元の案件以外で使える具体的な場面がある |
| 有用性 | 次回の判断・手順を改善し、失敗や再調査を減らす |
| 根拠 | 実際の確認で裏付けられている。十分な検証なら1回でもよい |
| 持続性 | 適用条件・例外・再確認条件が明確 |
| 追加価値 | 既存メモや容易に確認できる一般知識にない価値がある |

明示された継続的な好みも、範囲と例外を添えて保存できます。
作業日誌、完了報告、成果物一覧、一般論、推測は自動保存しません。
新しい根拠・条件がなければ、既存ノートへ利用日時だけを追記することもありません。
重複検索に失敗した場合は、自動保存を見送ります。

`smart` の候補検出は日本語・英語表現に基づくため、すべての教訓を捕捉する保証はありません。
hookのキーワード一致は評価を起動するだけで、保存の許可ではありません。
hook状態には候補フラグだけを保持し、会話本文を記録しません。Stop hookは一度だけ評価を依頼します。
MCPサーバー側で全クライアントの書き込みを強制的に制限する仕組みではありません。

### ノートの配置

| Folder | 用途 |
|---|---|
| `rules/` | 条件付きのルール、明示された継続的な好み |
| `workflows/` | 再利用手順、Skill化判断と背景 |
| `validations/` | 再利用できる確認方法 |
| `cases/` | 具体的インタラクション、既存の自由形式事例 |
| `corrections/` | 明示依頼による修正記録 |
| `artifacts/` | 成果物や登録済みSkillへの参照 |
| `projects/` | 明示依頼による長期スコープ |
| `schemas/` | ノート構造の定義 |

従来の7種類を維持し、新項目は任意項目として追加しています。既存ノートを一括変換しません。
具体事例は `type: case` のMarkdown内に、版付きのJSONブロックとして保持します。
通常のObservations／Relationsも使えるため、`generalized_to` / `learned_from` 等で抽象Memoryと結べます。
詳細と記入例は[CAPTURE.md](templates/CAPTURE.md)を参照してください。

Skillのレビュー基準と登録手順は[SKILL_REVIEW.md](templates/SKILL_REVIEW.md)にあります。
登録済みSkillのArtifactは `kind: skill` と `skill:<name>` を持ち、Workflowから `packaged_as` で結びます。
実行手順はSkill、背景・根拠・適用条件はWork Graphに残します。関連付けのためだけにノート一式を作りません。

### 共有・学習用メタデータ

| frontmatter | 既定 | 意味 |
|---|---|---|
| `sharing_scope` | `private` | `team` / `public` の明示で共有対象を指定 |
| `training_use` | `excluded` | `approved` の明示で学習利用を指定 |
| `privacy_review` | `pending` | 内容レビューの状態 |
| `review_sha256` | なし | 本文・メタデータに結び付いたレビューの指紋 |

項目がない旧ノートはprivate・学習対象外として扱います。
これはCLIの出力対象を選ぶための指定であり、ファイル自体のアクセス制御や暗号化ではありません。

### インストール先のファイル

以下は `${CODEX_HOME:-$HOME/.codex}` 配下です。

| 配置 | 内容 |
|---|---|
| `basic-memory.json` | 保存先と共通policy。`checkpointOnCompact=false` |
| `basic-memory-workgraph/config.json` | 評価・事例・Skillのモード |
| `basic-memory-workgraph/memory-policy.md` | 開始・終了hookの共通基準 |
| `basic-memory-workgraph/templates/` | 事例形式、Skillレビュー、スキーマの参照資料 |
| `basic-memory-workgraph/workgraph_tools.py` | 共有・JSONL出力・Skill登録CLI |
| `hooks/basic_memory_workgraph.py` | 方針注入、検索案内、保存評価依頼 |
| `hooks.json` | hook登録 |

導入済みCLIは、リポジトリ以外の場所からも実行できます。

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/basic-memory-workgraph/workgraph_tools.py" --help
```

この場合も、そのPython環境にPyYAMLが必要です。
公式pluginの設定探索はその仕様に従います。プロジェクトの `.codex/basic-memory.json` に
設定がある場合、ユーザー設定より優先されることがあります。
既存の `captureEvents` は保持します（未設定ならtrue）。公式pluginのイベント記録とは別に、
本フックでは本文を記録しません。圧縮時の自動checkpointは無効です。

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
python3 install_schemas.py --memory-dir "$HOME/knowledge/codex-memory"
```

スキーマは、管理対象のYAML項目と本文を過去の配布版と比較して移行します。
Basic Memoryが追加した `permalink`、日時、管理対象外の追加メタデータは保持します。
定義の変更・追加、本文編集、移行で失われる可能性があるコメントは、カスタマイズとして保持・通知します。
最新の内容なら再整形もしません。通常installerも同じ処理を使います。

<a id="uninstall"></a>

## 9. 解除する

リポジトリで実行します。

```bash
bash remove_workgraph_hooks.sh
```

追加hooksとその設定・状態・CLIコピーを解除します。
Basic Memory、公式plugin、保存済みノート、スキーマ、登録済みSkillと管理manifest、
`basic-memory.json` は残ります。共通policyとcheckpoint無効設定も残ります。

<a id="development"></a>

## 開発・検証

[Python環境](#python-tools)を用意し、リポジトリで実行します。

```bash
python3 -m unittest discover -s tests -v
bash -n install_basic_memory_workgraph.sh remove_workgraph_hooks.sh
```

テストは一時ディレクトリと架空の事例を使用します。実際の個人MemoryやSkillへは書き込みません。
設定維持、スキーマ移行、保存モード、共有境界、JSONLの情報保持、importの衝突、Skill登録の保護、
更新のdry-run・再実行・失敗時の復元などを確認します。外部パッケージ導入はモックで検証します。
意味内容の判断例は[tests/POLICY_SCENARIOS.md](tests/POLICY_SCENARIOS.md)にあります。
機械テストは、実際の会話に対する抽象化品質やCreatorレビューの正しさを証明するものではありません。

リリース時は、変更前の配布済みテンプレートを `schema-history/<version>/` に残してから
現行テンプレートを変更します。更新処理はこの履歴を使い、実行時にGitやネットワークから取得しません。
policy変更はリポジトリの `memory-policy.md` を編集し、`--configure-only` または `--update` で反映します。
