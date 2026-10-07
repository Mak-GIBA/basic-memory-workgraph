# ドキュメント一覧

[リポジトリ概要](../README.md)

インストーラーごとに、概要・収録ツール、導入手順、利用ガイドをまとめています。
初めて使う場合は、概要から目的に合うものを選んでください。
全ツールの一括導入やIDによる個別選択は、[一括インストール](installation.md)で説明しています。

| 対象 | 概要・収録ツール | インストール・更新・解除 | 導入後の使い方 |
|---|---|---|---|
| 知識を蓄積する | [Basic Memory Workgraph](basic-memory-workgraph/README.md) | [導入手順](basic-memory-workgraph/installation.md) | [使い方と設定](basic-memory-workgraph/usage.md) |
| OOUIからUI/UXを設計し、実装・画像付き検証・改善を進める | [Codex UX Stack](codex-ux-stack/README.md) | [導入手順](codex-ux-stack/installation.md) | [使い方](codex-ux-stack/usage.md) |
| 要件・設計・検証計画を整理する | [SpecKit Upstream](speckit-upstream/README.md) | [導入手順](speckit-upstream/installation.md) | [使い方](speckit-upstream/usage.md) |
| GitHubのIssue・PR・Projects・進捗を整理する | [GitHub Project Director](codex-github-pm/README.md) | [導入手順](codex-github-pm/installation.md) | [使い方](codex-github-pm/usage.md) |
| 技術・実現方式を比較・実測し、バックエンドを検証・改善する | [Design Research](design-research/README.md) | [導入手順](design-research/installation.md) | [使い方](design-research/usage.md) |
| ECCを導入し、必要なスキルだけ参照する | [Codex ECC](codex-ecc/README.md) | [導入・更新・復元](codex-ecc/installation.md) | [使い方](codex-ecc/usage.md) |
| PDF・Word・PowerPointを閲覧・編集する | [Office Workbench](codex-office/README.md) | [導入手順](codex-office/installation.md) | [使い方](codex-office/usage.md) |
| 日本語の文章を意味を保って整える | [yomiyasu](codex-yomiyasu/README.md) | [導入手順](codex-yomiyasu/installation.md) | [使い方](codex-yomiyasu/usage.md) |
| 作業ディレクトリからターミナルworkspaceを開く | [Herdr](herdr/README.md) | [導入とBash設定](herdr/installation.md) | [使い方](herdr/usage.md) |

## Workgraphを詳しく使う

- [Memoryの共有・インポート・学習用JSONL出力](basic-memory-workgraph/sharing.md)
- [保存方針・配置・仕組み](basic-memory-workgraph/reference.md)
- [困ったとき・記憶の点検](basic-memory-workgraph/troubleshooting.md)
- [採用エビデンスの設計と評価](basic-memory-workgraph/evidence-design.md)

## ECCの管理CLIを詳しく使う

[ECCを必要なときに読む](ecc-on-demand.md)で、原本の検索・取得、更新・復元、停止する起動時処理を説明しています。

## 文書の読み方

`bash`や`python3`のコードブロックはターミナルで実行します。特に指定がなければ、
このリポジトリのルートが作業場所です。`text`の依頼例はCodexの会話欄へ入力します。
SpecKitのプロジェクト操作、各Skillの利用例、Herdrの起動は、作業対象のプロジェクト側で行います。

「Plugin」は機能をまとめた配布単位、「Skill」はCodexが参照する作業手順、
「MCP」は外部ツールをCodexから呼び出すための接続です。
「CLI」はターミナルで実行するコマンド、「hook」は会話等のイベントに応じて動く処理を指します。

各ガイドのインストール挙動は、このリポジトリにあるスクリプトを基準にしています。
外部ツールの配布名や機能は変わることがあるため、参照資料と導入時の確認方法も掲載しています。

## 開発・説明の追加

[開発ガイド](development.md)に、検証方法、説明の保守方針、
[新しいインストーラー用の雛形](_templates/installer/README.md)の使い方をまとめています。
