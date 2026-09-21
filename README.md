# Basic Memory Work Knowledge Graph

案件をまたいで役立つ検証済みの知識と、ユーザーが明示した継続的な好みを
Basic Memory に保存し、次回の仕事で再利用するための Codex フックです。

```text
依頼 → 関連する Rule / Workflow / Case を検索 → 条件を比較して活用
                                                    ↓
                             好み・教訓の候補があれば保存可否を評価
                                                    ↓
                         基準に合格 → 重複検索 → 必要な作成・更新だけ
                         不合格・同じ内容 → 何も保存しない
```

## 保存するもの

共通の正本は [memory-policy.md](memory-policy.md) です。自動保存する技術的な知識は、
次の条件を**すべて**満たす必要があります。

| 基準 | 必要な内容 |
|---|---|
| 再利用性 | 元の案件以外で使える具体的な場面 |
| 有用性 | 次回の判断・手順をどう改善し、どの失敗や再調査を減らすか |
| 根拠 | 実際の検証による裏付け。十分な根拠があれば1回でもよい |
| 持続性 | 一時的な状態に依存しない知識と、適用条件・例外 |
| 追加価値 | 既存メモや容易に確認できる一般知識にはない価値 |

ユーザーが今後も適用すると明示した好みも、範囲と例外を添えて保存します。
単発の修正から恒久的な好みを推測しません。

以下は自動保存しません。

- 作業日誌、完了報告、成果物一覧、会話の引き継ぎメモ
- 案件固有の判断、今回だけの修正
- 抽象的な一般論、未検証の推測
- 既存メモと同じ内容、利用日時や進捗だけの追記

迷った場合は保存しません。明示的な「これを覚えて」という依頼は例外として、
案件固有でも指定された内容と範囲だけを保存できます。計画モードなどで
書き込みが禁止されている間は保存しません。

フックは候補を見つけて**評価を依頼する**もので、Basic Memory に直接書き込みません。
意味内容の合否は Codex が共通基準で判断します。キーワード一致は保存の許可ではなく、
MCP サーバー側で全クライアントの書き込みを強制的に制限する仕組みでもありません。

## 導入

Linux / WSL2 で、このリポジトリ一式を配置して実行してください。
スクリプトは同梱の Python ファイルとポリシーファイルを使用します。

```bash
bash install_basic_memory_workgraph.sh
```

通常の導入は `uv` / `uvx`、Basic Memory、公式 Codex plugin を確認・導入し、
保存プロジェクト、7種類のスキーマ、設定、追加フックを作成します。ECC は変更しません。

公式 plugin の MCP 起動には `uvx` が必要です。`uv` だけが PATH にある場合は、
実体と同じフォルダの `uvx` を `~/.local/bin/uvx` にリンクします。
見つからなければ公式インストーラーで導入し、両方の実行を確認します。

新規導入のデフォルトは次のとおりです。

```text
Basic Memory project: codex-memory
Markdown 保存先:      ~/knowledge/codex-memory/
Codex 設定先:         ~/.codex/（CODEX_HOME 指定時はその場所）
自動評価モード:        smart
```

保存先を指定する場合:

```bash
MEMORY_PROJECT=work-memory \
MEMORY_DIR="$HOME/knowledge/work-memory" \
bash install_basic_memory_workgraph.sh
```

### 既存環境の設定・フックだけを更新する

```bash
bash install_basic_memory_workgraph.sh --configure-only
```

この経路は Python 3 だけで実行できます。パッケージの更新、プロジェクト登録、
スキーマ作成、保存済みメモの変更は行いません。既存の `primaryProject` と
自動評価モードを維持し、環境変数で明示した場合だけ上書きします。
`MEMORY_DIR` はこの経路では使用しません。

設定とフックは変更前に日時付きの `.bak.*` へバックアップします。
無関係な設定と他のフックを保持し、不正な JSON は上書きせずエラーにします。
同じ内容で再実行してもフックやバックアップを増やしません。

## 自動評価モード

| モード | 動作 |
|---|---|
| `smart`（標準） | 依頼・回答に継続的な好みや教訓の候補を示す表現がある場合に評価 |
| `always` | 毎ターン評価。保存基準は同じ |
| `off` | 自動評価・自動保存を停止。明示的な保存依頼は利用可能 |

