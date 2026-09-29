# Design Research

[docs一覧](../README.md) · [導入手順](installation.md) · [使い方](usage.md)

技術・アーキテクチャ・アルゴリズム・AIエージェントの実現方式を、プロジェクトの制約、論文、公式資料、
必要に応じた小さな実験から比較するCodex Skillです。候補の一覧だけでなく、採用を勧める条件、
根拠、未確認事項、判断を見直す条件を残します。

対象は[install_design_research.sh](../../install_design_research.sh)です。
Skillと補助コードを内蔵した単一ファイルで、隣に資材を置く必要はありません。
この説明は配布スクリプトと埋め込み資料のv1.1.0を基準にしています。

## 導入するツールと役割

| ツール・資材 | 形式・提供元 | 用途 | 導入条件 |
|---|---|---|---|
| `design-research` | このスクリプト独自のCodex Skill | 制約の整理、基準案との比較、根拠の読解、反証の検討、判断の提案 | 標準 |
| `scripts/research.py` | 独自Python CLI | 文献の検索・ID照会・引用関係の取得、調査資料の初期化、証拠台帳の構造検証 | 標準 |
| `scripts/literature.py`・`scripts/dossier.py` | CLIを支える独自Pythonコード | API通信・キャッシュと、成果物の生成・検証 | 標準 |
| `references/`・`templates/` | 独自の参照資料・雛形 | 調査手順、証拠形式、エージェント設計の検討項目、レポート・判断記録 | 標準 |
| `agents/openai.yaml` | Codex向けの表示設定 | Skillの表示・呼び出しを補助 | 標準 |

**Design Researchはこのリポジトリ独自の追加キットです。**
インストーラーは論文検索サービスやモデル、MCPサーバーを導入しません。
補助CLIはarXiv・Semantic Scholar・Crossref向けの検索機能を持ちますが、取得するのは書誌情報・要旨・リンクです。
論文全文の取得・読解には、利用環境のブラウザー・PDFツールや利用者が用意した資料を使います。

## どのような場面で使うか

- 現行方式と新しいアルゴリズムを、同じ条件で比較したい。
- 単一エージェント・複数エージェント・通常のコードのどれが目的に合うか検討したい。
- 論文の評価結果が自分のプロジェクトにも当てはまるか、制約と不足する証拠を整理したい。
- 技術選定の理由と、次に行う最小限のPoCを他の開発者へ引き継ぎたい。

仕様書は必須ではありません。相談内容、リポジトリ、Issue、既存の比較資料から始められます。
画面の見た目だけを検討する用途は[UX Stack](../codex-ux-stack/README.md)、
要件・設計文書全体の整理は[SpecKit Upstream](../speckit-upstream/README.md)が別の入口です。
Design Researchは方式選定の判断と根拠をそれらへ渡せますが、SpecKit・Basic Memory・特定のMCPは必須ではありません。

## 読む順序

1. [導入手順](installation.md)で配置先と変更範囲を確認する。
2. [使い方](usage.md)で、問題と制約を添えて`$design-research`を呼び出す。
3. 提案と根拠の限界を確認し、必要な実験や実装を次の作業として決める。

## 参照資料

配布済みの`SKILL.md`と`references/protocol.md`が全体の手順、`references/providers.md`がCLIの使い方、
`references/evidence-format.md`が証拠台帳の形式を説明しています。
`references/sources.md`にはパッケージ作成時の参照元が記録されています。
これらは[導入手順](installation.md)の`--extract`でも確認できます。
