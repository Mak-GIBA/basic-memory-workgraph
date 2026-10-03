# ECCを必要なときに読む

ECCの原本をCodex標準プラグインのキャッシュに残し、初期スキル一覧には短い入口4件だけを載せます。
Python 3.11以降、Linux / WSL2、導入済みのCodexとネイティブECCプラグインが必要です。

ECC自体が未導入の場合は、[ECCのインストーラー](codex-ecc/installation.md)で原本の導入とこの設定をまとめて行えます。

## 導入と確認

リポジトリのルートから実行します。

```bash
python3 tools/ecc-on-demand/ecc_on_demand.py apply
python3 tools/ecc-on-demand/ecc_on_demand.py doctor
```

`apply` は、Codexのユーザー設定で `plugins."ecc@ecc".enabled = false` にし、
`~/.agents/skills/` に `ecc-python`、`ecc-errors`、`ecc-security`、`ecc-library` を配置します。
管理CLIは `${CODEX_HOME:-~/.codex}/ecc-on-demand/ecc_on_demand.py` に配置します。
設定のバックアップと管理状態も同じディレクトリに保存します。バックアップの権限は所有者のみ読み書き可能です。
ECCの原本、Basic Memory、独立したMCP、スキル一覧の上限は変更しません。

`--codex-home PATH`、`--skills-root PATH`、`--cwd PATH` はサブコマンドの前に指定できます。
同名の未管理スキルや、導入後に手で変更した管理ファイルがある場合は上書きせず停止します。
既存TOMLのコメントと他の設定を保持します。ECC設定がインラインテーブルやドット区切りのキーで書かれている場合は自動編集しません。
通常の`[plugins."ecc@ecc"]`テーブルに整理してから適用してください。

反映は新しいセッションで確認してください。実行中の共有Codexデーモンは再起動しません。

## 使用する入口

| 入口 | 取得する原本 |
|---|---|
| `ecc-python` | `python-patterns` |
| `ecc-errors` | `error-handling` |
| `ecc-security` | `security-review` |
| `ecc-library` | 依頼に合う専門スキルを最大5件検索し、必要な1〜3件を読む |

入口は自動選択も有効です。明示する場合は `$ecc-library` などと指定します。
React・Cloudflare・GitHub・記憶管理は既存の専門スキルを優先します。
ECC本文のTDDやデプロイ方針より、現在のユーザー・開発者・プロジェクトの指示が優先されます。

```bash
python3 tools/ecc-on-demand/ecc_on_demand.py search 'Python テスト' --json
python3 tools/ecc-on-demand/ecc_on_demand.py search 'DB マイグレーション' --json
python3 tools/ecc-on-demand/ecc_on_demand.py resolve api-design --json
```

`resolve` は本文のパス、スキルのディレクトリ、プラグインのルート、バージョンを返します。
相対参照は原本の位置から解決します。原本がない場合はエラーを返し、別キャッシュへ推測で切り替えません。
検索は名前・説明と現在の作業ディレクトリのPython / TypeScript / JavaScript構成を使う軽量な順位付けです。
文意全体を理解する検索ではないため、候補が合わない場合は英語の技術名で検索するか、名前を指定してください。

原本の一覧は、ECCをそのプロセス内だけで有効にした独立した `codex app-server --stdio` の
`skills/list` から毎回取得します。会話、モデル呼び出し、SessionStartフックは開始しません。
初期一覧が減っても、選んだ本文を読む分のコンテキストは消費します。

## 更新と復元

```bash
python3 tools/ecc-on-demand/ecc_on_demand.py update
python3 tools/ecc-on-demand/ecc_on_demand.py restore
```

`update` は `codex plugin marketplace upgrade ecc --json` と `codex plugin add ecc@ecc --json` を使います。
更新が途中で失敗した場合もECCの有効設定を `false` に戻し、診断結果を返します。
更新後にCodexからフックの信頼確認が要求されることがあります。本ツールはフックを自動承認しません。
原本は新しいネイティブカタログから解決するため、入口のバージョン固定パスを書き換える必要はありません。
入口や管理CLI自体の更新には、新しいリポジトリのコピーから`apply`を実行します。
ECC原本と管理資材をまとめて更新する場合は、ルートの`install_codex_ecc.sh --update --apply`を使います。

`configure-ecc` や直接の `codex plugin add` はECCを再有効化する場合があります。
`doctor` が再有効化を検出したら `apply` で戻してください。

`restore` は導入前のECCの有効値に戻し、管理対象の入口とCLIを取り除きます。
新しいECCインストーラーでECC自体を初めて導入した環境では、原本を残し、ECCを無効状態に保ちます。
導入後に追加した無関係な設定は保持し、設定バックアップも残します。
管理ファイルや有効値が手で変更されている場合は、その変更を消さず停止します。

## 停止する機能

ECCプラグインを無効化すると、付属スキルの一覧登録、付属Chrome DevTools MCP、
ECCのCodex用SessionStartフックが止まります。独立して設定したMCPは継続します。

ECC 2.2.2のSessionStartは、前回要約、instinct、学習済みスキルの紹介、技術構成を注入し、
ECCの保存領域を作成します。また、既定では30日を超えたECC要約を削除し、条件付きでobserverのセッション登録を行います。
無効化後はこれらの開始時処理が止まりますが、保存データは削除しません。
Basic Memoryのフック、Codexの会話履歴、Claude Code側のECC設定は別です。

`doctor` は新しい独立app-serverのカタログを確認します。モデルに渡される一覧が省略されていないかは、
新規セッションの診断ログでも確認してください。実行中のセッションの一覧は置き換えません。

## 検証

```bash
python3 -m unittest discover -s tests -p 'test_ecc_on_demand.py' -v
```

テストは隔離した設定と原本を使い、再適用、衝突、復元、更新成功・失敗、欠損、検索、RPCの取得を確認します。
実際のECC更新やユーザーの設定変更は行いません。
