# ECCの入口を使う

[概要](README.md) · [導入手順](installation.md)

## 最初の操作

導入後、新しいCodexセッションを開きます。入口は通常の自動選択も有効です。
特定の入口を使いたい場合は、Codexの会話で次のように指定します。

```text
$ecc-python このプロジェクトのPython実装を確認し、型と例外処理を整理してください。
$ecc-errors 外部APIの再試行を、失敗時の復旧と二重実行の防止を考慮して設計してください。
$ecc-security 認証処理の変更について、秘密情報と権限確認の扱いをレビューしてください。
$ecc-library このプロジェクトのDBマイグレーションに合う原本を選んで、移行手順を検討してください。
```

## 入口と原本

| 入口 | 用途・取得する原本 |
|---|---|
| `ecc-python` | Python実装の `python-patterns` |
| `ecc-errors` | 失敗処理・再試行の `error-handling` |
| `ecc-security` | 認証・秘密情報・安全性レビューの `security-review` |
| `ecc-library` | API・テスト・DB・Docker等の専門スキルを検索 |

ライブラリでは候補を最大5件に絞り、最初は該当する原本1〜3件を読みます。
原本が相対パスで別の資材を参照する場合は、原本の場所を基準に必要なものだけを取得します。
React・Cloudflare・GitHub・記憶管理は既存の専門スキルを優先します。
ユーザー、開発者、プロジェクトの現在の指示がECC原本より優先されます。

## ターミナルから調べる

リポジトリのルートから、検索と原本取得を実行できます。

```bash
python3 tools/ecc-on-demand/ecc_on_demand.py search 'Python テスト' --json
python3 tools/ecc-on-demand/ecc_on_demand.py search 'DB マイグレーション' --json
python3 tools/ecc-on-demand/ecc_on_demand.py resolve api-design --json
bash install_codex_ecc.sh --doctor
```

検索は名前・説明と一部のプロジェクト構成を使います。候補が合わない場合は、英語の技術名や原本の名前で絞ってください。
`resolve` は本文のパス、スキルのディレクトリ、プラグインのルートと版を返します。本文全体は出力しません。
リポジトリ外では、導入された管理CLIを利用できます。詳細は[管理CLIのガイド](../ecc-on-demand.md)を参照してください。

## 保存先と利用範囲

管理CLIと復元情報はCodex設定先の `ecc-on-demand/`、入口はユーザー用のスキル配置先に保存します。
ECC原本はCodexのプラグインキャッシュにあります。原本の場所は毎回Codexのカタログから取得するため、更新後も新しい原本を参照します。

入口の利用は、ECCの再有効化・更新・インストールを自動実行する指示ではありません。
ECCの付属SessionStartフックによる、前回要約・instinct・学習済みスキルの自動読み込みは停止します。
Basic MemoryとCodexの会話再開は別の仕組みです。

導入や更新のエラーは[導入手順の「困ったとき」](installation.md#困ったとき)で確認してください。
