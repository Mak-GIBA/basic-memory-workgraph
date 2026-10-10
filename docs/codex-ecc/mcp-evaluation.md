# ECC MCPの導入判断

**追加の再評価:** 未知URLからの文書探索、生成コードの実行、注文成立・console/network診断、実モデルによる情報保持まで測った[最新の比較と導入判断](mcp-workflow-evaluation.md)を参照してください。以下は初回調査の記録です。初回の停止・測定値は書き換えず保存しています。

2026年10月10日に、現在のCodexと既存ツールを基準に調べ直しました。初回の既定追加はContext7とPlaywrightに絞り、Chrome DevTools、Parallel Search、Cloudflare Docsは用途に応じて選択します。Sequential Thinkingの一律追加とToken Optimizerの登録は見送ります。既存の接続を削除・無効化する判断ではありません。

実測値と採点コードは親側で確認しました。研究ハーネスは`producer-design`のモデル工程が1800.009秒で停止し、その研究runの独立レビューまで完了していません。runは`20261010T084640Z-9997a580`、実行は`gan-harness.sh research`（`comparison`、`effectiveness`、`--reader-friendly --allow-network`）です。以下は限定した測定に基づく導入判断であり、研究ハーネスが一般的な効果を承認したという意味ではありません。

改修後のインストーラーと保存データは、別の限定auditで確認しました。`gan-harness.sh audit --reader-friendly --offline`のrun `20261010T094238Z-8cf55dc2`は`reviewed`となり、47テスト、14課題・26組・52出力の再採点、説明の範囲の独立レビューが成功しています。これは保存記録と設定管理の検証であり、外部モデルを再測定した結果ではありません。[限定auditのレポート](../design-research/ecc-mcp-installer-validation/report.md)に実行記録を残しています。

既定2件は文書探索と対話的な画面確認に使う接続です。今回の少数課題で、MCPを使えば正答率が上がるという結果は得られませんでした。既存手段で十分な作業には、その手段を使えます。選択方法は[インストール手順](installation.md)を参照してください。

## 最終出力の比較

| 対象・同じ課題での比較 | MCPなし | MCPあり | 判断 |
|---|---|---|---|
| Sequential Thinking：推論6問×2回 | 12/12正答、平均29.176秒 | 12/12正答、平均51.7875秒 | 正答増加なし、時間は約77.5%増。常用の採用条件を満たさない |
| Context7：文書を使う解釈2問 | 公式文書直接取得で2/2正答 | Context7取得文書で2/2正答 | 既知URLの課題では精度改善なし。文書探索の接続として使う |
| Token Optimizer：重要値の取得4ケース×2回 | 8/8で5項目を取得 | 6/8。新しい会話の2回で全項目を取得できず | 一律導入を見送り。再読だけの返却量削減を一般効果へ広げない |
| Playwright MCP：HTML操作2ケース×2回 | Playwright APIで4/4のDOM値が正しい | 4/4のDOM値が正しい | 対話的な操作に使う。固定テストの速度改善は主張しない |
| Chrome DevTools MCP：同じHTML操作 | Playwright APIで4/4 | 4/4 | console・network・性能診断が必要な場合に選ぶ。診断精度の効果比較は別途必要 |

推論は同じモデル`gpt-6.1-sol`、同じ推論設定`max`、同じ入力と出力形式で順番を入れ替えて測りました。MCP条件では実際の呼び出しが各試行3回成立しています。時間は起動・モデル処理・MCP操作を含む実行時間で、人間の作業時間ではありません。6問は両条件とも満点になったため、難しい課題での差や一般的な性能差までは判断できません。

Context7の文書解釈は各条件1試行です。モデル処理は8.694秒対11.902秒、文書取得は0.071秒対7.682秒でした。既知URLを直接取得する基準案が有利な設定であり、未知のライブラリ文書を探す作業の時間差には使えません。ブラウザーは通常APIのfill/clickとMCPのDOM評価を比べています。通常APIはブラウザー起動後から計時し、MCPの最初の操作にはブラウザー起動が含まれるため、操作内容と起動費用の計測範囲に差があります。正しい最終DOM値は確認できますが、一般的な操作速度の比率にはしません。

Token Optimizerは決定的な抽出器で必要情報の取得を測っています。モデルの推論精度や課金額は測っていません。同じ会話で過去の本文を保持している再読では、通常取得の63,481バイトに対して27バイトで重要値を保てました。過去の本文がない新しい会話では、この削減が情報欠落になりました。

## 同じ入力の出力例

Requestsの`timeout=(3.05, 27)`が全ダウンロードの期限かを問うと、直接取得とContext7の両方で`{"connect_read_pair": true, "total_download_deadline": false}`でした。今回の問いでは答えが改善したわけではありません。Context7は、ライブラリの識別・文書取得をMCPから行える経路を追加します。

