# HerdrのインストールとBash設定

[概要](README.md) · [使い方](usage.md)

## 前提と導入

Linux / macOSのBashとPython 3.8以降が必要です。
初回取得にはcurlと公式インストーラーの依存ツール、ネットワーク接続が必要です。sudoやpipは使いません。

```bash
bash install_herdr.sh --dry-run
bash install_herdr.sh
source ~/.bashrc
herdr --version
```

既存のHerdrがあれば再利用し、なければ`https://herdr.dev/install.sh`を取得して実行します。
公式処理を一時領域で実行し、バージョンと必要なCLIを確認してから配置します。
設定時にはサーバーを開始しません。

| 対象 | 配置・変更 |
|---|---|
| 新規Herdrバイナリ | `~/.local/bin/herdr` |
| ラッパー | `~/.local/bin/herdr-open` |
| Bash設定 | `~/.bashrc`の`herdr-open: cwd workspace`管理ブロック |

管理ブロックにはPATHと`herdr`関数を追加します。管理対象の既存ファイルを変更する前にバックアップを作ります。
既存のdotfileがシンボリックリンクの場合はリンクを保ち、参照先を更新します。
未管理の同名関数・aliasや、認識できないラッパーがある場合は保持して停止します。
既存のHerdr設定とセッションデータは保持します。

## 既存バイナリの指定と再実行

```bash
bash install_herdr.sh --binary /absolute/path/to/herdr --dry-run
bash install_herdr.sh --binary /absolute/path/to/herdr
```

上のパスは実際の実行ファイルに置き換えてください。
指定したバイナリは再インストールしません。同じ構成で再実行した場合は変更不要と表示します。
新しいスクリプトでラッパーを更新できますが、Herdr本体の更新は本体の手順で行います。

## 解除と検証

専用のアンインストールオプションはありません。
設定を解除するには、`~/.bashrc`の開始・終了マーカーで囲まれた管理ブロックを取り除き、新しいBashを開きます。
`~/.local/bin/herdr-open`の削除は、利用していないことを確認して行います。
この操作でHerdr本体やセッションデータを削除する必要はありません。

```bash
python3 -m unittest discover -s tests -p 'test_install_herdr.py' -v
```

テストは一時HOMEと模擬のHerdr・取得処理を使います。実ダウンロードや実セッションの起動は含みません。
