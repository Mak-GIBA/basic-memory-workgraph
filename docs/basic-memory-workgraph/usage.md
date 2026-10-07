# Basic Memory Workgraph：日常の使い方と設定

[概要](README.md) · [導入](installation.md) · [使い方](usage.md) · [共有](sharing.md) · [仕組み](reference.md) · [困ったとき](troubleshooting.md) · [docs一覧](../README.md)

ターミナルのコマンドは、特に指定がなければこのリポジトリのルートで実行します。
「Codexへの依頼例」はCodexの会話欄に入力します。

<a id="daily"></a>

## 日常の使い方

通常は、Codexへいつもどおり作業を依頼します。作業前に関連Memoryを検索し、
成功した手順や修正から再利用できる知識が得られたら、保存するかを評価します。
保存はCodexが行います。hookは検索・評価を促す役割で、直接Memoryを書き込むものではありません。

### 過去の知識を使いたい

Codexへの依頼例:

```text
この作業に関係する過去のCorrection・Rule・Workflow・CaseをBasic Memoryで確認してから進めて。
今回にも当てはまる条件と、当てはまらない条件を区別して使ってください。
```

### 修正指示を次の初回出力へ反映したい

[文脈付き修正指示の保存](#correction-mode)を有効にすると、例えば次の指示を
`corrections/` に残す候補として扱います。

```text
意思決定者向けなので、比較表と推奨案を先にして、細かい説明は後ろにしてください。
```

残すのは指示だけでなく、**目的・読者・成果物・制約と、望ましい出力・適用範囲**です。
初回出力の問題や修正理由は、会話から分かる範囲だけ記録します。
結果がまだ不明でも保存でき、「指示は確認済み／効果は未検証／承認は不明」と分けます。

次の依頼では、出力を作る前に関連するCorrectionを検索し、条件の合う履歴を初回出力へ反映します。
上記なら、似た意思決定用の説明で比較と推奨を先に置く参考になります。
技術解説にも一律適用したり、「常に短文を好む」という恒久的な好みに変えたりはしません。
今回の明示指示は過去の履歴より優先します。引用された過去の指示も新しい実行許可ではありません。

同じ範囲で指示が変われば既存ノートを更新し、異なるコンテキストでの指示は区別します。
全文ログ、新規依頼、相づち、追加情報のない重複は自動保存しません。
Correctionはそのまま学習用Caseにはならず、共有・学習利用の許可も自動では付けません。
記入例と参照手順は[CORRECTIONS.md](../../tools/basic-memory-workgraph/templates/CORRECTIONS.md)を参照してください。

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

### 改善シーケンスから初回出力を良くしたい

[progressiveモード](#progressive-mode)では、同じ成果物について
「初回出力 → 修正指示 → 改善 → 次の修正 → その後の利用」を一つのCaseに積み重ねます。
修正がない場合も、具体的な後続利用・再利用依頼、または非自明な検証済み成果から開始できます。
将来使える具体的な特徴・適用範囲・追加価値が必要で、単なる作業完了や一般的なテスト成功は対象外です。
結果が出る前から保存でき、後でどの版に対する指示・行動だったかを辿れます。
目的・読者・制約が似たCaseを次の出力前に検索し、採用された可能性のある特徴と失敗点を参照します。

評価のプロンプトや「いいね」は不要です。修正後のcommit／push指示、出力を土台にした次の仕事、
同じ形式の再利用、残りの修正範囲の限定などを、対象と文脈付きの観測事実として残します。
観測事実と採用・受容の推定、技術的な検証結果は別々です。
明示承認が不明でも、根拠と文脈に合う保存・再利用は可能です。検証だけの成功例では採用評価を空にします。
例えば「この手順で次のインポーターも作って」は再利用依頼の根拠であり、実際の利用完了や満足の証明ではありません。

- commit／pushだけなら推定は暫定。途中退避やエージェントの自主的なcommitは採用の根拠にしません。
- commitとpushを別々の高評価として加算しません。沈黙・時間経過・話題変更でも満足を推定しません。
- 後から同じ問題を指摘されたり、元に戻すよう依頼されたら推定を見直します。以前の実際の指示は消しません。
- 対象や順序が分からない箇所は不明のままにし、会話全文の収集やログからの復元はしません。

一つのセッションに別の成果物があればCaseを分けます。別セッションでも同じ成果物の継続と確認できれば
同じCaseを更新します。単なる新規依頼や、学習・比較価値のない全作業記録は自動保存しません。
検索・抽象化・採用推定はCodexが行い、CLIは構造と参照の整合性を検査します。
詳しい形式は[CAPTURE.md](../../tools/basic-memory-workgraph/templates/CAPTURE.md)を参照してください。

### 継続的な好みを覚えてほしい

```text
今後の案件でも、回答は日本語を基本にしてください。
英文作成を依頼した場合は英語で構いません。この好みを覚えてください。
```

「今回のボタンだけ青くして」のような単発の修正を、恒久的な好みと推測することはありません。
Plan/read-onlyモードでは、これらの依頼があっても書き込みを行いません。

### 抽象Memory・Correction・Case・Skillの違い

| 種類 | 残す内容 | 使い道 |
|---|---|---|
| Correction | 状況、修正指示、望ましい出力、適用範囲。効果は未検証でもよい | 出力前に参照し、同じ修正を繰り返すのを防ぐ |
| 抽象Memory | 条件付きルール、再利用手順、確認方法 | 別タスクで判断・実行するときに使う |
| Case | 要求、初回出力、修正、改善、結果の具体的な対比 | 類似案件の比較、学習データ候補に使う |
| Skill | レビュー・検証済みの実行手順や補助資源 | 繰り返す仕事を実行しやすくする |

抽象MemoryとCaseは別々に保存価値を判断し、両方が存在する場合に関連付けます。
Skill化の背景や根拠はWorkflowに残し、登録したSkillへArtifactから辿れるようにします。

### メモリをGitHub経由で共有したい

```text
確認済みのチーム共有メモリをGitHubへ共有して。PRまで作成してください。
```

```text
共有メモリを取り込んで。ローカルで編集したノートは保持してください。
```

更新後の新しいセッションでは、共通AGENTSの指示から共有手順を読みます。
共有先が未設定、またはログインが必要なら、その場で接続支援を提案します。
共有の指定と内容レビューは別途必要です。初回設定は[GitHub経由の共有](github-sharing.md)を参照してください。

<a id="modes"></a>

## 設定を変更する

モード変更は、リポジトリで `--configure-only` を実行します。
**指定した設定だけを変更し、省略した設定は維持します。** 変更後は新しいCodexセッションを開始してください。

<a id="correction-mode"></a>

### 文脈付き修正指示の自動保存を有効にする

初めてこの機能を導入する既存環境では、[Python環境](installation.md#python-tools)で次を実行します。
Correctionスキーマも更新し、既存の他の設定は維持します。

```bash
BM_CORRECTION_MODE=scoped bash install_basic_memory_workgraph.sh --update
```

以降の設定変更だけなら次でも切り替えられます。

```bash
BM_CORRECTION_MODE=scoped bash install_basic_memory_workgraph.sh --configure-only
# 修正指示の自動保存だけを停止
BM_CORRECTION_MODE=off bash install_basic_memory_workgraph.sh --configure-only
```

`scoped` は結果不明の修正も、分かっている文脈と限定された適用範囲で保存します。
`case=off` でも使えます。既存環境の更新では勝手に有効化せず、既定値は `off` です。

### 有用な具体事例の自動保存を有効にする

```bash
BM_CASE_MODE=reusable bash install_basic_memory_workgraph.sh --configure-only
```

成功・修正インタラクションのうち、比較や学習に価値があるものを選別します。
会話全文を毎回保存する設定ではありません。

<a id="progressive-mode"></a>

### 改善シーケンスを途中から段階的に保存する

[Python環境](installation.md#python-tools)で次を実行すると、Case v2・点検CLIを更新して有効化できます。

```bash
BM_CASE_MODE=progressive bash install_basic_memory_workgraph.sh --update
```

`reusable` は結果のある有用な事例、`progressive` はそれに加え、有用な未完了の改善過程や再利用依頼から保存します。
どちらも明示承認は必須ではありません。`off` は従来どおり明示保存依頼時のみです。
既存利用者の `caseMode` は更新時に保持し、未設定なら従来どおり `off` です。
導入済みでモードだけ切り替える場合は `--configure-only` も使えます。

### Skillの作成・登録まで自動で行う

[Python環境](installation.md#python-tools)を用意し、次を実行します。

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

# 修正指示・事例保存・Skillレビューを含む自動処理をすべて止める。
BM_AUTO_MODE=off bash install_basic_memory_workgraph.sh --configure-only

# 自動評価を再開する。事例・Skillの設定は保存されていた値を使う。
BM_AUTO_MODE=smart bash install_basic_memory_workgraph.sh --configure-only
```

**`BM_AUTO_MODE=off` の間は、他のモードが有効でも自動処理は動きません。**
明示的な保存依頼は指定された範囲で扱えます。Skill登録CLIは `auto` 設定を要求します。

### 全設定と現在値の確認

| 設定 | 値 | 動作 |
|---|---|---|
| `BM_AUTO_MODE` | `smart`（既定） | 実装モード確認後、成功／修正／教訓等の候補があるとき評価 |
| | `always` | 実装モード確認済みの各ターンで評価。保存基準は同じ |
| | `off` | 修正指示を含む自動保存・Skillレビューと登録を停止 |
| `BM_CORRECTION_MODE` | `off`（既定） | Correctionは明示保存依頼時のみ |
| | `scoped` | 結果不明の修正指示も、文脈と適用範囲付きで保存 |
| `BM_CASE_MODE` | `off`（既定） | 具体事例は明示保存依頼時のみ |
| | `reusable` | 結果のある有用な具体事例を選別して保存 |
| | `progressive` | 有用な修正・後続利用・再利用依頼・非自明な検証済み成果から保存し、採用・撤回の手掛かりも追加 |
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
  "correctionMode": "off",
  "caseMode": "off",
  "skillMode": "review"
}
```
