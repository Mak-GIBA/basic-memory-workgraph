# yomiyasuと補助Skillのインストール・更新・解除

[概要](README.md) · [使い方](usage.md)

## 前提と導入

BashとPython 3.10以降が必要です。yomiyasuの初回の通常導入と上流更新にはGitHubへのHTTPS接続を使います。
CodexでSkillを利用できる環境をあらかじめ用意してください。Pythonパッケージは追加しません。

```bash
bash install_codex_yomiyasu.sh
bash install_codex_yomiyasu.sh --apply
bash install_codex_yomiyasu.sh --doctor
```

標準ではyomiyasu、paragraph-writing、japanese-direct-writingの3スキルを一括導入します。yomiyasuの初回導入ではGitHub Releasesの最新安定版を調べ、その実行で取得するcommitを確定します。
取得したファイルのGit blob IDとサイズを検査してから配置します。
同じ構成での再実行は既存の導入を保持し、上流を自動更新しません。

paragraph-writingは固定版の原本・ライセンスとともにスクリプトに同梱しているため、取得用の通信はありません。
japanese-direct-writingも、提供されたZIPの本文と発動設定を同梱しています。導入時に元のZIPや取得用の通信は不要です。
ZIP名とSHA256、各原本ファイルのSHA256は、同スキルの`SOURCE.json`に記録します。

既定の配置先は`~/.agents/skills/`の下にある各スキル名のディレクトリです。
`--skills-dir PATH`で親ディレクトリを変えた場合は、診断・更新・解除でも同じ指定を使います。
同名の未管理Skillや別の場所の同名Skillを検出した場合は上書き・二重登録をしません。
選択した全スキルの検証と準備を済ませてから配置します。ディレクトリの切り替えに失敗した場合は、切り替え済みのSkillも元へ戻します。

## 対象を選ぶ

`--only all|yomiyasu|paragraph-writing|japanese-direct-writing`で導入・更新・診断・解除の対象を選べます。既定は`all`です。

```bash
bash install_codex_yomiyasu.sh --only paragraph-writing --apply
bash install_codex_yomiyasu.sh --only japanese-direct-writing --apply
bash install_codex_yomiyasu.sh --only yomiyasu --doctor
bash install_all.sh --only yomiyasu --apply
```

paragraph-writingまたはjapanese-direct-writing単独の導入には通信が不要です。一括導入スクリプトの`yomiyasu` IDは3スキルを導入します。
1.1.0または1.2.0から3スキルを導入する場合は、次の入口更新を使います。既存yomiyasuの上流原本と、各スキルの発動モードを保持します。

```bash
bash install_codex_yomiyasu.sh --force --apply
```

## 更新と発動モード

```bash
bash install_codex_yomiyasu.sh --check-update
bash install_codex_yomiyasu.sh --update
bash install_codex_yomiyasu.sh --update --apply
```

`--check-update`はyomiyasuの最新安定版と、補助スキルの同梱版を、それぞれ導入版と比較します。
`--update`もyomiyasuを選択した場合は通信して更新予定を調べますが、`--apply`がなければ配置は変更しません。
paragraph-writingまたはjapanese-direct-writing単独の更新確認・更新は通信せず、実行しているスクリプトの同梱版を使います。
既存の管理ファイルに編集や欠落がある場合は、`--force`を付けても停止します。
更新前の資材はバックアップに残します。

上流を更新せず、このリポジトリの入口・運用設定と補助スキルを更新する場合は`--force --apply`を使います。
既存の各Skillの発動モードは保持します。新規の補助スキルは管理済みyomiyasuのモードを継承し、全て新規なら`auto`にします。
`--mode`を指定すると選択したSkillへ適用します。既存設定を変更するときは、次のように明示します。

```bash
bash install_codex_yomiyasu.sh --mode explicit --force --apply
bash install_codex_yomiyasu.sh --mode auto --force --apply
```

新規導入の既定は`auto`で、文章を仕上げる依頼でSkillの自動選択を許可します。
`explicit`は各スキル名を指定して使う設定です。japanese-direct-writingの本文は原本のまま配置し、`explicit`では発動設定の`allow_implicit_invocation`だけを`false`に変更します。毎回答を校正するHookは登録しません。

## 解除と検査

```bash
bash install_codex_yomiyasu.sh --uninstall
bash install_codex_yomiyasu.sh --uninstall --apply
bash install_codex_yomiyasu.sh --only paragraph-writing --uninstall --apply
bash install_codex_yomiyasu.sh --only japanese-direct-writing --uninstall --apply
bash install_codex_yomiyasu.sh --self-test
bash install_codex_yomiyasu.sh --extract /tmp/yomiyasu-review
```

標準の解除は管理する3スキルが対象です。個別解除では`--only`を付けます。手で編集した管理ファイルや追加ファイルを検出した場合は、選択した全スキルの解除前に停止します。
バックアップは親フォルダの`.yomiyasu-installer-backups/`へ、Skill名付きのZIPで保存します。
配置・解除の切り替えが完了した後、旧一時フォルダの清掃だけに失敗した場合は、操作の完了と残ったパスを警告します。
`--doctor`は通信せず配置・ハッシュ・発動設定・既知の競合を調べます。
競合する別の校正Skillを検出しても、そのSkillを無効化しません。
`--project PATH`で競合診断の対象プロジェクトを指定できます。

自己テストは一時環境と模擬の上流応答を使います。実際の配布元への通信やモデルの文章品質は検証しません。
`--extract`は3スキルの資材を未使用または空のディレクトリへ展開します。インストールは行いません。`--self-test`と`--extract`は`--only`と併用できません。
yomiyasuの原本を通信なしで配置するには`--source-dir PATH --apply`を使えますが、
ローカルチェックアウトはスクリプトに記録された固定commitのファイルと一致する必要があります。
`--source-dir`は補助スキル単独の導入や`--update`と併用できません。
