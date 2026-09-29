# SpecKit Upstream：使い方

[概要と収録ツール](README.md) · [導入手順](installation.md) · [docs一覧](../README.md)

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

## 文書を作成・検査する

Codexと目的や不明点を確認し、雛形へ根拠のある内容を記載します。
以下のターミナルコマンドは、このインストーラーのリポジトリではなく、**attachしたアプリのルート**で実行します。

```bash
# 配置・CLI起動・プロジェクト設定を確認
speckit-workbench doctor --project .

# ドラフト文書の構造検査
speckit-workbench check --project . --phase draft

# 要件等の対応表・索引を生成して保存
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

## 成果物の保存先

| 場所 | 内容 |
|---|---|
| `docs/upstream/` | 目的、関係者、要求、設計、As-Is、検証計画等の正本Markdown |
| `docs/upstream/traceability/` | traceが生成する対応表・索引 |
| `docs/upstream/governance/reviews/` | reviewで保存するレビュー対象と内容 |
| `docs/upstream/governance/approvals.md` | 承認状態の要約 |
| `specs/<feature>/` | SpecKitで個別機能の作業を進める際の仕様・plan・tasks |
| `.specify/workbench.json` | system ID、文書の登録・探索先、承認profile |
| `.specify/workbench/approvals.jsonl` | 承認・撤回の台帳 |
| `.specify/workbench/gate-ready.json` | gateで記録する対象ファイルのハッシュと検査結果 |
| `.agents/skills/speckit-*/` | 新規の公式統合で配置するプロジェクト用Skill |

`specs/<feature>/`の具体的な内容やレビュー記録は、対応する作業・コマンドで作成します。
attachだけですべての成果物が完成するわけではありません。
`--docs-dir`を変更した場合、上流文書の保存先は設定値に従います。

項目のJSON形式や追跡ルールの詳細は、導入済み資材の`assets/references/TRACE_FORMAT.md`、
文書運用は`METHOD.md`を参照してください。[資料の配置・展開方法](installation.md)
