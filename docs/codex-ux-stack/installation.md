# Codex UX Stack：インストール・更新・解除

[概要](README.md) · [使い方](usage.md) · [検証範囲](validation.md) · [docs一覧](../README.md)

## 前提条件と導入

Linux / WSL2、Bash、Python 3.10以上、Node.js 20以上、npm、構造化exec出力・plugin・MCPに対応する認証済みCodex CLIが必要です。
ハーネスの実行にはGit、ChromiumのOS依存ライブラリ、Codexサンドボックスを起動できるホスト環境も必要です。

リポジトリのルートで実行します。スクリプト1ファイルだけをコピーして実行することもできます。

~~~bash
bash install_codex_ux_stack.sh --help
bash install_codex_ux_stack.sh --dry-run
bash install_codex_ux_stack.sh
bash install_codex_ux_stack.sh --doctor
~~~

**引数なしは実際に導入します。** --dry-runは予定表示だけで、ダウンロード・登録・導入先への書き込みを行いません。
インストーラーはCodexのログイン、対象アプリへの依存追加、データ移行を行いません。

## オプション

| オプション | 動作 |
|---|---|
| なし | 不足する標準構成を導入 |
| --deep | 固定コミットのux-critiqueも導入 |
| --force | このインストーラーが導入した未編集の対象を再配置・再登録 |
| --dry-run | 導入・解除の予定表示 |
| --status | 資材と登録の検査。ブラウザーは起動しない |
| --doctor | 資材・登録に加え、Chromium起動とCodexサンドボックスを確認 |
| --uninstall | このインストーラーが導入した未編集の対象だけを解除 |
| --extract PATH | 空または未使用のディレクトリへソースを展開。導入はしない |
| --codex-home PATH | Codex設定と実行環境の保存先 |
| --skills-root PATH | 新規Skillの保存先 |
| --bin-dir PATH | 起動コマンドの保存先 |
| --no-browser-download | Chromium取得を省略。実行可能かは別途確認 |
| --help / -h | ヘルプ表示 |

既存のSkillは指定先、CodexのSkillディレクトリ、~/.agents/skillsを確認し、重複導入を避けます。
手動導入や編集済みの対象は--forceでも置き換えません。無効化されている対象pluginは自動で有効化せず原因を報告します。

## 取得元・版・配置

| 対象 | 取得・版 | 新規の保存先 |
|---|---|---|
| ooui-design・参照資料 | 配布物1.1.0。OOUIと認知負荷の基準を同梱 | ~/.agents/skills/ooui-design/ |
| Product Design / Build Web Apps | openai-curated-remoteのCodex管理版。実際の版を記録 | Codexのplugin環境 |
| web-design-guidelines | vercel-labs/agent-skillsのコミット063bee94c3f4df8453406c830b0a7df0f2860278 | ~/.agents/skills/web-design-guidelines/ |
| ux-critique | Thecsiz/ux-critiqueのコミット3da293cafb639195bf71797590081d4ffb0045ba | ~/.agents/skills/ux-critique/ |
| ハーネス・専用Skill・共通設計基準 | 配布物1.1.0 | ~/.agents/skills/ux-gan-harness/ |
| ブラウザー環境 | Playwright 1.63.0 / Playwright MCP 0.0.83、埋め込みnpm lockfile | CODEX_HOME/ux-stack/runtime/ |
| 起動コマンド | ハーネスのBashへ渡すラッパー | ~/.local/bin/ux-gan-harness |
| 導入記録・バックアップ | ハッシュ、版、処理結果、旧資材 | CODEX_HOME/ux-stack/ |

CODEX_HOMEの省略時は~/.codexです。ChromiumはPlaywrightのキャッシュへ取得し、PLAYWRIGHT_BROWSERS_PATHがあればその設定を使います。
標準MCPは固定版のNodeエントリーポイントと、取得したChromiumの実行パスを使います。
既存のMCPは独自設定を保護します。配置前に資材を検査し、再配置時は旧資材をbackups/へ残します。

