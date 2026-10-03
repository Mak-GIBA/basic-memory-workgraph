# Office Workbenchのインストール・更新・解除

[概要](README.md) · [使い方](usage.md)

## 前提と導入

主対象はLinux / WSL2のglibc環境で、x86_64とARM64に対応します。
macOS用の取得経路もありますが、この環境では未検証です。ネイティブWindowsとAlpineは対象外です。
Bash、Python 3.11以降、venv・pip、導入済みCodexが必要です。初回導入はGitHubとPyPIへ接続します。

```bash
bash install_codex_office.sh
bash install_codex_office.sh --apply
export PATH="$HOME/.local/bin:$PATH"
office-workbench doctor
```

Skillは`~/.agents/skills/office-workbench/`、CLI入口は`~/.local/bin/office-workbench`に配置します。
本体・OfficeCLI・venvは`${XDG_DATA_HOME:-~/.local/share}/codex-office/releases/`、
管理情報は`${XDG_CONFIG_HOME:-~/.config}/codex-office/install.json`に保存します。
既存のECC、Basic Memory、Hook、AGENTS、シェル設定は変更しません。

## 描画環境と任意機能

```bash
bash install_codex_office.sh --system-deps
bash install_codex_office.sh --install-system-deps --apply
```

`--system-deps`は不足する描画・フォント環境の導入コマンドを表示します。
`--install-system-deps --apply`はUbuntu / DebianでOSパッケージを導入し、必要に応じてsudoを使います。
このOS操作は失敗時の自動ロールバックの対象外です。他のOSでは利用中のパッケージ管理方法で用意します。
フォントファイルはキットに含みません。

| 指定 | 追加するもの・動作 |
|---|---|
| `--with-mcp --apply` | 公式`codex mcp add`で`codex-office-workbench`を登録。この場合だけCodex設定を変更 |
| `--with-docling --apply` | 大きな別venvにDoclingを導入。変換時のモデル取得は別途発生する場合あり |
| `--officecli /absolute/path/officecli --apply` | 明示した既存バイナリを再利用。変更・削除しない |

MCPは同名の既存設定を上書きしません。登録に失敗した場合も、コア導入は保持してMCPの未完了を報告します。
Doclingの追加はOCRやモデル処理を自動実行する指定ではありません。

## 更新・解除・検査

```bash
bash install_codex_office.sh --apply --force
bash install_codex_office.sh --uninstall
bash install_codex_office.sh --uninstall --apply
bash install_codex_office.sh --self-test
bash install_codex_office.sh --extract /tmp/codex-office-review
```

通常の再実行は同じ構成を保持します。明示更新では新しいreleaseを構築し、旧releaseとバックアップを残します。
`--force`でも編集済みの管理ファイルは上書きしません。再構築後も使う任意機能のフラグは更新時にも指定します。
venvを含む`releases/`は移動しないでください。

MCPを追加した場合は、先に`office-workbench mcp-disable --apply`で自分の登録を解除します。
アンインストールは管理する入口・Skill・管理情報を解除し、文書・旧release・バックアップは保持します。

自己テストは通信・Codexを模擬します。PDFの実ライブラリがない場合は対象テストをSKIPします。
`--extract`は未使用または空のディレクトリへソースと`README_JA.md`を展開します。
`--assets-only --apply`は通信なしで入口だけを置く診断用モードです。編集エンジンがなく、利用準備は未完了です。
