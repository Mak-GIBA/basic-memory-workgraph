# 再検討モード：reassess

`resume`は中断した同じ検証を同じ条件で続ける。`reassess`は完了済み研究を入力に、**新しい条件と新しい実行ID**で検討し直す。
前回の報告・stateは上書きせず、入力ハッシュを保存する。別slugを必須とする。

```bash
bash <skill>/scripts/gan-harness.sh reassess \
  --project /path/to/project \
  --prior-run docs/design-research/previous/runs/ACTUAL_RUN_ID/state.json \
  --slug revised-method \
  --brief "要件変更の内容、または新しい方式を探す理由" \
  --requirements docs/upstream/requirements.md \
  --report-profile proposed-method --target-methods 5 --allow-network
```

パスは実際の正本・実行IDへ合わせる。要件ファイルが存在しない研究では `--requirements` を省略できる。
ただしupstreamの新たな方式設計を完成させるには、正本要件を指定した研究が必要。

## 検討する内容

前回の課題、候補、採否、限界、失敗例、残った疑問を読む。変わった要件・データ・利用状況・計算予算を対応表にする。
古い知見を「そのまま適用可能」「条件付き」「再測定」「適用不能」に分け、理由を説明する。
同じデータ・指標・計算条件で比較できない新旧結果は、順位表で直接比較しない。

比較は約5手法を目安にし、前回の有力案、最小改良、単純な代替、異なる原理、離れた分野からの転用を検討する。
この分類自体をノルマにしないが、**前回案と少なくとも1つの離れた原理**は必要。
転用では、元分野の前提、対象問題との対応、変更が必要な箇所、予想する作用、失敗条件を説明する。
ベースライン、強い既存法、異なる原理を無視して複雑な統合案だけで競わせない。

各離れた案を `candidate_roles` に登録する。role=distantには次を付ける。
- `difference`: 前回案と本質的に何が異なるか。
- `falsification`: どの結果なら中心仮説を棄却するか。
- `experiment_id`: dossier.experiments内の試験。
- `command`: 実際に試せるコマンド。必要なコードは通常のproposal.files、実行宣言はproposal.experimentsへ。
- `prerequisites`: データ・依存・予算。未準備の条件は未実行として報告する。

既存の隔離PoCを再利用し、予算内の識別実験を実行する。学習全体が不可能でも、準備条件と次の最小試験を具体化する。
5候補を5つの高コストジョブにする必要はない。1つの共通試験で複数方式を比較できる。
検索8要求、1反復3実験、最大5反復など既存上限を勝手に緩めない。

## dossier.reassessment

`changed_conditions, retained_findings, invalidated_findings, comparability, decision_delta, next_experiment` は具体的な説明文。
`candidate_roles`は全候補を一度ずつ参照し、`candidate_id, role, mechanism`を持つ。前回案のrole=incumbentには、前回選定した実在候補を参照する`previous_candidate_id`も必要。
少数の候補に絞る場合は `comparison_exception` に実質的な理由を記載する。
仮説・文献報告・前回の測定・今回の実測を区別し、履歴を新規のobserved証拠に変換しない。
「新案が勝たない」「前回案を維持する」「保留する」も妥当な結論。手法の優劣と研究の完了、人の採用承認は別。
