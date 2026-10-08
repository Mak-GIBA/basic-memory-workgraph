# 機械可読メタデータと文書正本

独自規約です。SpecKit/ISOがこのJSON形式を定めているわけではありません。
一つの要件・設計・検証等の本文に、ひとつの fenced `upstream` JSONブロックを付けます。
複数項目を同じMarkdownに置けます。IDは一度だけ定義し、他からはlinksで参照します。

例（参考であり実プロジェクトへ自動投入しません）:

    ```upstream
    {
      "id": "APP-FR-001",
      "type": "requirement",
      "system": "APP",
      "title": "有効な入力を受けたら予約情報を保存する",
      "status": "proposed",
      "basis": "proposed",
      "owner": "確認担当の役割",
      "sources": ["要求ヒアリング議事録の該当箇所"],
      "links": {"derives_from": ["APP-US-001"]},
      "acceptance": "対象入力・前提・観測方法・期待結果を具体的に記載する"
    }
    ```

type: goal, stakeholder, need, capability, story, business_rule, requirement,
quality, interface, data, operation, constraint, design, decision, verification,
issue, change, evidence, risk。

status: draft / proposed / approved / retired。
basis: observed(現状の観測) / agreed(合意根拠あり) / proposed(提案) / unknown。
statusとbasisとverification resultは別です。現在動くことを合意とみなさないでください。
approvedにはapproval.by/reference/dateが必要。入力された承認の真偽をツールが認証するわけではありません。

linksは関係名→ID配列:
- derives_from: 下位要求→上位要求/ストーリー/目的/設計判断
- addresses: 関係するニーズ/課題→目的
- belongs_to: ストーリー→機能のまとまり
- satisfies: 設計/設計判断→満たす要件
- verifies: 検証計画→確認する要件/設計/ストーリー/目的
- changes: 不具合/変更要求→対象要件/設計
- depends_on / conflicts_with / supersedes / supports: 明示的な補助関係

verificationにはmethod(test/analysis/inspection/demonstration)、expected、
result(not_run/pass/fail/partial)、result_evidenceを付けます。
計画段階ではresult=not_runのままで正しい。passなら実行ログ等への参照を付けます。

## コマンド
`item --id APP-GOL-001 --type goal --title "..." --apply` で雛形を作成できます。
`--parent APP-GOL-001` は存在する上位項目へderives_fromを追加します。
`--file specs/001-feature/spec.md` で既存仕様へ追記できます（本文は保持、バックアップあり）。
本文作成・承認・リンクの意味上の判断はCodex/人が行ってください。

既存資料を移動しない場合、`register-doc --file docs/existing-design.md --apply`で探索対象に登録します。
メタデータのない文書は本文としては読めますが、機械的な項目間の索引には入りません。

## 検査の意味
`check --phase draft`: ID・型・参照切れなどはerror。要件・設計・検証の不足はwarning。
`check --phase ready`: 計画合意に必要な不足もerror。アプリの稼働判定ではありません。
`trace --write`: 新規は内部の.specify/workbench/trace/index.jsonを更新。旧形式ではindex.json/matrix.mdを更新。手書きファイルは上書きしません。
初期雛形だけならNO_ITEMSとなります。空の文書を合格としないための仕様です。

本文の矛盾・適切な粒度・本当の承認・テスト実行の真偽は機械検査だけでは保証できません。
全プロジェクトのready検査です。並行する未完了の仕様があるとreadyにはなりません。

## Hash-bound approval

`status: approved` だけではreadyとはみなさない。
`$upstream-review`で生成したreview packetに含まれる意味内容ハッシュを、
`$upstream-approve`で `.specify/workbench/approvals.jsonl` へ記録する。
文書中の `approval` には `by/reference/date/review_id/content_hash` を保持する。

ハッシュ対象からは `status`, `approval`, verificationの実行結果 (`result`, `result_evidence`)
を除外する。したがって承認記録そのものやテスト実行結果の追記では承認対象の意味内容は変わらない。
一方、title, basis, sources, links, acceptance, expected等の意味内容を変えると再承認が必要になる。

