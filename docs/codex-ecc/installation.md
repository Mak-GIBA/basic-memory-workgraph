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
初回の既定では、独立したMCPとしてContext7とPlaywrightを追加します。
同名の既存設定（無効設定を含む）とContext7の旧名`context7-mcp`はそのまま保持し、重複登録しません。
フックを自動承認するオプションは使用しません。

stdioのMCPを起動するにはNode.jsと`npx`が必要です。初回起動時にnpmパッケージを取得します。
Context7はライブラリ文書探索、Playwrightは対話的なブラウザー操作の接続として選んでいます。
今回の比較で既存手段に対する正答率の改善を確認したという意味ではありません。
用途別に追加するMCPは、次のプリセットまたは名前のカンマ区切りで選べます。

| 選択 | 新規に追加する候補 | 適する用途 |
|---|---|---|
| `recommended` | Context7、Playwright | 文書探索と対話的な画面確認。初回の既定 |
| `research` | Context7、Parallel Search | 文書・Web調査。既存のWeb検索で足りる場合は不要 |
| `browser` | Playwright、Chrome DevTools | 画面操作、console・network・性能の診断 |
| `cloudflare` | Context7、Cloudflare Docs | Cloudflare公式文書の探索 |
| `none` | 追加しない | ECCスキルだけを使う。既存MCPは保持する |

```bash
# まず通信・変更なしで予定を確認する
bash install_codex_ecc.sh --mcps recommended,browser,cloudflare
# 初回適用、または適用済み環境の更新時に選択を指定する
bash install_codex_ecc.sh --apply --mcps recommended,browser,cloudflare
bash install_codex_ecc.sh --update --apply --mcps research
```

名前は`context7`、`playwright`、`chrome-devtools`、`parallel-search`、`cloudflare-docs`、
`sequential-thinking`です。プリセットと名前を組み合わせられ、重複はまとめます。
`none`は他の指定と併用できません。未知の名前は設定変更やECC取得の前にエラーになります。

Sequential Thinkingは明示的な選択だけで追加できます。今回の6問×2回では両条件とも12/12正答で、
平均処理時間は29.176秒から51.7875秒へ増え、常用の事前採用条件を満たしませんでした。
難易度や試行数が限られるため、別の課題での効果まで否定する結果ではありません。
Token Optimizerは登録対象に含めません。同一会話の再読では返却量を減らせましたが、
過去の本文を持たない新しい会話で重要値を取得できない失敗が2回再現しました。
今回測ったのは`@ooples/token-optimizer-mcp@7.4.3`で、ECCカタログの無印パッケージとは区別しています。
課金節約やモデル精度の改善はこの返却量測定からは主張しません。

測定条件、同じ入力の実出力、用途別判断は[MCPの導入判断](mcp-evaluation.md)にあります。
新規登録のstdioパッケージは測定したバージョンに固定しています。バージョンを上げる際は再検証して登録定義を更新してください。
PlaywrightとChrome DevToolsの新規登録はheadless・隔離プロファイルを使用します。
Chrome DevToolsは利用統計とCrUXへのURL問い合わせを無効にします。既存接続の設定は変更しません。
ブラウザー操作には利用可能なブラウザーも必要です。インストーラーはブラウザーやNode.jsを導入しません。
Cloudflare DocsとParallel SearchはURL接続です。公開検索は認証なしで確認できましたが、
制限や追加の認証要件は各サービスの運用に従います。
GitHubは既存の公式連携または`gh`を使用します。Jira・Confluenceなど、認証や接続先の指定が必要なサービスは自動登録しません。

## オプション

| オプション | 動作・既定値 |
|---|---|
| `--apply` | 実際に導入・設定する。更新・復元にも必要 |
| `--dry-run` | 予定表示のみ。引数なしも同じ動作 |
| `--doctor` | 配置、管理ファイル、原本の取得、ECCの無効状態を診断 |
| `--update` | 適用済みの環境で、ECCと管理資材を更新する |
| `--mcps SELECTION` | 追加するMCPを選ぶ。初回の既定は`recommended`、再適用・更新では前回の選択 |
| `--restore` | 管理した設定と入口を復元。ECC本体は削除しない |
| `--json` | 結果をJSONで出力する |
| `--codex-home PATH` | Codex設定先。既定は `CODEX_HOME`、未指定時は `~/.codex` |
| `--skills-root PATH` | 入口の配置先。既定は `~/.agents/skills` |
| `--codex COMMAND` | Codex実行ファイル。既定は `codex` |
| `--cwd PATH` | 原本取得と診断の対象ディレクトリ。既定は現在の場所 |

`--apply` と `--dry-run` は併用できません。`--doctor`・`--update`・`--restore` も互いに併用できません。
`--doctor` は `--apply` と併用できません。
`--mcps`は導入・更新で使い、診断・復元とは併用できません。
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

Basic Memory、既存のMCP、他のプラグイン、スキル一覧の上限を保持します。
追加したMCP設定は管理状態に記録し、再適用では重複させません。
選択は不足する接続の追加だけに使います。別のプリセットや`none`へ変更しても、既存接続を無効化・削除しません。
以前のインストーラーが追加したSequential Thinkingなども保持します。旧状態に選択の記録がない場合は、
新しく追加する候補に`recommended`を使い、以前の管理・復元情報を引き継ぎます。
`--restore --apply`は変更されていない管理対象MCPだけを削除します。
管理対象MCPへ認証設定などを手で追加した場合は、上書き・削除せず停止します。
`--doctor`のMCP診断は設定の検証です。起動や認証、検索結果の取得成功を保証するものではありません。
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
