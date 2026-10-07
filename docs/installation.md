# 全ツールの一括インストール

[リポジトリ概要](../README.md) · [docs一覧](README.md)

[`install_all.sh`](../install_all.sh)は、全9ツールの一括導入と`--only`による個別選択に対応した共通の入口です。
選んだツールの個別インストーラーを順に呼び出します。
各ツールの取得元、配置先、編集保護は個別インストーラーに従います。

## 前提条件

リポジトリをcloneして使います。一括スクリプトだけをダウンロードすると、呼び出すインストーラーや補助資材が不足します。
全ツールの標準導入はLinux / WSL2向けです。Bash、PATH上のPython 3.11以降の`python3`、venv・pip、
Node.js 20以降・npm、Git、curl、導入済みCodex CLI、外部配布元へのネットワーク接続が必要です。
導入済みWorkgraphを更新する場合は、同じ`python3`からPyYAMLを参照できるようにします。
準備方法は[WorkgraphのPython環境](basic-memory-workgraph/installation.md#python-tools)にあります。

Codex CLIには、各ツールが使うplugin・MCP・app-server等のコマンドが必要です。
選択したツールだけを入れる場合は、そのツールの前提条件を確認してください。
たとえばUX Stackとyomiyasuの組み合わせにはPython 3.10以降を使えます。
導入後のGitHub接続、モデルの認証、文書描画など、実際の利用に必要な準備は各ガイドで説明しています。

## 導入する

```bash
git clone https://github.com/Mak-GIBA/basic-memory-workgraph.git
cd basic-memory-workgraph
bash install_all.sh --list
bash install_all.sh --dry-run
bash install_all.sh --apply
```

引数なし、または`--dry-run`は、実行予定のコマンドだけの表示です。
個別インストーラーは起動せず、ダウンロードや導入先への書き込みも行いません。
前提ソフトの動作や配布元への接続は、この予定表示では確認しません。
`--apply`を付けると、以下の順序で実際に導入します。

| ID | 導入対象・標準動作 | 詳細 |
|---|---|---|
| `workgraph` | Basic Memory、公式plugin、Workgraph・hooks・保存プロジェクト。導入済みなら設定を保持する`--update` | [導入・更新](basic-memory-workgraph/installation.md) |
| `ux-stack` | ooui-design、認知負荷のガイド、画像付きUX検証、Product Design・Build Web Apps、UIレビュー、Playwright | [導入・更新](codex-ux-stack/installation.md) |
| `speckit` | SpecKit CLIと上流工程のWorkbench・8 Skill。`--apply`で導入 | [導入・更新](speckit-upstream/installation.md) |
| `github-pm` | GitHub Project DirectorとCodex共通指示。ghの導入は別途指定 | [導入・更新](codex-github-pm/installation.md) |
| `design-research` | コアロジックの調査・比較・検証に使うSkillとハーネス | [導入・更新](design-research/installation.md) |
| `ecc` | Codex標準ECC pluginと必要時に参照する4つの入口。`--apply`で導入・設定 | [導入・更新・復元](codex-ecc/installation.md) |
| `office` | OfficeCLI、文書処理ライブラリ、Office Workbench。`--apply`で導入 | [導入・更新](codex-office/installation.md) |
| `yomiyasu` | 日本語の推敲用Skill、原本、検査ツール。`--apply`で導入 | [導入・更新](codex-yomiyasu/installation.md) |
| `herdr` | Herdr、herdr-open、Bash設定 | [導入とBash設定](herdr/installation.md) |

UX Stackは日本語のUI文言を仕上げる際にyomiyasuを推奨します。
一括導入では両方が含まれ、個別選択なら次のように組み合わせられます。

```bash
bash install_all.sh --only ux-stack,yomiyasu --dry-run
bash install_all.sh --only ux-stack,yomiyasu --apply
```

`--only`はカンマ区切りでも、複数回でも指定できます。同じIDの重複は1回にまとめ、上の表の順序で実行します。
スクリプト自身の場所を基準に資材を参照するため、別の作業ディレクトリから絶対パスで呼び出すこともできます。

## 再実行・更新・解除

既存の設定や編集済み資材の扱いは、各インストーラーの保護処理に従います。
一括スクリプトから`--force`を渡すことはありません。
導入済みWorkgraphは`CODEX_HOME`、未指定なら`~/.codex`にある配置を検出し、
`--update`で保存先・保存モードを維持しながらローカル資材とスキーマを更新します。
この経路ではBasic Memory本体や外部pluginを取得・更新しません。
既存配置が不完全でも、初回導入で設定を作り直す処理へは切り替えません。

ほかのツールは通常の導入経路を使います。すでにある管理対象をそのまま保持するツールもあるため、
一括導入の再実行がすべてのツールの最新版への更新になるわけではありません。
特定の版への更新、任意機能、配置先変更は、表の導入ガイドに沿って個別インストーラーで指定します。
解除も各ガイドに従って行います。Herdrは専用の解除オプションがなく、管理対象のBash設定等を手動で取り除きます。
OfficeのMCP・Docling・OSパッケージ導入などの任意機能は、一括スクリプトからは指定しません。

## 途中で失敗した場合

選択したインストーラーと必要な補助コードがあるかを、導入開始前に確認します。
実行中に1つの導入処理が失敗した場合は、残りのツールも実行し、最後にツールごとの結果と未完了件数を表示します。
成功した導入を一括で取り消す処理はありません。原因を解消して全体を再実行するか、失敗したIDを`--only`で選び直してください。
個別インストーラーが中断を表す終了コード130または143を返した場合は、後続の導入を停止します。

| 終了コード | 意味 |
|---|---|
| `0` | 予定・一覧・ヘルプの表示完了、または選択した全導入処理が正常終了 |
| `1` | 1つ以上の導入処理が未完了。表示されたIDと個別ログを確認 |
| `2` | 引数が不正、または選択したインストーラー・補助コードが不足。導入処理は未開始 |
| `130` / `143` | 中断。先に完了した処理は保持 |

`COMPLETE`は選択したインストーラーの正常終了を示します。
実際のCodexセッションでのSkillの選択、モデルの出力品質、アプリや文書の完成までは示しません。
導入後はCodexを再起動し、各ガイドの状態確認・doctor・最初の利用手順を実行してください。
