# Basic Memory Work Knowledge Graph — 簡単導入

このセットは、Basic Memoryを次の用途に軽微拡張します。

> 過去の仕事・ユーザー修正・ルール・作業手順・検査を
> Knowledge Graphとして蓄積し、次回の仕事で関連事例を辿る。

---

## まず理解する図

```text
あなたの依頼
   ↓
[Codex Hook]
   ↓
Basic Memoryから似たCaseを検索
   ↓
Case → Correction → Rule
  └→ Workflow → Validation
   ↓
Codexが過去事例を踏まえて作業
   ↓
終了時
   ↓
今回の修正・手順をKnowledge Graphへ追加
```

Basic Memoryでは、Markdownファイルがノードです。

```text
cases/過去事例.md          → Case node
rules/原図保持.md          → Rule node
workflows/文書修正.md      → Workflow node
```

Markdown中の

```text
- learned_from [[過去事例]]
- implemented_by [[文書修正]]
```

がKnowledge Graphのedgeです。

---

# 1. インストールは何をするのか

インストールスクリプトは、順番にこれだけ行います。

```text
STEP 1
uvを確認
   ↓
STEP 2
Basic Memoryをインストール/更新
   ↓
STEP 3
Basic Memory公式Codex pluginをインストール
   ↓
STEP 4
Markdownを保存するKnowledgeフォルダを作成
   ↓
STEP 5
Case / Rule / Workflowなどのフォルダ作成
   ↓
STEP 6
7種類のSchemaを配置
   ↓
STEP 7
Codexに「このBasic Memory projectを使う」と設定
   ↓
STEP 8
2本だけ追加Hookを設定
```

ECCは変更しません。

---

# 2. まず普通に実行する

Linux / WSL2:

```bash
chmod +x install_basic_memory_workgraph.sh
bash install_basic_memory_workgraph.sh
```

デフォルトでは:

```text
Basic Memory project:
  codex-memory

Knowledge保存先:
  ~/knowledge/codex-memory/
```

が作られます。

---

# 3. 保存先を自分で決めたい場合

例えば:

```bash
MEMORY_PROJECT=work-memory \
MEMORY_DIR="$HOME/knowledge/work-memory" \
bash install_basic_memory_workgraph.sh
```

これは、

```text
Basic Memory上の名前 = work-memory

実際のMarkdown保存場所 =
~/knowledge/work-memory/
```

という意味です。

---

# 4. インストール後にできるフォルダ

例えばデフォルトの場合:

```text
~/knowledge/codex-memory/

├── cases/
├── corrections/
├── rules/
├── workflows/
├── validations/
├── artifacts/
├── projects/
├── schemas/
└── Work-Knowledge-Graph.md
```

役割:

| Folder | Meaning |
|---|---|
| cases | 過去に実施した具体的な仕事 |
| corrections | ユーザーからの明示的な修正 |
| rules | 条件付きの再利用ルール |
| workflows | うまくいった作業手順 |
| validations | 確認・評価手順 |
| artifacts | 成果物への安全な参照 |
| projects | プロジェクトや長期スコープ |
| schemas | 上記ノートの構造 |

---

# 5. Codex側に何が追加されるか

```text
~/.codex/basic-memory.json
```

Basic Memoryの保存先設定。

```text
~/.codex/hooks/basic_memory_workgraph_recall.py
```

仕事開始前に過去事例を検索させるHook。

```text
~/.codex/hooks/basic_memory_workgraph_save.py
```

仕事終了前に今回の知識を保存させるHook。

```text
~/.codex/hooks.json
```

上記2本のHook登録。

既存hooks.jsonがある場合はバックアップしてからマージします。

---

# 6. Hookの意味

## UserPromptSubmit

あなたが依頼すると:

```text
「PDFを翻訳して。図はそのまま」
```

HookがCodexへ、

```text
Basic Memoryから似たCaseを探す
↓
関連Caseを起点に2〜3 hop辿る
↓
Correction
Rule
Workflow
Validation
を確認する
```

よう指示します。

---

## Stop

Codexが今回の仕事を終えようとすると:

```text
今回に再利用価値があるか？
```

を1回だけ評価させます。

例えば:

```text
Case
「PDF日本語翻訳」

received
 ↓
Correction
「図を再生成しない」

generalized_to
 ↓
Rule
「原図保持指定時は再描画しない」

implemented_by
 ↓
Workflow
「原図抽出→本文翻訳→再配置」

validated_by
 ↓
Validation
「原図との比較」
```

のようなKnowledge Graphを作ります。

すべてのターンで必ず大量のノートを作るわけではありません。

---

# 7. 自動保存モード

デフォルト:

```text
smart
```

修正・判断・大きな仕事のときだけKnowledge保存処理が走ります。

毎ターン実行する場合:

```bash
BM_AUTO_MODE=always \
bash install_basic_memory_workgraph.sh
```

停止:

```bash
BM_AUTO_MODE=off \
bash install_basic_memory_workgraph.sh
```

通常は`smart`推奨です。

---

# 8. インストール後の必須操作

Codexを完全に再起動してください。

Codexで:

```text
/plugins
```

`codex@basic-memory`を確認。

次に:

```text
/hooks
```

以下を確認してtrust:

```text
Searching Basic Memory Work Knowledge Graph
Updating Basic Memory Work Knowledge Graph
```

その後:

```text
$bm-status
```

---

# 9. 最初のテスト

会話1:

```text
PDF翻訳で「図をそのまま」と指定した場合は、
図を再生成せず原図を使ってください。

今回の修正を、次回も使える事例として記憶してください。
```

仕事終了後にKnowledgeが保存されます。

新しいCodex会話を作ります。

```text
PDF翻訳をします。

Basic Memoryから過去の似たCaseを検索し、
関連するRule、Workflow、Validationを辿ってから作業してください。
```

関連Knowledgeを参照できれば成功です。

---

# 10. 解除

追加した自動Knowledge Graph Hookだけ外す:

```bash
chmod +x remove_workgraph_hooks.sh
bash remove_workgraph_hooks.sh
```

これは削除しません:

- Basic Memory本体
- Basic Memory公式Codex plugin
- 保存済みMarkdown
- Knowledge Graph
- Schema

---

# ECCとの役割分担

```text
ECC
├─ eval-harness
└─ 作業Skill

Basic Memory
├─ Case
├─ Correction
├─ Rule
├─ Workflow
├─ Validation
└─ Relation Graph
```

ECCは「今回どう作る・どう検査する」。

Basic Memoryは「過去に何が起き、どう改善し、どの手順が有効だったか」。

最初からOMEGAも併用せず、この2つから始める方が管理しやすいです。
