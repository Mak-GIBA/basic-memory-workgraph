# Codex UX Stack：使い方

[概要](README.md) · [導入手順](installation.md) · [検証範囲](validation.md) · [docs一覧](../README.md)

## Codexの画面から実行する

アプリのフォルダーでCodexを開き、$ux-gan-harnessを入力して専用Skillを選びます。
URLと起動手順は、指定内容やREADME、起動済みサーバーから確認します。

~~~text
$ux-gan-harness
インストール済みのgan-harness.shを実際に起動してください。
このアプリを初見ユーザーとして画像からレビューし、
類似アプリの良い点も画像付きで比較して、修正と再確認を自動で反復してください。
専門用語を知らない人でも主要操作を迷わず完了できることを優先し、
指摘のたびに説明やボタンを増やして画面を煩雑にしないでください。
~~~

実行したコマンド、RUN_ID、処理段階を表示します。調査・修正・評価は別々のCodex実行です。
元の会話のAIが、自分のレビューに置き換える手順にはしません。

## レビューだけにする

~~~text
$ux-gan-harness
インストール済みのgan-harness.shのauditを実行してください。
画像と操作からレビューし、docs/ui-ux-review.mdに具体的な改善案をまとめてください。
今回はレビューだけで、アプリのコードは変更しないでください。
~~~

auditは画像と資料を保存し、アプリを修正しません。reviewedはレビュー作成の完了で、アプリの合格ではありません。

## ターミナルから使う

PATH・URL・コマンドを自分のプロジェクトに置き換えてください。

~~~bash
ux-gan-harness doctor --project /path/to/app
ux-gan-harness audit --project /path/to/app --url http://localhost:3000

ux-gan-harness run \
  --project /path/to/app \
  --url http://localhost:3000 \
  --start-command 'npm run dev -- --host 127.0.0.1' \
  --test-command 'npm test' \
  --test-command 'npm run build'
~~~

起動済みサーバーは再利用し、自身が起動したプレビューだけを終了します。
作成・削除の確認にはテスト用データや使い捨て環境を使います。
必須チェックを指定してください。省略時は調査役が既存のチェックを特定します。特定・完了できなければ合格にしません。

## オプションと完了条件

| オプション | 用途・既定値 |
|---|---|
| --project PATH | 対象アプリ。既定は現在のディレクトリ |
| --url URL | HTTP(S) URL。audit/runでは必須 |
| --start-command COMMAND | URLに到達できない場合の起動コマンド |
| --test-command COMMAND | 必須チェック。複数指定可 |
| --review PATH | 既存レビュー。省略時は対象アプリの最新レビュー |
| --reference-url URL | 比較候補の公式URL。複数指定可 |
| --max-iterations N | 修正反復の上限。既定5回 |
| --phase-timeout SECONDS | 各Codex実行・チェックの上限。既定1800秒 |
| --browser auto | Browser plugin → Playwright MCP →失敗を記録してローカル経路 |
| --browser local-playwright | 専用のローカル経路を明示選択 |
| --model MODEL | その実行だけCodex設定のモデルを上書き |
| --brief TEXT | 対象ユーザーや重点タスクを補足 |

画像と実操作から問題を記録し、コードは原因調査と修正に使います。
指摘を共通の原因でまとめ、1回に最大3グループを修正します。
別の評価役が、前後の画像と操作から次を確認します。

- Critical・Highが解消している。
- 必須フローがDesktop 1440×900、Tablet 768×1024、Mobile 390×844で完了できる。
- 該当するエラー・キャンセル等の状態と、4つの利用者視点で再確認した。
- 必要なテスト、画像、比較資料がある。
- 新しい重大問題や主要画面の煩雑化がない。

Medium・Lowの細部は残件として保存できます。上限到達や2回続けて改善しない場合は未達成です。
新機能追加、自動commit・reset・デプロイは行いません。

| 状態 | 意味 | 終了コード |
|---|---|---|
| reviewed | auditのレビュー作成が完了 | 0 |
| passed | runの改善条件を満たした | 0 |
| incomplete | 上限・確認不足等で条件が残る | 2 |
| stalled | 2回続けて改善しない | 2 |
| blocked | 環境不備・画像欠落・出力不正・想定外の変更等 | 1 |
| cancelled | 中断。差分・画像を保持 | 130 |

## 成果物とEvidence

| 対象アプリ内の保存先 | 内容 |
|---|---|
| docs/ui-ux-review.md | 指定11章、確認した画面・フロー数、重要度別件数、改善順 |
| docs/ui-ux-reference-apps.md | 比較画像、良い工夫、適用案、採用しない部分、出典・日付 |
| docs/ui-ux-fix-report.md | 解消した指摘の前後画像、検証、簡潔さの評価、残件 |
| docs/ui-ux-review-assets/RUN_ID/ | 役割・反復ごとのPNG |
| artifacts/ux-gan/RUN_ID/ | 状態、JSON結果、操作範囲、検証ログ、元のレビュー |

Evidenceは画像表示と相対リンク、対象UI、操作、表示幅を含みます。
PNGの実在・読み取り・サイズを検査します。ローカル経路ではブラウザーの撮影記録とハッシュを照合します。
指摘と画像の画面・フローが対応することも検査します。解消扱いには別の評価役による同じフローの結果画像が必要です。
類似アプリは公開デモを優先し、公式資料の画像は実操作と区別します。

画像はtest-results/の外に保存し、各ロールの終了時にdocsへ退避します。
元のレビューと画像、各実行のレポートも保存します。手動編集と競合した最新レポートは上書きしません。
発見した総数と、実際に確認した画面・フロー数を区別します。

## 中断と再開

~~~bash
ux-gan-harness resume 20261004T120000Z-example --project /path/to/app
~~~

RUN_IDは実際の値に置き換えます。修正後の評価が失敗した場合は、その評価から再開します。
修正自体が中断・未検証になった場合は差分を保持し、新しいaudit/runで確認します。
別の作業でソースが変わった場合は新しいaudit/runを開始します。
ハーネス同士はロックで重複実行を防ぎます。同じファイルの同時編集は確実に帰属できないため、修正中は並行編集を避けます。

## 他の収録ツール

Product Designはデザイン案や試作、Build Web Appsは実装・ブラウザー確認、
web-design-guidelinesは観察した問題のコード確認に使います。

~~~text
Product Designを使って、予約一覧の主要操作が分かりやすいデザイン案を比較してください。
~~~

~~~text
$web-design-guidelines 実画面で見つかったフォームのラベルとエラー表示について、UIコードを確認してください。
~~~

--deepで導入したux-critiqueは追加の批評に使えます。

~~~text
$ux-critique --standard
予約詳細で、初めて使う店舗スタッフが変更と取り消しを迷わず行えるかレビューしてください。
~~~

これらは別の依頼です。ハーネスの成功や、未確認部分の動作保証を意味しません。