skills@latestへの依存は外しました。取得するSkillの正本は[sources.json](../../tools/codex-ux-stack/sources.json)、
ブラウザーの正本は[npm lockfile](../../tools/codex-ux-stack/browser/package-lock.json)です。配布元にあるライセンス・参照資材も保存します。
ライセンスファイルがない原本は、その事実をUPSTREAM_SOURCE.jsonに記録します。

OOUIと認知負荷の参照資料は、同じ正本からooui-designとハーネスへ配置します。
ハーネスには自身の資料を同梱するため、別のSkill配置先には依存しません。
yomiyasuは日本語UI文言の確認に利用を推奨します。導入する場合は
[既存の別インストーラー](../codex-yomiyasu/installation.md)を使ってください。
status / doctorには利用可能かを表示しますが、未導入でもUX Stackの導入失敗にはしません。

## 更新・確認

~~~bash
bash install_codex_ux_stack.sh --status
bash install_codex_ux_stack.sh --doctor
bash install_codex_ux_stack.sh
bash install_codex_ux_stack.sh --force
bash install_codex_ux_stack.sh --deep --force
~~~

1.0.0から更新する場合は`--force`を使います。引数なしでは新しいooui-designが追加されますが、
既存の未編集ハーネスはそのままです。status / doctorは新スキルとハーネスの参照資料も確認するため、
旧ハーネスのままでは未準備として報告します。未管理・編集済みの同名Skillは保護します。

対象ごとにINSTALLED・SKIP・FAILEDを表示します。一部が失敗すると終了コード1とINCOMPLETEになります。
先に導入した対象は残り、原因を解消して再実行できます。plugin・MCPを含む一括ロールバックはありません。
ファイルの置き換えに失敗した場合は直前の資材を復元します。

COMPLETEは導入処理の完了です。ブラウザー、Codexサンドボックス、モデル、アプリの操作は別の確認です。
Skillが候補に出なければCodexを再起動して$ooui-designまたは$ux-gan-harnessを入力してください。
起動コマンドがPATHにない場合は、保存先の絶対パスでも使えます。

## 解除・復旧

~~~bash
bash install_codex_ux_stack.sh --uninstall --dry-run
bash install_codex_ux_stack.sh --uninstall
~~~

導入記録にある未編集の対象だけを解除します。
もともと存在した対象、編集済みの資材・設定、アプリの成果物、ブラウザーキャッシュ、バックアップは残ります。
解除できない依存対象がある場合はブラウザー環境も保護し、未完了を報告します。

手動編集を保持して更新する場合は、保存先とmanifest.json、バックアップを比較してください。
編集を別の場所へ保存し、導入先を空けて再実行した後に必要な変更を戻せます。

<a id="troubleshooting"></a>

## 困ったとき

| 状況 | 確認・対処 |
|---|---|
| pluginが見つからない | codex plugin list --available --jsonで配布名・marketplaceを確認 |
| Skillが候補に出ない | 保存先とSkillの無効化設定を確認 |
| 設計参照資料が欠落・空・旧版 | 未編集の管理対象は--forceで更新。同名の未管理・編集済みSkillは内容を保管してから導入先を確認 |
| Chromiumが起動しない | doctorで原因を確認し、PlaywrightのOS依存ライブラリを用意 |
| 独自MCP設定が残る | その設定を検査。ハーネスは失敗理由を記録してローカル経路へ切替可能 |
| bwrap・ユーザー名前空間の権限エラー | ホスト／コンテナーのCodexサンドボックス対応を修復。権限は迂回せず停止 |
| 編集済みとして再導入が止まる | ハッシュと内容を比較し、編集を別に保管してから更新 |
| ダウンロードやnpmが失敗 | 既存資材は削除されない。原因を解消して再実行 |
| 起動コマンドが見つからない | ~/.local/bin/ux-gan-harness doctorを実行するかbin-dirをPATHへ追加 |

参考：[Codexの非対話実行](https://developers.openai.com/codex/noninteractive/)、[Skillの配置と呼び出し](https://developers.openai.com/codex/skills/)、[Playwright MCP](https://github.com/microsoft/playwright-mcp)、[Linuxサンドボックス](https://github.com/openai/codex/blob/main/codex-rs/linux-sandbox/README.md)。
