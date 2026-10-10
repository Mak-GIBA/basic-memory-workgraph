# Design Research 2.4.0 — single-entry workflow

**Codexで使うのは `$design-research` だけです。** `$upstream-new` / `$upstream-change` はシステム全体の要件→設計→検証を担当し、その途中で本Skillの研究機能を使います。

短い指示例: `$design-research 検索精度を改善して`、`$design-research 前回の検討を見直して`、`$design-research 研究状況を教えて`。

内部では `research`, `plan`, `workstream`, `reassess`, `resume`, `status` に振り分けます。新機能全体は要件整理→コアロジック分解→テーマ単位の研究→統合設計→検証計画の順。選択根拠・止める箇所は `overlay/tools/design-research/skill/references/workflow-guide.md` を参照。

従来2.3.0でインストールした5つのショートカットSkillは、次の更新時に **改変のない所有済みフォルダだけ** バックアップへ退避してSkill一覧を簡潔にします。個別に編集したもの・所有者不明な同名フォルダは保存します。機能は共通Skillから使えます。

## インストール

このパッケージは前版と同様に、実行時にGitHubの固定版ベース2つをハッシュ検証してからパッチ適用・インストールする組立式です。通常実行にはネット接続が必要で、GitHubへのログインは不要です。

```bash
bash install_design_research.sh --dry-run --update
bash install_design_research.sh --update
bash install_speckit_upstream.sh --apply --update
```

既存の導入先のユーザー編集を無断上書きせず停止します。古いショートカットが編集済みのときは消しません。

2.4.0は主要指標・入力・採点・採用条件を実験前に固定し、親実行器が実出力を再採点します。報告には共通入力、期待値、各方式の実出力と成果物リンクを載せます。効果検証で主要効果が未測定なら完了しません。設計・文献調査では未測定を明示して条件付きの結論を出せます。MCP以外のアルゴリズム、検索、エージェント、技術選定にも同じ契約を使います。

比較設計と実験準備を別工程で保存し、再開時に検証済みの工程を再利用します。長い指示は標準入力でCodexへ渡し、比較設計を重複して渡しません。検証範囲と実モデルの制約は[検証結果](../../docs/design-research/validation.md)を参照してください。ユーザーが計画だけ求めたときは研究を開始しません。

## ファイル

- リポジトリ直下の両インストーラー: 固定版を検証して組み立てるbootstrap
- このディレクトリ: パッチの保守元、参照資料、テスト、bootstrapのテンプレート
- `build_bootstraps.py`: この保守元を決定的なZIPにして両bootstrapへ埋め込む。`--check`で一致を確認
- `build_installers.py`: 固定版へパッチを適用し、検証済みの通信不要な通常インストーラーを出力


## ワークフロー上の現在地

内部の `scripts/workflow_overview.py --project <project>` は、要件と研究計画・完了runを照合して、現在の工程（未分割・研究準備・研究進行・統合待ち）と実行可能なテーマを読み取り専用で表示します。計画変更や研究実行はしません。

例えば `RP1`・`RP2` が独立で `RP3` がそれらの選定結果に依存するとき、最初の状態は `RP1`・`RP2` が `ready`、`RP3` が `blocked_by_dependency` です。完了したrunを同じ計画ハッシュで照合した後に `RP3` が実行候補になります。全テーマの完了後も、結合した性能と全体設計はupstreamが検討します。

**実行境界:** 各runのハーネスは現在の仕様では同じprojectのロックで直列に実行されます。並列群の表示はスケジュール案であり、自動並列実行ではありません。独立した全プロジェクトへの自動コード変更やPR作成も行いません。
