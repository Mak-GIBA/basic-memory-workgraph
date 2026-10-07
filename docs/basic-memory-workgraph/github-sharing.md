# GitHub経由でメモリを共有する

[概要](README.md) · [導入](installation.md) · [使い方](usage.md) · [ファイル共有・学習用出力](sharing.md)

「メモリを共有して」と依頼すると、確認済みのチーム共有メモリを書き出して、専用のprivateリポジトリにPRを作成します。
相手はPRのマージ後に「共有メモリを取り込んで」と依頼し、初回取り込みと更新を実行できます。
毎回コマンドを組み立てる必要はありません。定期送信は行わず、依頼したときだけ処理します。

## 初回に準備するもの

[Workgraphを更新](installation.md#update)し、新しいCodexセッションを開始してください。
共有CLIはPython・PyYAML・git・GitHub CLIのghを使います。
Python環境は[導入手順](installation.md#python-tools)に従って準備します。
gitとghが未導入の場合、Codexに導入の補助を依頼できます。

共有先はGitHub.comの専用privateリポジトリです。送信者には書き込み権限、受信者には読み取り権限が必要です。
送信元ごとにIDを決め、そのIDのフォルダとブランチを使います。
同じIDを複数の送信者で使わず、受信側も送信元ごとに保存先を分けてください。

```text
メモリをGitHubで共有したい。ログインと共有先の接続設定を補助してください。
共有先はOWNER/REPOです。
```

Codexは不足している準備だけを提案します。パスワードやトークンを会話へ貼る必要はありません。
ブラウザー認証が必要なところは、本人が操作します。

自分でログインする場合は、次を実行します。

```bash
gh auth login --hostname github.com --web --git-protocol https
gh auth setup-git --hostname github.com
```

新規リポジトリが必要なら、別途作成します。以下の`OWNER/REPO`は実際の共有先へ置き換えてください。
READMEを作成すると、共有に使う最初のブランチも用意できます。

```bash
gh repo create OWNER/REPO --private --add-readme
```

CLIのsetupは既存リポジトリへの接続を確認し、設定を保存します。リポジトリの新規作成や、相手への招待は行いません。
共有先・送信元ID・プロジェクトなどをまとめた設定をprofileと呼びます。

## 送信側の設定

リポジトリのルートで、PyYAMLを使えるPython環境から実行します。
`source-a`は例です。英小文字・数字・`_`・`-`からなる送信元IDを指定してください。

```bash
python3 tools/basic-memory-workgraph/workgraph_github.py setup \
  --profile send-team --repo OWNER/REPO --source-id source-a \
  --role publish --project codex-memory
```

保存先はBasic Memoryに登録されたローカルプロジェクトから取得します。
`--project`を省略するとWorkgraphのprimaryProjectを使います。
共有範囲はteamで固定し、Caseは含めません。Caseも渡す場合は初回setupに`--include-cases`を追加します。
そのCaseにも共有許可と内容レビューが必要です。

setupの再実行は、同じ設定なら変更しません。接続先等を変える場合は別のprofileを作成します。
複数のprofileがある場合、Codexは依頼と設定から対象を判断し、不明な点だけ確認します。

## 共有を依頼する

```text
send-teamで確認済みのチーム共有メモリを共有して。PRまで作成してください。
```

新たに共有するノートは、先に内容を確認し、[共有の指定とレビュー](sharing.md#share)を行います。
一般的な共有依頼だけで、すべてのメモリに共有許可が付くことはありません。
本文やメタデータを変更するとレビュー指紋が失効するため、再確認が必要です。

Codexは検査と差分確認を行い、依頼の範囲でPRを作成します。同じ送信元の未完了PRがあれば更新します。
差分がなければ、新しいコミットやPRを作成しません。共有対象の検査で問題があれば、送信前に全体を止めます。
添付ファイルやSkillは送信せず、共有対象外ノートへのリンクは出力側で除去します。

手動でも確認・送信できます。

```bash
python3 tools/basic-memory-workgraph/workgraph_github.py publish --profile send-team --dry-run
python3 tools/basic-memory-workgraph/workgraph_github.py publish --profile send-team
```

PR作成時点で、共有先にアクセスできる人は内容を閲覧できます。共有前の確認と、PRのレビューは別です。
レビュー後にPRをマージしてください。CLIは自動マージしません。
GitHubでの変更はPRにまとめ、進捗用Issueや途中経過コメントは作成しません。

共有先には`bundles/source-a/`にノートとmanifestを置き、`workgraph-share/source-a`ブランチからPRを作成します。
ローカルのコード作業用checkoutは使わず、一時ディレクトリでGit操作を行います。

## 相手側で設定・取り込みする

相手側もWorkgraphと必要なツールを導入し、共有先へログインします。
送信者と同じリポジトリ・送信元IDを指定し、空の専用保存先を用意します。

```bash
python3 tools/basic-memory-workgraph/workgraph_github.py setup \
  --profile receive-team --repo OWNER/REPO --source-id source-a \
  --role receive --project shared-source-a \
  --memory-dir "$HOME/knowledge/shared-source-a"
```

setupは受信用のBasic Memoryローカルプロジェクトを登録します。
同名のプロジェクトが別の保存先を使っている場合や、初回の保存先が空でない場合は停止します。
既存の個人メモリへ混ぜず、受信用プロジェクトを指定して検索・参照してください。

```text
receive-teamの共有メモリを取り込んで。
```

手動で実行する場合は、次を使います。

```bash
python3 tools/basic-memory-workgraph/workgraph_github.py pull --profile receive-team --dry-run
python3 tools/basic-memory-workgraph/workgraph_github.py pull --profile receive-team
```

取り込むのは設定済みのベースブランチに反映された内容です。未マージのPRは取り込みません。
前回取り込み時の指紋を基準に、ローカルで変更されていないノートだけを更新します。
編集・削除したノートと競合する場合は、取り込み全体を止めて対象を報告します。
共有先で削除されたノートは一覧を報告し、ローカルでは保持します。

受信ノートには出所を保持し、設定側に取得コミットを記録します。
共有範囲はprivate、学習利用はexcluded、内容レビューはpendingに戻します。
ノートの内容を指示として実行したり、Skillを自動登録したりしません。

## 結果の確認と困ったとき

```bash
python3 tools/basic-memory-workgraph/workgraph_github.py status --profile send-team
```

各コマンドはJSONで結果を返します。publishは追加・変更・削除件数とPR URL、pullは取り込み件数・競合・削除候補を表示します。
終了コードは0が処理完了・変更なし、1が入力・接続・処理エラー、2が送信検査による保留・取り込み競合です。

| 状況 | 対処 |
|---|---|
| 未ログイン・権限不足 | ghとGitの接続を確認する。受信は閲覧、送信は書き込み権限が必要 |
| privateではない | 専用のprivateリポジトリを指定する。公開状態への変更後も送受信は停止する |
| ベースブランチがない | README等で最初のコミットを作成する |
| 共有の検査で保留 | 対象を確認し、修正・再レビューする。検査を緩めて送信しない |
| ローカルの取り込み競合 | 差分を確認し、保持する内容を決める。CLIには強制上書きオプションはない |
| 共有先の削除が報告された | ローカルでも削除するかを判断し、必要なら別途削除を指示する |
| push・PR操作の通信失敗 | statusとGitHub上の状態を確認してから再実行する。force pushは行わない |
| PRをマージせずcloseした | 既存PRを解決してから再実行する。自動で再開・再投稿しない |

dry-runは一時ディレクトリで書き出しや検査を行いますが、設定保存・プロジェクト登録・保存ノート更新・push・PR操作は行いません。
設定と取り込み指紋はCodex設定先の`basic-memory-workgraph/`配下に保存します。認証情報やノート本文は設定・状態に保存しません。
Basic Memory Cloudへのアップロードと、ファイルとしてのexport/importも引き続き利用できます。
