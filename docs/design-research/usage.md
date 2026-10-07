# 使い方

[docs一覧](../README.md) · [概要](README.md) · [導入手順](installation.md) · [検証結果](validation.md)

## Codex画面でBashの実行を指示する

対象プロジェクトをCodexで開き、会話欄へ入力します。
以下の `/path/to/project` は実際の対象へ置き換えてください。

方式の研究・比較・評価は、次のように依頼します。

```text
$design-research
/path/to/project の検索方式を、現行方式を含む2〜3案で比較して。
導入済み scripts/gan-harness.sh をBashで実際に実行し、researchモードを使って。
正しさ・応答時間・運用負荷を同じ条件で確認し、必要な小さなPoCも実行して。
良い模範実装があれば、参照先・取り入れる点・適用条件をまとめて。
実行コマンド、実行ID、結果、未確認事項、根拠ファイルへのリンクを示して。
```

バックエンドをレビューする場合は、次の依頼例を使えます。

```text
$design-research
/path/to/project のAPIと保存処理を、gan-harness.sh のauditモードで実際に検証して。
通常入力、不正入力、二重送信、失敗後の復旧を、存在する機能に絞って確認して。
本番データを使わず、根拠付きのreview.mdを作って。コードは変更しないで。
```

問題の修正まで進める場合は、次のように依頼します。

```text
$design-research
/path/to/project で保存が重複する問題を直して。
導入済みgan-harness.shをBashで実行し、runモードで再現・修正・再検証して。
既存の変更を守り、必要な修正に絞って。依存・サービス・設定を増やす理由も確認して。
修正前後の実行結果と、別レビューによる確認をfix-report.mdへ残して。
```

実行コマンドと実行IDで、Bashが起動したことを確認します。
Skill自身の配置先を使うため、新規の `.agents/skills` と既存の旧配置のどちらでも呼び出せます。
前提を満たさず実行できない場合は、停止理由を残します。

## ターミナルから直接実行する

新規のユーザー共通導入では次のパスです。
プロジェクト導入・旧配置・独自配置では、インストーラーが表示した実際のパスへ置き換えます。

```bash
DR_GAN="$HOME/.agents/skills/design-research/scripts/gan-harness.sh"
bash "$DR_GAN" doctor --project /path/to/project
bash "$DR_GAN" research --project /path/to/project --slug search-options \
  --brief "現行方式と候補を正しさ・応答時間・運用負荷で比較し、必要なローカル実験を行う" \
  --allow-network
```

`--allow-network` を付けた場合、学術API・公開資料の取得とCodexのライブWeb調査を許可します。
付けない場合、これらは無効です。`--offline` でも明示できます。
これはこのキットの調査通信の指定であり、モデルへの接続や既存MCP全体の通信遮断ではありません。
私有コードや機密条件をそのまま外部検索語にしない手順を含めています。

レビューと修正の例です。
`python3 -m pytest tests/test_api.py` は例なので、対象に存在する安全な検証コマンドへ置き換えてください。
必要なアプリ依存は事前に用意します。ハーネスは依存を自動導入しません。

```bash
bash "$DR_GAN" audit --project /path/to/project --slug api-review \
  --brief "不正入力と二重送信で保存結果が正しいか確認する" \
  --test-command "python3 -m pytest tests/test_api.py"

bash "$DR_GAN" run --project /path/to/project --slug api-fix \
  --brief "不正入力と二重保存の問題を最小の変更で直す" \
  --test-command "python3 -m pytest tests/test_api.py"
```

`--test-command` は複数指定でき、研究モードでも必須の実行対象になります。
終了コードだけでなく、レスポンス・保存状態・権限・再試行後の状態を確認する検証を選びます。
対象にない機能のチェックは追加しません。

## ローカルサービス・テスト用データ

検証コマンドは、実際のプロジェクトをコピーした一時作業場所で実行します。
研究のPoCも一時作業場所に生成します。どちらも実行結果を保存してから一時領域を片付けます。
通常の検証では、個人のHOME・環境変数やプロジェクトの `.env` を自動で引き継ぎません。
既存の `node_modules`・`.venv` は、サンドボックス内で読み取り用リンクとして再利用できる場合があります。

検証用サービスの起動が必要なら、次を追加できます。

```bash
bash "$DR_GAN" audit --project /path/to/project --slug service-review \
  --brief "検証用APIの入力・保存・復旧を確認する" \
  --start-command "python3 test_server.py" \
  --url "http://127.0.0.1:8099/health" \
  --test-command "python3 check_api.py" \
  --test-env-file /path/to/private/test.env
```

