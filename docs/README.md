# ドキュメント一覧

[リポジトリ概要](../README.md)

インストーラーごとに、概要・収録ツール、導入手順、利用ガイドをまとめています。
初めて使う場合は、概要から目的に合うものを選んでください。

| 対象 | 概要・収録ツール | インストール・更新・解除 | 導入後の使い方 |
|---|---|---|---|
| 知識を蓄積する | [Basic Memory Workgraph](basic-memory-workgraph/README.md) | [導入手順](basic-memory-workgraph/installation.md) | [使い方と設定](basic-memory-workgraph/usage.md) |
| UI/UXを設計・実装・確認する | [Codex UX Stack](codex-ux-stack/README.md) | [導入手順](codex-ux-stack/installation.md) | [使い方](codex-ux-stack/usage.md) |
| 要件・設計・検証計画を整理する | [SpecKit Upstream](speckit-upstream/README.md) | [導入手順](speckit-upstream/installation.md) | [使い方](speckit-upstream/usage.md) |
| GitHubのIssue・PR・Projects・進捗を整理する | [GitHub Project Director](codex-github-pm/README.md) | [導入手順](codex-github-pm/installation.md) | [使い方](codex-github-pm/usage.md) |
| 根拠に基づいて技術・実現方式を比較する | [Design Research](design-research/README.md) | [導入手順](design-research/installation.md) | [使い方](design-research/usage.md) |

## Workgraphを詳しく使う

- [Memoryの共有・インポート・学習用JSONL出力](basic-memory-workgraph/sharing.md)
- [保存方針・配置・仕組み](basic-memory-workgraph/reference.md)
- [困ったとき・記憶の点検](basic-memory-workgraph/troubleshooting.md)

## 文書の読み方

`bash`や`python3`のコードブロックはターミナルで実行します。特に指定がなければ、
このリポジトリのルートが作業場所です。`text`の依頼例はCodexの会話欄へ入力します。
SpecKitのプロジェクト操作、UX Stack・GitHub Project Director・Design Researchの利用例は、作業対象のプロジェクト側で行います。

「Plugin」は機能をまとめた配布単位、「Skill」はCodexが参照する作業手順、
「MCP」は外部ツールをCodexから呼び出すための接続です。
「CLI」はターミナルで実行するコマンド、「hook」は会話等のイベントに応じて動く処理を指します。

各ガイドのインストール挙動は、このリポジトリにあるスクリプトを基準にしています。
外部ツールの配布名や機能は変わることがあるため、参照資料と導入時の確認方法も掲載しています。

## 開発・説明の追加

[開発ガイド](development.md)に、検証方法、説明の保守方針、
[新しいインストーラー用の雛形](_templates/installer/README.md)の使い方をまとめています。
