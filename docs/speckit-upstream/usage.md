# SpecKit Upstream：使い方

[概要と収録ツール](README.md) · [導入手順](installation.md) · [既存要件・設計の見直し](reassessment.md) · [docs一覧](../README.md)

## 最初の操作

グローバル導入後、対象アプリのフォルダーでCodexを開きます。
新規開発なら`$upstream-new`、既存アプリなら`$upstream-existing`から開始します。
プロジェクトの準備がまだなら、Skillが[attachによる準備](installation.md)を案内します。

以下はCodexの会話欄への入力例です。

```text
$upstream-new 店舗スタッフ向けの予約管理アプリを作りたいです。
今日の予約と未対応の予約を把握し、予約の変更・取り消しを行えるようにしたいです。
目的、必要な機能、画面、検証計画を整理してください。
```

既存アプリの場合の例です。

```text
$upstream-existing このリポジトリの予約管理機能を整理してください。
実装から分かる現状、合意済みと確認できる仕様、改善案を分けてください。
```

これらは上流文書を整える依頼です。アプリ実装の開始は別途指示します。

## 8つのコマンド

| Codexへの入力 | 用途・成果 |
|---|---|
| `$upstream-new 作りたいもの` | 目的、要求、ストーリー、仕様・設計、検証計画 |
| `$upstream-existing` | As-Is（現状）、合意済み仕様、To-Be（目指す状態）の整理 |
| `$upstream-change 変更内容` | 変更理由、対象要件、設計・検証への影響 |
| `$upstream-bug 症状` | 期待挙動、再現条件、対象要件、修正方針と回帰検証計画 |
| `$upstream-refactor 対象` | 維持する挙動、品質改善の目的、設計変更・移行の計画 |
| `$upstream-check` | 上流文書の内容レビューとCLIによる構造検査 |
| `$upstream-review` | 次の承認段階の対象を固定したreview packet |
| `$upstream-approve` | 明示されたreviewと項目IDについての承認記録 |

これらは明示呼び出し専用の独自Skillです。公式の`$speckit-*`とは名前が異なります。
`$upstream-bug`も診断・上流整理の入口であり、自動修正を許可する指示ではありません。
コマンド一覧はターミナルの`speckit-workbench commands`でも確認できます。

## 既存要件・設計を見直す

現状の整理は`$upstream-existing`、要件の妥当性・曖昧さ・評価方法の点検は`$upstream-check`から始めます。
処理結果・受入条件・品質契約を変更する改善は`$upstream-change`、外部挙動を保つ内部設計の改善は`$upstream-refactor`へ進めます。

Workbench 2.0.1のSkillには、方式の有効性・評価方法・精度改善について、判断を左右する不確実性がある場合にDesign Researchを使う手順があります。
使用理由と`research/audit`を明示し、導入済みのハーネスを実行します。
単純な文書修正には研究を一律要求せず、未導入・旧版・実行不能では必要な研究を未実行として残します。
Design Researchを自動導入したり、アプリを自動修正したりする手順は含めていません。

[ユースケース別ガイド](reassessment.md)に、7つの場面の判断基準、Codex入力例、成果物、仕様への反映先をまとめています。

```text
$upstream-change 検索の精度を改善するため、現行方式と品質要件を見直して。
Design Researchのresearchを明示して実行し、現行案を含む候補を同じ評価条件で比較して。
必要な小さなPoCの結果を品質要件・設計判断・検証計画の変更案へ戻して。
アプリ実装はまだ変更しないで。
```

## 文書を作成・検査する

Codexと目的や不明点を確認し、雛形へ根拠のある内容を記載します。
以下のターミナルコマンドは、このインストーラーのリポジトリではなく、**attachしたアプリのルート**で実行します。

```bash
# 配置・CLI起動・プロジェクト設定を確認
speckit-workbench doctor --project .

# ドラフト文書の構造検査
speckit-workbench check --project . --phase draft

# 要件等の対応索引を内部に保存
speckit-workbench trace --project . --write
```

`check`は読み取り専用、`trace --write`は生成文書を書き込みます。
検査の合格だけで文書の意味や実装の正しさが確認されたわけではありません。

## レビューと承認を記録する

1. `$upstream-review`を呼び、review ID、対象項目ID、内容、未決事項を確認します。
2. 承認する項目IDを明示し、修正が必要なら先に文書を直します。
3. その明示承認を`$upstream-approve`で記録します。
4. 次の承認段階についても同じ流れを繰り返します。

手動で行う場合、まず未承認項目を確認し、レビュー対象を保存します。

```bash
speckit-workbench approval-plan --project .
speckit-workbench review --project . --checkpoint next --write
```

出力されたreview IDと実在する項目IDを使います。次の値は例なのでそのままでは実行できません。
`--by`には承認者、`--reference`には実際の承認根拠を記載します。