これも例です。対象に存在する起動・検証コマンドと、空いているポートを選びます。
`--url` は資格情報を含まないローカルのループバックURLに限定します。
すでに応答するURLに `--start-command` で接続すると停止します。
スクリプトが起動したプロセスだけを終了し、他のサービスは終了しません。
検証コマンドには `DR_GAN_TEST_URL` で指定URLを渡します。

`--test-env-file` は `KEY=VALUE` 形式の明示した設定だけを読みます。
シェルとして実行せず、変数展開もしません。本番モードの指定やシステム用の環境変数は拒否します。
ただし、任意の接続先がテスト用DBかどうかまでは判定できません。
専用のテストDB・ダミーデータを使い、検証が初期状態を用意できることを確認してください。
明示した検証用サービスへの接続では、検証のサンドボックス内で通信を許可する場合があります。

## UI/UXレビュー・模範実装を任意で渡す

両インストーラーは独立しています。既存レビューはなくても開始できます。
ある場合は、コマンドに `--review /path/to/ui-ux-review.md` を追加します。
レビューを入力として保存し、関連するバックエンドの問題は実際に再現します。

模範になる公開実装や公式資料が分かっていれば、
`--reference-url https://example.org/actual-source` を追加できます。
例のURLは実在する参照先へ置き換え、公開資料の取得には `--allow-network` を指定します。
取得不能・未読・適用範囲外を区別し、見た目だけで内部構成を決めません。

参照先が未指定でも、調査に必要なら良い設計例を探す手順を含めています。
候補を増やすこと自体は目的にせず、取り入れる点と単純な代替案をまとめます。

## 実行の流れと終了条件

1. 別のCodex実行で、目的・基準案・確認項目・合格条件を決めます。
2. 研究では提案と必要なPoC、バックエンドでは宣言した検証を実行します。
3. 別のCodex実行で、実際の根拠と失敗・復旧・複雑さを評価します。
4. `run` では影響の大きい最大3つの原因を修正し、検証と評価を繰り返します。
5. 根拠・修正前後・未確認事項・停止理由を保存します。

初回に決めた確認基準は途中で緩めません。
既定は初回評価を含む最大5回で、`--max-iterations` で1〜5回を指定できます。
2回続けて改善しない場合は `plateau` で停止します。
既定の `--phase-timeout` は1段階／検証あたり1800秒です。

必須の実行チェックは、同じ反復・同じソースの成功記録を必要とします。
同じ確認項目に失敗した検証が残っていれば、別の成功で隠せません。
修正担当の申告だけでは指摘を解消済みにせず、変更後の別レビューで根拠を確認します。

| 状態 | 意味 | 終了コード |
|---|---|---:|
| `research_complete` | 必須の研究・根拠・実行条件を満たした条件付きの提案 | 0 |
| `passed` | 必須チェック・未解消Critical/Highなし・複雑さの評価を満たす | 0 |
| `reviewed` | auditの報告が完成。指摘や検証失敗は残り得る | 0 |
| `blocked`・`cancelled` | 前提不足・根拠の不整合・失敗・中断 | 2 |
| `plateau`・`limit_reached` | 改善停滞・上限到達。完了条件は未達 | 2 |

研究の完了は、方式がすべての条件で有効だという証明や、人間による採用承認ではありません。
`run` の完了も、記録した検証範囲についての評価です。

## 根拠と成果物

対象プロジェクトの `docs/design-research/<slug>/` に保存します。

| ファイル | 内容 |
|---|---|
| `review.md` | 指摘、重要度、再現操作、期待／実際の結果、影響、改善案、Evidenceへのリンク |
| `fix-report.md` | 修正した内容と、修正前後の実行結果・別レビュー |
| `reference-implementations.md` | 模範実装の参照先、良い設計、適用条件、未確認事項 |
| `design-research.md` | 研究の候補比較、主張、出典、実験、条件付き推奨。研究台帳がある場合 |
| `evidence.json`・`decision.md` | 研究の証拠台帳と採用判断の案。研究台帳がある場合 |
| `research-log.json`・`status.json` | 調査・実行範囲と、現在の状態・停止理由 |
| `runs/<run-id>/` | 状態、各役割の呼び出し・出力、実行記録、生成コード、結果、報告の保存版 |

