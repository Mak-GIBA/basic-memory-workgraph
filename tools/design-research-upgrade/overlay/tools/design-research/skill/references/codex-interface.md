# Design Researchの内部Codexインターフェース

**ユーザーが呼ぶのは `$design-research` だけです。** 利用目的・ワークフローの
使い分けは [workflow-guide.md](workflow-guide.md) に定義されています。

`reassess` / `plan` / `workstream` / `resume` / `status` はユーザーに覚えてもらう
別Skillではなく、統一Skill内から使う内部工程です。旧2.3.0版の個別Skillは、
所有権が確認できて未編集のものだけインストーラーが移行時に退避・整理します。
ユーザー自身が編集したSkillや第三者の同名Skillは保護し、無断削除しません。

## 内部処理の責務

- `scripts/workflow_overview.py --project <project>`: 要件・計画・過去runから現段階と次の候補を読み取り専用で表示。
- `scripts/codex_interface.py runs`: 過去runを実在パス・状態と共に確認。read-only。
- `scripts/research_workstreams.py`: 要件IDから技術的な問いを分解し、依存関係、評価指標、計算予算、統合検証を扱う。
- `scripts/codex_interface.py prepare research`: 新規の単一方式検討。
- `... prepare workstream`: 固定した計画の研究テーマの一つを実行準備。
- `... prepare reassess`: 完了した過去研究の新しい条件での再検討。
- `... prepare resume`: 中断済み同条件runの続行。
- `... workstreams`: 依存・実行段階の計画確認。並列ジョブの起動ではない。
- `... run MODE --expect-dispatch SHA`: prepareと同じ入力を検査後に実ハーネスを実行。

`prepare`のreadyは研究が成功したことではありません。ユーザーの範囲、通信許可、
入力要件、既存サンドボックスとロックを確認してください。
前回の計測を今回の実測とは扱いません。最新という理由だけで過去runを選びません。

2.4以降は`--report-profile comparison`が既定です。提案手法の詳細章が必要なら
`proposed-method`を指定します。`--evaluation-purpose`はauto / effectiveness /
design / literatureから選び、効果検証依頼ではeffectivenessにします。prepareの
dispatch hashが両者を固定するため、runで変更すると実行を拒否します。
resumeは既存runの目的・指標・profileを引き継ぎ、新しい指定は受け付けません。
詳しくは[主要指標と対照実験](effectiveness-evaluation.md)を確認してください。

## upstreamとの責務分担

`$upstream-new` / `$upstream-change` がストーリー・要件・全体設計を管理し、
その途中で `$design-research` が技術的な問いの抽出・比較・PoC・研究報告を担当します。
最後にupstreamが複数研究の整合性と全体アーキテクチャをレビューし、
図解付きdesign.mdと検証計画へ反映します。

既存のルールでは同一projectの研究ハーネス実行はロックに従い直列です。
並列可能と書かれた実行計画は並列実験済みを意味しません。完全な自動スケジューラ、
過去run検索結果からの自動選択、研究成果の科学的正しさの保証はありません。
CodexのSkill自動起動はモデルの振る舞いであるため、短い入力や否定例を実機評価してください。
