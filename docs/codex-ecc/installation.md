# ECCのインストール・更新・復元

[概要](README.md) · [使い方](usage.md)

## 前提条件

- Linux / WSL2、Bash、Python 3.11以降の `python3`、Git。
- `codex plugin` と `codex app-server` が使える、導入済みのCodex CLI。
- 初回導入・更新ではECC配布元へのネットワーク接続。
- このリポジトリ一式。シェルスクリプト1枚だけのコピーでは使えません。

Codex、Python、Git自体のインストールは行いません。以下はリポジトリのルートで実行します。

## 初回導入

**引数なしは、通信・設定変更をしない予定表示です。**

```bash
bash install_codex_ecc.sh
bash install_codex_ecc.sh --apply
bash install_codex_ecc.sh --doctor
```

適用では、ローカルの設定と同名スキルを確認した後、CodexからECCの登録・導入状態を取得します。
マーケットプレイスがなければ `affaan-m/ECC` を登録し、未導入なら `ecc@ecc` をインストールします。
導入済みなら、その原本を再利用します。通常適用では明示的なマーケットプレイス更新を実行しません。
取得する版とキャッシュはCodexが管理します。

その後、ECCの有効設定を`false`にし、入口4件と管理CLIを配置して診断します。
フックを自動承認するオプションは使用しません。

## オプション

| オプション | 動作・既定値 |
|---|---|
| `--apply` | 実際に導入・設定する。更新・復元にも必要 |
| `--dry-run` | 予定表示のみ。引数なしも同じ動作 |
| `--doctor` | 配置、管理ファイル、原本の取得、ECCの無効状態を診断 |
| `--update` | 適用済みの環境で、ECCと管理資材を更新する |
| `--restore` | 管理した設定と入口を復元。ECC本体は削除しない |
| `--json` | 結果をJSONで出力する |
| `--codex-home PATH` | Codex設定先。既定は `CODEX_HOME`、未指定時は `~/.codex` |
| `--skills-root PATH` | 入口の配置先。既定は `~/.agents/skills` |
| `--codex COMMAND` | Codex実行ファイル。既定は `codex` |
| `--cwd PATH` | 原本取得と診断の対象ディレクトリ。既定は現在の場所 |

`--apply` と `--dry-run` は併用できません。`--doctor`・`--update`・`--restore` も互いに併用できません。
`--doctor` は `--apply` と併用できません。
カスタム配置先を使う場合は、更新・診断・復元でも同じ引数を指定してください。

予定表示では、ローカルの設定と管理ファイルだけを確認します。実際の配布元・導入版の照会は適用時に行います。
診断は独立したapp-serverを利用し、モデル処理や会話を開始しません。Codexによるメタデータ取得が発生する場合があります。

## 配置と設定変更

| 対象 | 配置・変更 |
|---|---|
| ECC原本 | Codex標準プラグインのキャッシュ。パスは固定しない |
| 有効設定 | Codexの `config.toml` に `[plugins."ecc@ecc"]` の `enabled = false` |
| 入口4件 | スキル配置先の `ecc-python`、`ecc-errors`、`ecc-security`、`ecc-library` |
| 管理CLI・状態 | Codex設定先の `ecc-on-demand/` |
| 設定バックアップ | 同ディレクトリの `config.before-ecc-on-demand.<識別子>.toml`。所有者のみ読み書き可能 |

Basic Memory、独立したMCP、他のプラグイン、スキル一覧の上限を保持します。
ECCに付属する起動フックとMCPはプラグインの無効化に伴い停止します。
ECC設定がインラインテーブルやドット区切りのキーで書かれている場合は自動編集せず、
通常の`[plugins."ecc@ecc"]`テーブルに整理するよう案内します。

## 更新・再実行

```bash
bash install_codex_ecc.sh --update
bash install_codex_ecc.sh --update --apply
```

更新はCodex標準の `plugin marketplace upgrade ecc` と `plugin add ecc@ecc` を使い、
管理CLIと入口もリポジトリの資材で更新します。管理ファイルを手で編集した場合は上書きせず停止します。
以前の方式でこのリポジトリの管理CLIだけを適用した環境も、その復元情報を引き継ぎます。

導入・更新の処理を始める前にバックアップを作ります。途中で失敗した場合はECCを無効に戻し、原因とバックアップ先を表示します。
初回失敗の復元情報は `bootstrap.json` に残し、原因を直して `--apply` を再実行すると引き継ぎます。
更新失敗後は `--update --apply` を再実行できます。復元情報やバックアップを手で削除しないでください。

新しいセッションで反映を確認してください。実行中の共有デーモンは自動で再起動しません。
`--doctor` はローカルのネイティブカタログを確認します。リモートプラグインを含む実際のセッションの件数とは異なる場合があります。

## 復元

```bash
bash install_codex_ecc.sh --restore
bash install_codex_ecc.sh --restore --apply
```

導入済みだったECCは、最初に記録した有効値へ戻します。有効だった場合は一括スキル登録や起動フックも再開されます。
今回初めてECCを導入した環境では、原本を残したまま無効状態を維持します。
入口と管理CLIを取り除き、導入後に追加した無関係な設定とバックアップを保持します。
ECC本体やマーケットプレイスの削除、フックの信頼状態の削除は行いません。

管理ファイルやECCの有効値を手で変更した場合は、それを消さず停止します。
初回導入が途中で失敗し、管理状態の作成が完了していない場合は、まず `--apply` を成功させてください。

## 困ったとき

| 状況 | 対処 |
|---|---|
| Codexコマンドが不足している | 使用中のCLIで `codex plugin --help` と `codex app-server --help` を確認する |
| `ecc` が別の配布元に使われている | `codex plugin marketplace list --json` で確認する。スクリプトは置き換えない |
| カタログに `ecc@ecc` がない | 元のエラーと `codex plugin list --available --json` を確認する。別プラグインへ切り替えない |
| 同名スキルや管理ファイルの編集がある | ファイルを確認し、自分の変更を保管・整理してから再実行する |
| 原本が欠けている | `--doctor` で原因を確認し、管理導入済みなら `--update --apply` で標準の再取得を試す |