```bash
# 承認予定だけを確認する
speckit-workbench approve --project . \
  --review rev-YYYYMMDDTHHMMSSZ-xxxxxxxxxx --id APP-FR-001 \
  --by "user" --reference "確認済みの明示承認の参照"
```

実際の明示承認があり、対象を確認できた場合だけ、同じコマンドへ`--apply`を付けて記録します。
レビュー対象の保存だけでは承認されず、承認者名を書くだけで本人認証されるわけでもありません。

承認時には項目内容、同じ文書の通常Markdown本文、直接依存先のハッシュを記録します。
関連内容が変わると`STALE_APPROVAL`や`STALE_DEPENDENCY_APPROVAL`になり、再レビューが必要です。
誤承認や撤回は`revoke-approval`で記録できます。

```bash
# まず予定を確認し、記録する場合は --apply を追加
speckit-workbench revoke-approval --project . --id APP-FR-001 \
  --by "user" --reference "承認撤回の根拠"
```

### 承認段階の選択

attach時の既定は`normal`です。変更時は`approval-profile --set`を使い、適用には`--apply`を付けます。

| profile | 段階 |
|---|---|
| `small` | scope → solution |
| `normal` | intent → requirements → solution |
| `critical` | purpose → stories → requirements → design → verification |

```bash
speckit-workbench approval-profile --project .
speckit-workbench approval-profile --project . --set critical
```

## 実装前の文書状態を確認する

```bash
# 現時点の構造検査だけ
speckit-workbench gate --project .

# 合格状態の文書・設定のハッシュを記録
speckit-workbench gate --project . --write

# 記録後に対象が変わっていないか確認
speckit-workbench gate --project . --verify
```

gateは必要な上流項目、要求・設計・検証計画、選択した承認段階の完了等を確認します。
Goalだけの状態や、必須文書が空・見出しだけの状態ではREADYになりません。
検証**計画**が整っていれば、テスト結果が`not_run`でも許されます。アプリのテスト合格を示すものではありません。

`check`・`gate`は検査失敗時に非ゼロで終了します。CIやマージ条件への接続は自動では行いません。
`gate --verify`は古い記録の利用を検出しますが、同じユーザーによる改ざんを防ぐ権限制御ではありません。

<a id="成果物の保存先"></a>

## 成果物の保存先と確認先

新規の正本は次の3文書と、必要な研究報告です。`--docs-dir`を指定した場合は設定値に従います。

| 確認したいこと | 正本 | 主な内容 |
|---|---|---|
| 何を作る・維持するか | `docs/upstream/requirements.md` | 目的・利用者・範囲、機能・品質・制約、現状と期待、不明点 |
| どう実現するか | `docs/upstream/design.md` | 構成・動作・データ・API・運用、選定理由と変更影響 |
| どこまで確認できたか | `docs/upstream/verification.md` | 受入条件、確認方法、実際の結果、未実行、証拠 |
| 研究・実測から何が分かったか | `docs/design-research/<slug>/report.md` | 結論、比較、検証、変更前後、残る確認。実行した場合のみ |

内部のレビュー・承認要約・索引は`.specify/workbench/`に、ResearchのJSONは`.internal/`に保存します。
ユーザーが通常確認するのは、主資料の該当する節と結論です。承認待ちでは対象IDと固定済みreview packetへのリンク1つを加えます。
公式の`specs/<feature>/spec.md`・`plan.md`・`tasks.md`は必要な機能詳細として参照します。
文書の内容は固有の`<!-- upstream:section ID -->`と`<!-- /upstream:section -->`で囲みます。
節を編集した場合はその節、節外の共通条件を編集した場合は文書全体、上位依存を変更した場合は関連下位の再確認が必要です。
節のない旧文書は文書全体を固定します。有効な旧承認を更新だけで失効させません。

## 既存資料を3文書へ移行する

```bash
# 本文・移動元・リンク変更・再レビュー対象・バックアップ先を確認。まだ書き込まない
speckit-workbench migrate --project .
# 確認した統合を適用
speckit-workbench migrate --project . --apply
# 自分で作った追加の上流資料も統合する場合だけ明示する
speckit-workbench migrate --project . --include-doc docs/upstream/custom.md --apply
```

標準の旧19文書と旧CLIの既定itemファイルを統合します。混在した種別を持つ旧文書は、本文の適用範囲を保つため一つの節として移します。
公式SpecKit資料とユーザー独自の追加文書は保持します。保持する文書から移動元へのリンクがある場合、先にリンクを直すか追加文書を明示して移行します。
元の文章・設定は`.specify/workbench/migrations/`にバックアップし、ID・出典・証拠・承認履歴を残します。
配置と本文の固定範囲が変わる項目は再レビューが必要です。過去の承認を自動で付け直しません。
重複ID・壊れた記録・リンクの解決不能・統合先の競合では停止し、途中の適用に失敗した場合は文書と設定を戻します。
適用済みの再実行は変更しません。Researchの移行方法は[Researchの使い方](../design-research/usage.md#既存資料を1報告書へ移行する)にあります。
