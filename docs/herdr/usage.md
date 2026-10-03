# ディレクトリに対応するHerdrを開く

[概要](README.md) · [導入手順](installation.md)

## 日常の操作

設定を反映したBashで、作業対象へ移動してから実行します。

```bash
cd /path/to/project
herdr
```

`/path/to/project`は実際のプロジェクトに置き換えてください。
引数なしの`herdr`は、必要な場合だけサーバーを起動し、現在のディレクトリのworkspaceを選びます。
既存workspaceがなければ、そのディレクトリを指定して作成します。
Herdr内から実行した場合は既存UIを切り替え、クライアントを重ねて起動しません。

ディレクトリを直接指定する場合と、本来のCLIを使う場合は次のように分かれます。

```bash
herdr-open /path/to/project
herdr --version
herdr workspace list
```

`herdr`に引数がある場合は本来のバイナリへ渡します。
`herdr-open`は対話ターミナルが必要です。自動化処理からUIを開く用途には使いません。

## workspaceの照合

選択したセッションの`session.json`と稼働中のworkspace一覧を照合します。
最初に確認したworkspaceと実パスの対応は、セッションディレクトリの`herdr-open-workspaces.json`に保存します。
元の`session.json`には書き込みません。
同じラベルがあるだけでworkspaceを再利用したり、別のディレクトリ用に切り替えたりはしません。

起動ログは同じ場所の`herdr-open-startup.log`に残ります。
起動・ロック・スナップショットの照合はそれぞれ15秒を上限に待ちます。
未知の形式や照合失敗で停止した場合は、表示された原因とログを確認してください。
実行時のディレクトリ変更を基に対応先を自動変更せず、初回に記録した対応を使います。
