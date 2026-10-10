# Upstream × Design Research：要件駆動コアロジック分解版

## このパッケージの状態

改修コード・テンプレート・適用スクリプトです。**GitHub上のリポジトリへは未反映で、PRも未作成です。**
対象は `Mak-GIBA/basic-memory-workgraph` の確認済みmain、コミット `d3f46e0d591b45cb2423317030a489b91566e891`。
今回の接続ではブランチ作成が403で拒否されました。

既存の研究ハーネス・上流CLIを差し替えるのではなく、追加モジュールと小さな呼び出し箇所の修正で接続します。
過去に作成した提案手法章・約5方式比較・3種類のSVG図の拡張も同梱し、対象mainにまとめて適用します。
その完全適用版が既に存在する場合は記録を検証して引き継ぎます。未公開の独自v2.1版など、未確認の変更は自動マージしません。

## 改善内容

| 項目 | 変更 |
|---|---|
| 初見向けドキュメント | 目的、対象、具体例、用語、全体から詳細への図解、読み方、限界を指示・検査・出力へ接続します。 |
| 設計前の方式検討 | 新規/方式変更の設計はdesign-researchを必須にし、現行の正本要件を研究入力に固定します。 |
| 段階的なdesign.md | 全体アーキテクチャ→主要コンポーネント→代表処理→データ/API/フレームワークと選定理由の順で説明します。 |
| 再検討モード | 完了済みresearchから新しいreassessを開始し、前回案と別原理の案を含めて再比較します。 |
| ストーリーと使い勝手 | 未解決の懸念を確認し、成功・失敗・中断復帰を含むユースケースから検証可能な要件を作ります。 |
| 画面例のUI/UX連携 | 実在するooui-design等を使用し、適用内容、画面資材、確認内容、未確認範囲を記録します。 |

研究前の要件レビュー/承認→研究の実行→研究に基づく設計→設計のレビュー/承認を分けます。
CLI `flow` 自体が研究を自動起動するわけではありません。Skillの手順と、研究根拠を確認するready検査の両方を追加しています。

## ローカルチェックアウトへの適用

BashとPython 3.11以上が必要です。Windowsでは既存インストーラーと同様にLinux/WSL環境で扱います。
ZIPを展開したディレクトリで実行してください。

```bash
# 変更予定のみ。リポジトリは変更しません。
python3 upstream_research_light_upgrade/apply_upgrade.py \
  --repo /path/to/basic-memory-workgraph --dry-run

# 一時コピーで適用・検証・再生成し、成功したバイト列だけを元へ戻します。
python3 upstream_research_light_upgrade/apply_upgrade.py \
  --repo /path/to/basic-memory-workgraph --apply
```

スクリプトはGitHubからの取得・git commit/push・依存のインストール・Codex起動・グローバル設定変更をしません。
完全なチェックアウトが必要です。以前配布したネット取得式bootstrapだけにこの更新を適用するものではありません。
対象ソースのハッシュ/統合箇所が一致しなければ停止します。強制上書きのオプションは設けていません。
既存のカスタム拡張を上書きせず、同じパッケージの適用後に編集があれば再適用を拒否します。
一時コピーでの検証に失敗した場合は原本を変更しません。バックアップとログの場所は結果/エラーに表示します。
検証中に対象ソースが変わった場合も原本へ反映しません。外部プロセスによる同時編集への完全な排他制御ではありません。

成功後に再生成される配布物は次の2つです。

```text
install_design_research.sh       Design Research 2.2.2
install_speckit_upstream.sh      Upstream Workbench 2.0.3
```

それぞれ元のビルド方式で保守元ソースを内蔵します。このZIPには、未検証の再生成済みインストーラーは入れていません。
Skillを実際に更新する操作は、ソースの更新とは別です。差分確認後に実行します。

```bash
bash install_design_research.sh --update
bash install_speckit_upstream.sh --apply --update
```

公式SpecKit本体が未導入の場合の取得方針は元のupstreamインストーラーのままです。必要に応じて既存の`--skip-specify`を使用します。
新しいMCP、サービス、フック、Memory設定、個人のCodex設定は追加しません。

## 再検討モードの利用

```bash
bash /actual/skill/design-research/scripts/gan-harness.sh reassess \
  --project /path/to/project \
  --prior-run docs/design-research/previous/runs/ACTUAL_RUN_ID/state.json \
  --slug revised-method \
  --brief "変更された要件と、前回よりよい方式を再検討する理由" \
  --requirements docs/upstream/requirements.md \
  --report-profile proposed-method --target-methods 5 --allow-network
```

実際のSkill、完了済みrun、要件正本のパスへ置き換えます。新規研究にはresearch、中断した同じ研究にはresumeを使います。
reassessは新しいslugを必要とし、前回のstateとアーカイブreportを変更しません。過去の測定を新規実測として登録しません。
前回の案を比較対象に残し、少なくとも1つの離れた原理について、差分、作用機序、反証条件、コマンド、前提、実験IDを定めます。
既存の検索・反復・隔離実験の上限を維持します。5候補を5つの高コスト学習ジョブとして全実行する必要はありません。
前回案の維持、悪化、同等、判断保留も有効な結論です。

