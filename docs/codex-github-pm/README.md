# GitHub Project Director

[docs一覧](../README.md) · [導入手順](installation.md) · [使い方](usage.md)

GitHubのIssue・PR・Projectsとローカルの要件・実装を読み、プロジェクト全体のタスクを整理するためのSkillです。
要件からのIssue案、作業の分割、担当・期限・優先度の計画、定例Issueへの進捗記録をCodexに依頼できます。

対象は[install_codex_github_pm.sh](../../install_codex_github_pm.sh)です。
独自資材を内蔵した単一ファイルで、リポジトリの補助コードを一緒に配置する必要はありません。
このガイドは埋め込み実装・資料のv1.1.0を基準にしています。

## 導入するツールと役割

| ツール・資材 | 形式・提供元 | 用途 | 導入条件 |
|---|---|---|---|
| `github-project-director` | このスクリプト独自のCodex Skill | 現状調査、タスク案、変更内容の確認、反映後の検証という作業手順 | 標準 |
| `github_inspect.py` | Skill内の独自Pythonスクリプト | Issue・PR・Project・依存関係・定例コメントの読み取り。取得範囲やエラーも表示 | 標準 |
| 操作・計画の参照資料、`agents/openai.yaml` | Skill内の独自資材 | GitHub操作と進捗記録の手順、Codex向けの表示設定 | 標準 |
| GitHub CLI（`gh`） | GitHub公式CLI | GitHubの読み取り・書き込み。補助スクリプトも利用する | 既存を再利用。不足時の導入は`--install-gh`指定時のみ |

**GitHub Project Director自体はGitHub・OpenAI・ECCの公式配布物ではありません。**
判断の手順をSkillが提供し、操作には公式CLIまたは利用可能な既存GitHub MCPを使います。
GitHub MCPの追加や認証設定はインストーラーに含まれません。
GitHub CLIにはProjectsを扱うコマンドがあります。[公式CLI資料](https://cli.github.com/manual/gh_project)

## どのような場面で使うか

- 事業目的・ユーザーストーリー・要件から、既存Issueと重複しない作業案を作りたい。
- Issueが大きすぎる、完了条件が不明、実装済みの作業が残っているなどの問題を整理したい。
- 親子関係と依存関係を確認し、今後2週間の担当・優先度・期限を計画したい。
- 同じ定例Issueに、成果・決定事項・次のアクション・保留事項を読みやすく追記したい。

タスクの状態はGitHub Issues／Projectsを正本とします。別の管理DBやバックグラウンドの定期実行は導入しません。
Basic Memory、ECC、SpecKitは必須ではありません。既存のSpecKit文書があれば、要件の根拠として参照できます。

## 読む順序

1. [導入手順](installation.md)でSkillを配置し、利用するGitHub接続を確認する。
2. 新しいCodexセッションで、[使い方](usage.md)の「まず提案だけ」の例を試す。

## 参照資料

インストール後のSkill内に`SKILL.md`、`references/native-operations.md`、
`references/planning-and-meetings.md`があります。導入前の確認にはインストーラーの`--extract`を使えます。
展開方法は[導入手順](installation.md)に記載しています。

外部CLIの説明は[Projects](https://cli.github.com/manual/gh_project)と
[認証状態の確認](https://cli.github.com/manual/gh_auth_status)の公式資料を2026-09-30に確認しました。
利用環境でのコマンド・権限の確認方法も導入手順に掲載しています。