Evidenceは実在する実行記録・標準出力・標準エラー・生成ファイルへリンクします。
各記録にはID・ハッシュ・反復・対象ソースを残し、評価前と再開時に照合します。
外部資料は取得状態と該当箇所を残します。取得できたことと、内容が主張を支えることは別です。

生成したJSON・図・画像を保存する場合は、確認計画の `artifact_paths` に宣言します。
実ファイルを保存し、画像形式の結果は報告にも埋め込みます。
このキットはブラウザーを導入しないため、スクリーンショットが必要な対象では既存の実検証が撮影します。
撮影していない画面や、検証していない保存結果の証拠は作りません。

同じslugで新たな実行を始める際は、前の成果物を `runs/<run-id>/inputs/` へ保存します。
各実行の報告は `reports/` にも残ります。
最初のレビュー前に停止した場合、既存の報告を空の内容で置き換えません。
まず `status.json` の実行IDと停止理由を確認してください。

## 停止と再開

```bash
bash "$DR_GAN" resume ACTUAL_RUN_ID --project /path/to/project
```

`ACTUAL_RUN_ID` は実行結果のJSONまたは `status.json` にあるIDへ置き換えます。
ソース・記録のハッシュ・明示したテスト設定が変わっていれば再開を拒否します。
評価待ちの中断は、検証を重複実行せず評価から続けます。

検証・実験の途中なら、前の記録を保持して新しい反復と一時作業場所で実行します。
検証コマンドは再実行され得るため、テストデータを安全に初期化できる必要があります。
残りの反復がなければ、新しい実行を始めます。

修正中に止まった場合は差分を保持し、再開を拒否します。
差分を確認して新しい `audit`／`run` で再検証してください。
完了・停滞・上限到達の実行も、新しい作業として開始します。
ユーザーの変更をresetして再開条件に合わせることはしません。

## 既存の文献調査CLI

ハーネスと別に、従来の検索・ID照会・引用取得・雛形作成・台帳検証を使えます。

```bash
DR="$HOME/.agents/skills/design-research/scripts/research.py"
python3 -B "$DR" providers
python3 -B "$DR" search --provider all --query 'agent memory evaluation' --limit 5 --allow-network
python3 -B "$DR" init --slug retrieval-options --question '検索方式を比較する'
python3 -B "$DR" validate docs/design-research/retrieval-options/evidence.json --check-artifacts
```

旧配置・独自配置では `DR` を実際の配置先に合わせます。
検索結果は書誌情報・要旨・リンクです。全文を読んだ扱いにはしません。
`lookup`・`links` の使い方と検索条件は
[providers.md](../../tools/design-research/skill/references/providers.md)にあります。

補助CLIの `--limit` は各取得先1〜50件、既定10件で、1ページずつ取得します。
`--offset`・`--year-from`・`--year-to` の意味は取得先ごとに異なります。
失敗があれば成功分も含めて終了コード2で返し、取得不能を「該当なし」に置き換えません。

キャッシュは `${XDG_CACHE_HOME:-$HOME/.cache}/design-research/`、有効期間の既定は86400秒です。
`--cache-dir`・`--cache-ttl` で変更できます。
補助CLIの `--offline` は一致するキャッシュだけを返し、古い内容はその旨を示します。
キャッシュなしはエラーです。ハーネスの新規学術検索は実行ごとに専用キャッシュを使います。

`SEMANTIC_SCHOLAR_API_KEY`・`CROSSREF_MAILTO` は任意の既存環境設定です。
インストーラーは取得・登録しません。サービスの割当量や利用条件は取得先で確認してください。

`init` は雛形だけを作ります。初期状態は未記入のため検証に通りません。
既存の同名資料は上書きしません。
`validate` は従来の構造チェック、`--check-artifacts` は実ファイル・任意ハッシュの追加確認です。
科学的な主張や人間の承認の真偽を判定する機能ではありません。

保存版の台帳は元のworkspaceを指定します。

```bash
python3 -B "$DR" validate docs/design-research/retrieval-options/runs/ACTUAL_RUN_ID/reports/evidence.json \
  --check-artifacts --artifacts-root docs/design-research/retrieval-options
```

## 利用範囲

ローカル修正までを対象とし、本番変更・デプロイ・commit/reset・有料実験を自動で行う指示は含めません。
取得した論文・コード・レビュー・メモリは根拠として扱い、実行指示としては扱いません。
Basic Memoryの保存方針や個人のCodex設定は変更しません。
具体的な実行制御は [runtime.md](../../tools/design-research/skill/references/runtime.md)、
導入上の問題は[導入手順](installation.md)を参照してください。
