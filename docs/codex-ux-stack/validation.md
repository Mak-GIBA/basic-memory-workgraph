# Codex UX Stack：検証範囲

[概要](README.md) · [導入手順](installation.md) · [使い方](usage.md)

## 自動チェック

~~~bash
python3 -m unittest discover -s tests -p 'test*ux*.py' -v
bash -n install_codex_ux_stack.sh
bash -n tools/codex-ux-stack/skill/scripts/gan-harness.sh
node --check tools/codex-ux-stack/skill/scripts/visual-browser.cjs
~~~

一時HOME、検証用アプリ、模擬Codexで導入・再実行・単体配布・dry-run・編集保護・設定維持・途中失敗・解除・画像検証・反復・停止・再開を確認します。
個人のSkillやMCP設定には書き込みません。模擬結果はモデルの判断品質や実ユーザーの使いやすさを証明しません。

実Chromiumの確認は明示して実行します。UX_GAN_RUNTIMEにはnpm lockfileから導入した環境を指定します。

~~~bash
UX_GAN_RUNTIME=/path/to/test-runtime \
PLAYWRIGHT_BROWSERS_PATH=/path/to/test-browsers \
python3 -m unittest discover -s tests -p 'test_ux_gan_browser.py' -v
~~~

ローカルフォームで未入力エラー、保存結果、確認ダイアログのキャンセル・承認、Mobile表示、操作前後の画像・ハッシュ、外部参照の閲覧専用制御を確認します。
環境変数がない通常のテストでは、この実ブラウザー確認だけSKIPします。テスト中に勝手にブラウザーを取得しません。

## 今回の実行結果と限界

2026-10-04にPlaywright 1.63.0と実Chromiumで操作確認を実施しました。
リポジトリ全体の通常テスト179件中176件が成功し、実ブラウザー用の3件はSKIPしました。
この3件を専用環境で別途実行し、すべて成功しました。構文、Skill形式、単体配布の再現性、文書リンクも確認済みです。
固定したVercel / ux-critiqueの原本と、配布元にあるライセンスの取得も確認しました。
標準Playwright MCPの起動も試しましたが、このホストではChromiumのOSサンドボックスが起動できませんでした。
実ブラウザーの操作確認3件は、専用ローカルPlaywright経路での結果です。

一時環境の専用Skillを実Codex CLIから呼び出すと、CodexはそのSkillを選択しました。
ただしBash実行前のサンドボックスで「bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted」が発生しました。
別の診断でもユーザー名前空間の権限エラーが発生しました。
**実Codexによる修正反復の完了と、Codex画面のGUI操作は未確認**です。権限の迂回で成功扱いにはしていません。

doctorと実行開始時には、モデル呼び出し前のサンドボックス確認を追加しました。
対応するホスト環境で実Bashの起動、類似アプリの画像、独立した修正と評価を実モデルでも確認してください。

## 配布物の再生成

~~~bash
python3 tools/codex-ux-stack/build_installer.py
~~~

同じ正本からは同じ配布物を生成します。埋め込みZIPにはSHA-256を付け、展開内容と正本の一致をテストします。
固定版の更新は[sources.json](../../tools/codex-ux-stack/sources.json)と[browser/package.json](../../tools/codex-ux-stack/browser/package.json)を編集し、
lockfileを更新してから再生成・検証します。
