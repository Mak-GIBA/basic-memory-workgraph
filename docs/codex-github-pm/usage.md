# 使い方

[docs一覧](../README.md) · [概要と収録ツール](README.md) · [導入手順](installation.md)

## 最初の操作

導入後、**管理したいプロジェクトのディレクトリで新しいCodexセッションを開始**します。
インストーラーのリポジトリが管理対象とは限りません。
以下の`text`ブロックはCodexの会話欄へ入力します。Skill名はターミナルのコマンドではありません。

```text
$github-project-director
このプロジェクトのIssue構成を見直して。要件・実装・既存Issueを確認し、
抜け、重複、大きすぎるIssueとその改善案を示して。まず提案だけ。
```

Skill名の後ろ、または次の行に依頼を書きます。通常の自然言語からの選択も有効ですが、
明示したい場合は`$github-project-director`を使ってください。
対象が曖昧ならリポジトリやProjectのURLを添えます。

## 調査から反映まで

1. README・要件・コード・テストと、既存のIssue・PR・Projectsを確認します。
2. 根拠と取得範囲を示し、作成・分割・更新の案、完了条件、未確定事項を提示します。
3. 利用者が対象と変更内容を確認し、反映する範囲を指示します。
4. 承認済みの内容をCLIまたは利用可能なGitHub MCPで反映し、再取得して結果とURLを確認します。

既に具体的な対象・内容の反映が承認されていれば、同じ承認を繰り返す手順ではありません。
Skillの呼び出しだけで一括変更が承認されたことにはなりません。
状態が提案時から変わっていれば差分を確認し、部分的に失敗したときは成功分と未反映分を分けて報告します。

## 用途別の依頼例

### 要件からタスクを作る

```text
$github-project-director
このプロジェクトの事業目的・ユーザーストーリー・要件を読み、既存Issueと重複しない
タスク案を作って。各案に目的、作業範囲、完了条件、根拠を付けて。まず提案だけ。
```

要件と実装・既存Issueの対応を確認し、利用者の成果として検証できる単位を提案します。
ファイルごとの機械的な分割や、すべての作業への親Issue作成を前提にしません。
技術的な保守作業に架空のユーザーストーリーを付けることも求めません。

### 担当・期限・優先度を計画する

```text
$github-project-director
今後2週間の作業案を作って。既存Projectの項目と依存関係を確認し、
優先順・担当候補・期限案・未確認の稼働条件を整理して。反映前に変更案を見せて。
```

日付・タイムゾーン・稼働条件を確認し、Projectの既存フィールドを使って計画します。
Issueの親子関係と着手の前提となる依存関係は区別します。
このSkillではIssueごとの期限をProjectの日付フィールドで扱う方針です。
マイルストーンの期限を個別Issueの期限として代用する計画にはしません。

### 定例Issueに進捗を記録する

次の`#42`は例です。実際の記録先Issue番号またはURLへ置き換えてください。

```text
$github-project-director
定例Issue #42へ今回の進捗を追記したい。関連Issue・PRを確認し、短い概要、主な更新、
決定事項、次のアクション、必要な保留事項をまとめて。担当や期限は変更せず、
投稿するコメント案を先に見せて。
```

同じ定例Issueへ、実施日ごとに新しいコメントを追記する手順です。
変更フィールドの羅列ではなく、チームメンバーが成果・理由・次の行動を理解できる文章を目指します。
過去の本文・コメントを置き換えず、記録だけの依頼で担当や状態を変更しません。
投稿前には過去コメントと同じ処理の目印を確認し、通信失敗時の重複投稿を避けます。
この確認は同時投稿まで防ぐ仕組みではありません。

## 読み取り補助スクリプト

Codexが調査で使う`github_inspect.py`は、ターミナルからも実行できます。
Python 3.10以上と、対象へアクセスできる認証済みの`gh`が必要です。
以下は既定の導入先を使う例です。`OWNER/REPO`、`OWNER`、Project番号、Issue番号を実際の値に置き換えます。

```bash
python3 ~/.agents/skills/github-project-director/scripts/github_inspect.py snapshot --repo OWNER/REPO
python3 ~/.agents/skills/github-project-director/scripts/github_inspect.py project --owner OWNER --owner-type user --number 1
python3 ~/.agents/skills/github-project-director/scripts/github_inspect.py relations --repo OWNER/REPO --issue 42
python3 ~/.agents/skills/github-project-director/scripts/github_inspect.py meeting --repo OWNER/REPO --issue 42
```

組織のProjectでは`--owner-type organization`にします。ホストや取得上限を指定する場合、
`--hostname HOST --max-pages N`は`project`等のサブコマンドより前に置きます。
定例コメントの再試行を調べる`meeting --entry-key KEY`も利用できます。

この補助スクリプトは読み取り専用で、結果を標準出力へ返します。
一覧の`complete`・`pages`・`error`を確認し、途中までの取得や権限不足を「該当なし」と扱わないでください。
`snapshot`で得るProjectはリポジトリにリンクされたものです。必要なProjectは個別に指定して確認します。

## 成果物の保存先

| 場所 | 内容・作成タイミング |
|---|---|
| Codexの会話 | 調査結果、Issue案、計画、反映前の確認内容 |
| GitHub Issues／Projects | 承認後に反映したタスク、親子・依存関係、担当や計画の値 |
| 指定した定例Issueのコメント | 記録内容を承認し、投稿したときの進捗報告 |
| ターミナルの標準出力 | 読み取り補助スクリプトの結果。自動でリポジトリへ保存しない |

計画や結果をローカルにも保存したい場合は、保存先と対象を依頼に含めます。
別の台帳DBや定期実行ジョブ、毎回のスナップショットは自動作成しません。

## 利用範囲と次の作業

SkillはCodexへの作業手順で、アクセス制御や常に正しい文章・判断を保証するものではありません。
内蔵テストも実モデルの文章品質や実GitHubへの反映成功を証明するものではありません。
取得できなかった範囲と提案の前提を確認してください。

本番デプロイ、PRのマージ、Issueの削除・転送、管理権限の変更はこのSkillの対象外です。
GitHubへ接続できない場合はローカル資料による暫定分析となり、リモート状態や反映成功を推測しません。
認証・権限・導入の問題は[導入手順](installation.md)を参照してください。
