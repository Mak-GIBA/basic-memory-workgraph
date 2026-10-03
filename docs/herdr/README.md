# Herdr — 作業ディレクトリからターミナルを開く

[docs一覧](../README.md) · [導入手順](installation.md) · [使い方](usage.md)

プロジェクトへ移動して`herdr`を実行すると、そのディレクトリに対応するworkspaceを開く構成を用意します。
既存のworkspaceがあれば再利用し、なければ作成します。
[install_herdr.sh](../../install_herdr.sh)は単体で使えます。引数なしでは実際に導入・設定します。

## 導入するもの

| ツール・資材 | 提供元 | 役割 |
|---|---|---|
| Herdr | [Herdr](https://herdr.dev/) | ターミナルとworkspace。未導入時だけ公式インストーラーから取得 |
| `herdr-open` | このリポジトリ | ディレクトリの実パスでworkspaceを検索・選択・作成する |
| Bashの`herdr`関数 | このリポジトリ | 引数なしを`herdr-open`へ、引数ありを本来のHerdrへ渡す |

workspace名やラベルだけで照合せず、最初に確認した実パスとの対応を別ファイルに保持します。
Git worktreeは作りません。CodexのSkill・Plugin・MCP・Hookも登録しません。

ラッパーはHerdr 0.9.3で確認したCLIと`session.json`の形式を使います。
未知の形式では、新しいworkspaceを推測で作らず停止します。
導入は[導入手順](installation.md)、日常の操作は[使い方](usage.md)を参照してください。
