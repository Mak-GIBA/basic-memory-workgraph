# yomiyasuのインストール・更新・解除

[概要](README.md) · [使い方](usage.md)

## 前提と導入

BashとPython 3.10以降が必要です。初回の通常導入と上流更新にはGitHubへのHTTPS接続を使います。
CodexでSkillを利用できる環境をあらかじめ用意してください。Pythonパッケージは追加しません。

```bash
bash install_codex_yomiyasu.sh
bash install_codex_yomiyasu.sh --apply
bash install_codex_yomiyasu.sh --doctor
```

初回導入ではGitHub Releasesの最新安定版を調べ、その実行で取得するcommitを確定します。
取得したファイルのGit blob IDとサイズを検査してから配置します。
同じ構成での再実行は既存の導入を保持し、上流を自動更新しません。

既定の配置先は`~/.agents/skills/yomiyasu/`です。
`--skills-dir PATH`で親ディレクトリを変えた場合は、診断・更新・解除でも同じ指定を使います。
同名の未管理Skillや別の場所のyomiyasuを検出した場合は上書き・二重登録をしません。

## 更新と発動モード

```bash
bash install_codex_yomiyasu.sh --check-update
bash install_codex_yomiyasu.sh --update
bash install_codex_yomiyasu.sh --update --apply
```

`--check-update`は導入版と最新安定版を比較します。
`--update`も通信して更新予定を調べますが、`--apply`がなければ配置は変更しません。
既存の管理ファイルに編集や欠落がある場合は、`--force`を付けても停止します。
更新前の資材はバックアップに残します。

上流を更新せず、このリポジトリの入口・運用設定だけを更新する場合は`--force --apply`を使います。
既存の発動モードは保持します。変更するときは、次のように明示します。

```bash
bash install_codex_yomiyasu.sh --mode explicit --force --apply
bash install_codex_yomiyasu.sh --mode auto --force --apply
```

新規導入の既定は`auto`で、文章を仕上げる依頼でSkillの自動選択を許可します。
`explicit`は`$yomiyasu`を指定して使う設定です。毎回答を校正するHookは登録しません。

## 解除と検査

```bash
bash install_codex_yomiyasu.sh --uninstall
bash install_codex_yomiyasu.sh --uninstall --apply
bash install_codex_yomiyasu.sh --self-test
bash install_codex_yomiyasu.sh --extract /tmp/yomiyasu-review
```

解除はこのインストーラーが管理するSkillだけが対象です。手で編集した管理ファイルや追加ファイルは消さず停止します。
`--doctor`は通信せず配置・ハッシュ・発動設定・既知の競合を調べます。
競合する別の校正Skillを検出しても、そのSkillを無効化しません。
`--project PATH`で競合診断の対象プロジェクトを指定できます。

自己テストは一時環境と模擬の上流応答を使います。実際の配布元への通信やモデルの文章品質は検証しません。
`--extract`は独自資材を未使用または空のディレクトリへ展開します。インストールは行いません。
通信なしで原本を配置するには`--source-dir PATH --apply`を使えますが、
ローカルチェックアウトはスクリプトに記録された固定commitのファイルと一致する必要があります。