直接依存先のハッシュも承認イベントへ保存し、上位のGoal/Need/Story/Requirement等が変わった場合は
下流のDesign/Verification等をstaleとして再レビューする。


## 1.2.1: 承認対象の本文と、READYに必要な範囲

- 項目の承認ハッシュは、意味を持つJSONフィールドと、その項目を定義したMarkdownの通常本文（upstreamブロック外）を含む。
- 共通本文の一部分だけを重要仕様と判定する意味解析は行わない。同じ文書の通常本文を変えた場合は、その文書に属する項目をまとめて再レビューする。別文書の項目は、依存リンクによる失効がない限り巻き込まない。
- 上流JSONのstatus/approval/result/result_evidenceだけの更新は、計画の意味内容を変更しない。検証実施の真偽は別途確認する。
- 重要な仕様本文は対象IDを定義した文書へ置く。sourcesで参照した外部ファイル・URLの中身まで、このハッシュで固定されるわけではない。
- レビュー資料には、JSONの全意味フィールドと、承認対象の通常本文を収録する。
- 1.2.0以前の承認・レビューには通常本文の固定がないため、履歴は保持するが現在有効とはみなさない。新しいレビューと明示承認が必要。古い承認を自動的に再付与しない。

### READYの最低限

全作業モードでgoal / need / story / requirements / design / verificationの範囲を確認する。
requirementsはrequirement・quality・interface・data・operation・constraintのいずれか、designはdesign・decisionのいずれか。
既存の対象項目を再利用してよく、タスクごとに新規項目を捏造しない。
ドラフト中の不足は警告、全体READYではエラーになる。承認段階もすべて完了する必要がある。

### need / storyを作らないことが妥当な場合

内部インフラ変更などで新しい利用者ニーズ・操作を作ることが不適切なら、
対象システムの各有効goalに以下の任意フィールドを置き、その目的と省略理由を明示レビューする。

```json
"readiness_exemptions": {
  "need": "既存の品質制約を満たすための内部変更で、追加の利用者要求はない。",
  "story": "利用者の操作は変更しない。既存の操作の互換性は要件と検証計画で扱う。"
}
```

これはgoalのJSONブロック内に置くフィールド例であり、単独のupstreamブロックではない。
`need`と`story`だけが指定可能。具体的理由と有効な合意がなければ省略できない。
目的・要件・設計・検証計画自体の省略には使えない。理由の変更も再承認が必要。
必須文書を別の資料へ統合する場合も、既存の管理対象登録を意図的に調整する。
ファイルを空にしたり、見出し・メタデータだけを残すのは完成として扱わない。

## 3文書と節の承認（2.0.0）

新規の配置はrequirements.md / design.md / verification.md。IDとリンクのスキーマは維持する。
`item`は種別で振り分け、個別ファイルを作らない。`--file`で指定した既存文書への追記も使用できる。節のない既存項目がある文書には従来形式で追記し、同じ文書内の形式を混在させない。

```markdown
<!-- upstream:section APP-FR-001 -->
## APP-FR-001 予約の保存
本文、理由、前提、例外、根拠とupstream JSONをここに置く。
<!-- /upstream:section -->
```

節名は文書内で一意。入れ子・重複・閉じ忘れ、節のある文書で節外に置いた項目はエラー。
節内の通常本文とJSONの意味をhash version 3で固定する。節外の共通条件も各項目へ結び付ける。
節のない旧文書は従来どおり文書全体の本文をhash version 2で固定する。既存の有効な承認はそのまま検査できる。
別の節の変更だけでは失効しない。共通条件の変更は文書内の全項目、上位依存の変更は関連する下位項目に伝播する。
status/approval/result/result_evidenceの除外と、受入条件・expected等の計画項目の固定は維持する。
移行後のIDは変えないが、配置・本文の固定範囲が変わるため明示的な再レビューが必要。台帳と旧スナップショットは書き換えない。