63,481バイトの同じ合成文書から、`retry_limit=3`、`max_count=1700`、`request_id=req-01731`、`error=E_CONFLICT`、`guard=approval_required`を取り出す課題では、通常取得は新しい会話でも5項目を返しました。共有キャッシュを使うToken Optimizerは`{"content":"// No changes"}`だけを返し、抽出結果は`{}`でした。`diffMode:false`で全文を取り直すと5項目を回復できました。サーバーが読んだ履歴と、現在の会話が本文を持っていることを同一視できない例です。

単価170・数量11を設定するローカルHTMLでは、通常API、Playwright MCP、Chrome DevTools MCPのすべてが`1870`を返しました。MCPによる精度向上の例ではなく、Codexからブラウザーを操作できる経路の動作例です。[Playwrightの公式説明](https://github.com/microsoft/playwright-mcp)も、CLIの効率とMCPの継続的・探索的な利用を用途によって分けています。

## ECCカタログ34件の扱い

| 分類 | 対象 | 今回の扱い |
|---|---|---|
| 文書・画面操作 | `context7`、`playwright` | 初回の既定。用途による接続上の価値で選択 |
| 公開検索・文書 | `parallel-search`、`cloudflare-docs` | 選択式。公開検索の動作を確認。モデル精度改善の測定とは区別 |
| 検討の整理 | `sequential-thinking` | 明示指定のみ。今回の常用採用条件は未達 |
| 返却量の削減 | `token-optimizer` | 登録見送り。新しい会話での情報欠落を再現 |
| GitHub | `github` | 既存の公式連携または`gh`を使う。重複登録を見送り |
| 記憶・履歴 | `ecc-memory-vault`、`memory`、`omega-memory`、`longhand`、`memxus` | 既存Basic Memoryとの役割を整理するまで追加しない。履歴の索引化も今回の依頼には含めない |
| ローカルファイル | `filesystem` | 現在のCLIでは既存のファイル操作を使う。対象ルートを必要とする別クライアントで再検討 |
| 業務・配備・データ | `jira`、`confluence`、`supabase`、`vercel`、`railway`、`clickhouse`、`cloudflare-workers-builds`、`cloudflare-workers-bindings`、`cloudflare-observability` | 対象プロジェクトと認証が決まったときに検討。現在は既定追加しない |
| 外部検索・ブラウザー | `firecrawl`、`exa-web-search`、`browserbase`、`browser-use` | 既存の検索とローカルブラウザーで不足する要件が生じた場合に検討 |
| 専用サービス | `ito-compute`、`codescene`、`magic`、`fal-ai`、`laraplugins` | 計算・解析・UI・画像・Laravel等の対象用途と接続条件を決めてから検討 |
| 代理・作業管理・評価 | `nexus`、`devfleet`、`evalview` | 既存のCodex・実行管理・評価との接続目的を決めてから検討。登録だけでモデル変更や品質向上が起きるとは扱わない |

Chrome DevToolsはこの34件のJSONカタログとは別の候補として確認しました。必要なときに`browser`で選べます。後半のサービス群は今回、同じ条件での主要効果を測っていません。効果がないという判断ではなく、対象用途がない状態での一律追加を見送っています。

[Sequential Thinkingの公式実装](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking)は入力された検討項目を管理するもので、登録だけで別モデルや正解判定器を追加するものではありません。[Context7](https://github.com/upstash/context7)は文書検索経路を提供します。[Chrome DevTools](https://github.com/ChromeDevTools/chrome-devtools-mcp)の診断機能は用途限定の根拠ですが、今回のDOM課題から性能診断の品質向上は推定しません。

## バージョンと検証範囲

測定したバージョンはSequential Thinking `2026.8.31`、Context7 `4.3.0`、Playwright MCP `0.0.83`、Chrome DevTools MCP `1.10.1`、Token Optimizer `@ooples/token-optimizer-mcp@7.4.3`です。[Token Optimizerの配布元](https://github.com/ooples/token-optimizer-mcp)のscopedパッケージと、ECCカタログに記載された無印`token-optimizer-mcp`を区別しました。無印パッケージへ今回の結果を転用しません。版や会話管理の仕様が変われば再検証が必要です。

測定準備で起きた未呼び出し、古いツール名・pageIdの指定、DOMのtextContentを関数として扱った誤りは`evidence/pilot/`に残し、本試験と分けました。前回の調査が停止した原因は、モデル工程の600秒上限、依存ディレクトリのsymlinkによるexit 127、レビュー記録の不整合です。これらをMCPの精度低下や性能失敗とは扱いません。

計測コード、固定入力と正解、実出力は[測定資材](../../tools/ecc-on-demand/evaluation/README.md)にあります。モデル測定は利用量を消費する明示的な処理であり、インストーラーや通常のテストでは実行しません。親側の`check_captures.py`は取得済み実測値の再採点で、外部モデルの再サンプリングとは異なります。研究ハーネス内の実験は0件で停止しました。実行状態は[ハーネスのレポート](../design-research/ecc-mcp-benefits/report.md)に記録されています。