対象の旧実行は現時点では**完了済みresearchのstate.json**です。任意のPDF報告や未完了auditを自動的に検証済み入力へ変換する機能ではありません。

## 初見向けの研究報告

Skillの通常のresearch/audit/run呼び出しには`--reader-friendly`を指定します。
新CLIフラグを指定しない従来呼び出し・既存のresume設定はそのままです。
researchには構造化された説明と全体/詳細の図を求め、提案手法章のSVGを使える場合は二重掲載しません。
audit/runでは架空の対象アーキテクチャを描かず、確認の段取りと記録された検証範囲を図で説明します。

- 新しい設計の雛形：`overlay/tools/speckit-upstream/assets/templates/design.md`
- 研究前の要件・設計・画面例の手順：`overlay/tools/speckit-upstream/assets/references/RESEARCH_FIRST.md`
- 初見向け研究レポートの契約：`overlay/tools/design-research/skill/references/readable-documents.md`
- 再検討の契約：`overlay/tools/design-research/skill/references/reassessment.md`

Mermaidの図は対応Markdownビューアーで表示します。対応しない媒体では図を画像へ出力して確認する手順を記載していますが、新しい画像サービスやレンダラーは導入しません。
提案手法章の3種類の図は従来拡張のSVG出力を維持します。

## ready検査と互換性

新規/方式変更したdesign.mdにはv2 markerと研究runへのbindingを追加します。
`check --phase ready`は、各研究テーマの完了state/報告、ハッシュ、要件スナップショット、実在する候補と設計IDの対応、段階的な図解、UI/UXの記録を検査します。
`gate`のスナップショットには研究・正本要件・関連画面/図の資材も含めます。
旧文書は警告のみで、自動移行・自動再承認・一括書き換えはしません。ただし方式を新たに設計し直す際は新契約を使用します。
この互換性のため、全ての既存文書に対する強制アクセス制御にはなっていません。古い形式へ戻して新規設計の義務を回避しない運用が必要です。

要件はバイト単位で固定します。表記・承認情報の変更も再確認対象になり、意味が同じだと自動推測して無視しません。
機械検査は資料や図の意味・研究の科学的妥当性・実際のSkill使用・人間の使用感を保証しません。内容のレビューは必要です。

## 検証したこと・していないこと

前版は134件のテストが成功しています。今回の追加45件を含め、合計179件のテストが成功しました。実ログはvalidation/workstreams-tests.log、内訳はvalidation/workstreams-summary.jsonです。
前版の内訳は契約/統合箇所/トランザクションの70件、持ち越した提案手法拡張の56件、配布先upstream用の新規8件です。
テスト用runと要件は明示した架空fixtureです。実際の研究の成功やユーザー承認を作ったものではありません。
前版の検証環境はPython 3.13.5。今回の環境は新しい検証記録に記載します。実モデルとブラウザーでの操作感は未検証です。

**GitHubの完全な現行チェックアウトをこの環境へ取り込めていないため、現行main全体での回帰試験・インストーラー再生成・実際のSkill実行は未実施です。**
適用スクリプトはユーザーの完全なチェックアウトの一時コピーで、両ビルダー、両インストーラーのself-test、関連する既存回帰試験を実行し、全成功前には原本へ反映しない構成です。
この構成自体の安全停止・ロールバック等はミニチュアfixtureで検証しています。実mainで既存テストが追加修正を要する可能性は残ります。

```bash
python3 upstream_research_light_upgrade/run_tests.py
```

`validation/tests.log`に実行ログ、`validation/summary.json`に範囲を記録しています。
`previous_report_upgrade/validation`とsamplesは前回拡張の記録で、今回の現行mainでの実行記録ではありません。

## 今回の追加：要件を満たすための研究テーマを分ける

全体を1回の研究へ渡すのではなく、必要能力→コアロジック→判断する問いへ分解します。
テーマ数は要件から決めます。約5手法はテーマごとの比較候補数の目安です。

- `research_workstreams.py`：要件との対応、入力/出力契約、依存DAG、計画予算、資源競合の検査と実行バッチ案。
- 実研究への`--workstream-plan` / `--workstream-id`：テーマを一つ選んで入力を凍結し、role promptへ渡す。
- design契約v2：複数研究→一つの全体設計を許容。standard分類の設計は既存根拠で説明し、不要な研究は要求しない。
- 統合の計画/実証を区別し、局所的な改善だけを全体成功と扱わない。

**並列ランナーそのものではありません。** 同じprojectは既存のロックを維持して直列化します。
独立コピーの準備と並列起動・結果回収はホストの親担当が行います。CLIはその可否・順序の計画と検査を提供します。
本更新はリポジトリ本体、GitHubのbranch/PR、個人設定を変更しません。
前版パッケージを既に適用してあるチェックアウトへの自動差分更新は行わず、安全のため拒否します。
元の確認済みベースまたは検証済み提案手法拡張に対して適用し、独自変更は内容を見てマージしてください。

詳細：`overlay/tools/speckit-upstream/assets/references/RESEARCH_WORKSTREAMS.md`。
合成例：`examples/workstream-demo/`。この例には実研究結果や実行済みrunはありません。