文字数だけを理由に評価を起動しません。`smart` の候補検出は日本語・英語の
表現に基づくため、すべての教訓を検出するものではありません。
保存したい内容が明確なら、明示的な保存依頼を使用できます。

```bash
BM_AUTO_MODE=always bash install_basic_memory_workgraph.sh --configure-only
BM_AUTO_MODE=off bash install_basic_memory_workgraph.sh --configure-only
BM_AUTO_MODE=smart bash install_basic_memory_workgraph.sh --configure-only
```

## 配置と設定

| 配置 | 役割 |
|---|---|
| `~/.codex/basic-memory.json` | 保存先と共通基準。`checkpointOnCompact` は `false` |
| `~/.codex/basic-memory-workgraph/memory-policy.md` | 開始・終了フックが読む共通基準 |
| `~/.codex/basic-memory-workgraph/config.json` | `smart` / `always` / `off` |
| `~/.codex/hooks/basic_memory_workgraph.py` | 開始時の検索・保存基準注入と終了時の評価依頼 |
| `~/.codex/hooks.json` | 追加フックの登録 |

`CODEX_HOME` を指定した場合、追加フックはその設定先を使用します。
公式 plugin の設定探索はその plugin の仕様に従います。

ポリシーを変える場合はリポジトリの `memory-policy.md` を編集し、
`--configure-only` を再実行してください。`placementConventions` にも同じ内容を反映します。
既存セッションが旧フックのパスを保持している場合も、新しい処理へ転送します。

圧縮時の自動チェックポイントは無効にします。`captureEvents` は既存値を維持します
（未設定なら `true`）。これは知識グラフにノートを作らないローカルのイベント記録です。
プロジェクトの `.codex/basic-memory.json` がある場合、そのキーはユーザー設定より
優先されるため、導入後に有効設定を確認してください。

### ノートの種類

| Folder | 用途 |
|---|---|
| `rules/` | 条件付きの再利用ルール、明示された継続的な好み |
| `workflows/` | 検証済みの再利用手順 |
| `validations/` | 再利用できる確認手順 |
| `cases/` | 既存事例、または明示的な保存依頼による具体的な仕事の記録 |
| `corrections/` | 明示的な保存依頼による修正記録 |
| `artifacts/` | 明示的な保存依頼による成果物参照 |
| `projects/` | 明示的な保存依頼による長期スコープ |
| `schemas/` | ノート構造の定義 |

自動保存のために Case → Correction → Rule などの一式を作る必要はありません。
根拠は保存対象のノート内に簡潔に記録し、既存ノートとの関係が役立つ場合だけ
`implements [[Rule]]` や `validated_by [[Validation]]` などの型付きリンクを追加します。

## 導入後の確認

新しい Codex セッションを開始してください。フックの登録が反映されない場合は
Codex を再起動し、`/hooks` で次の2項目を確認します。

```text
Searching Basic Memory Work Knowledge Graph
Evaluating reusable Basic Memory knowledge
```

公式 plugin は `/plugins` で `codex@basic-memory` を確認できます。
必要なフックの trust は Codex の画面で設定してください。

```bash
bm hook status --harness codex --project-dir "$PWD"
```

`primary project` が意図した保存先で、`checkpoint on compact: off` であることを確認します。
`capture events` は既存の選択どおりであることを確認します。

保存判断の例:

```text
「今後、PDF翻訳で原図保持を指定したときは、図を再生成せず原図を使って」
→ 継続的な好みとして、条件とともに保存候補にする。

「今回のボタンだけ青くして」
→ 単発の修正なので自動保存しない。

「ファイルを修正し、全テストが通った」という長い完了報告
→ 再利用できる新しい教訓がなければ自動保存しない。
```

## 検証

```bash
python3 -m unittest discover -s tests -v
bash -n install_basic_memory_workgraph.sh remove_workgraph_hooks.sh
```

テストは一時ディレクトリで設定更新、保存評価の起動条件、再入防止、旧フックからの
移行、他のフックの保持を確認します。実際の Basic Memory へは書き込みません。
意味内容の評価例は [tests/POLICY_SCENARIOS.md](tests/POLICY_SCENARIOS.md) にあります。

## 解除

```bash
bash remove_workgraph_hooks.sh
```

追加フックとそのローカル設定・状態を削除します。Basic Memory 本体、公式 plugin、
保存済みメモ、スキーマ、`basic-memory.json` は残ります。
したがって、保存基準と自動チェックポイントの無効設定もそのまま残ります。
