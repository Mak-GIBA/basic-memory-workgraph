# Basic Memory Workgraph

[docs一覧](../README.md) · [導入手順](installation.md) · [使い方と設定](usage.md)

Codexでの作業から、次の仕事にも役立つ知識をBasic Memoryへ蓄積するためのツールです。
成功した手順やユーザーの修正を振り返り、再利用できるルール・具体事例・Skillを関連付けます。
修正指示を状況と望ましい出力の組として蓄積し、似た依頼の初回出力から活用できます。

対象スクリプトは[install_basic_memory_workgraph.sh](../../install_basic_memory_workgraph.sh)です。
このインストーラーはリポジトリ内のPythonコードやテンプレートも使うため、リポジトリ一式が必要です。
補助資材は`tools/basic-memory-workgraph/`にまとまっています。ルートのインストーラーから呼び出します。

## 導入するツールと役割

| ツール・資材 | 提供元 | 役割・使う場面 |
|---|---|---|
| uv / uvx、Python 3.12 | AstralのツールとPythonランタイム | Basic Memoryの実行環境を用意する。uvxは公式pluginのMCP起動にも必要 |
| Basic Memory（`bm`） | Basic Memory | Markdownノートを保存・検索し、知識同士の関係を扱う基盤 |
| `codex@basic-memory` plugin | Basic Memory | CodexからBasic Memoryを使う連携機能とSkillを提供 |
| Workgraphの方針・スキーマ・Graph索引 | このリポジトリ | Rule、Workflow、Validation、Correction、Case等の保存基準と形式を定義 |
| Workgraphの追加hooks | このリポジトリ | 作業前の知識検索と、作業後の保存価値の評価をCodexへ促す |
| `workgraph_tools.py` / `workgraph_sequence.py` | このリポジトリ | 共有、インポート、JSONL出力、記憶の構造点検、Skill登録とCaseの整合性検証 |

Basic Memoryが保存・検索の基盤、Workgraphが「何を、どの形で残して再利用するか」の運用を担当します。
追加hook自体はMemoryを書き込みません。検索・判断・保存はCodexが行います。
更新用の`update_workgraph.py`や設定用の`configure_workgraph.py`もリポジトリに含まれます。

## できること

- 過去の判断や検証済み手順を、条件の似た新しい作業で再利用する。
- 文脈付きの修正指示を保存し、次回の初回出力に反映する。
- 改善過程をCaseとして記録し、ルールやWorkflowへ関連付ける。
- レビューした知識だけを共有したり、許可したCaseを学習用JSONLへ出力したりする。
- 繰り返す手順をSkill化する価値を検討し、設定を有効にした場合は検証後に登録する。

**導入直後は再利用知識の自動評価が有効です。修正指示・具体事例の自動保存とSkillの自動登録は、設定で有効にします。**
すべての会話を保存するものではなく、保存価値がなければ何も保存しません。
共有や学習への利用は別途指定が必要です。LLMの学習そのものは実行しません。

## 読む順序

1. [導入・更新・解除](installation.md)：環境を準備し、Codex側の反映を確認する。
2. [使い方と設定](usage.md)：依頼例を試し、必要な保存モードを選ぶ。
3. [共有・学習用出力](sharing.md)：レビューした知識を外へ渡す。

保存や更新で困ったら[トラブルシューティング](troubleshooting.md)、
保存基準・内部構成は[リファレンス](reference.md)を参照してください。

## 参照資料

- [Basic Memory公式リポジトリ](https://github.com/basicmachines-co/basic-memory)
- [uv公式ドキュメント](https://docs.astral.sh/uv/)
- このリポジトリの保存方針の正本：[memory-policy.md](../../tools/basic-memory-workgraph/memory-policy.md)

Workgraphはこのリポジトリ独自の追加機能です。Basic Memory本体と公式pluginの更新、
Workgraphの更新は別の操作です。具体的な範囲は[更新手順](installation.md#update)で確認できます。
