# ECC MCPの再評価：最終成果まで測った導入判断

2026年10月10日の再評価では、**Context7とPlaywrightは用途を限定して使い、Chrome DevToolsは診断時に選ぶ**判断です。Sequential Thinkingの常用追加とToken Optimizerの登録は見送ります。Parallel SearchとCloudflare Docsは明示選択を維持します。現在のCodexでは、今回の課題に対象MCPを追加して正答数が増える結果は得られませんでした。

既存の初回登録候補`context7,playwright`は、文書探索と対話的な画面操作を使えるようにする運用上の選択として維持します。「精度向上を実証したので一律に使わせる」という判断ではありません。固定した採用条件は「正答を少なくとも1件増やし、退行がなく、平均時間の増加が10%以内」です。満点同士の比較はこの条件を満たさず、時間差は用途別の補助根拠として扱います。インストーラーのプレビューにも選択理由を表示し、既存接続・無効化設定・前回の選択を保持します。

## 実測結果

比較は同じ`gpt-6.1-sol/max`、同じ課題・出力形式で各条件2回行い、順序を通常→MCP、MCP→通常にしました。通常側は対象MCPを追加せず、既存のweb・shell・直接APIを使います。標準検索の`codex_apps`経路は既存ツールに含みます。MCP側は対象の実呼び出しを確認しています。異なる用途の値は合算して順位付けしません。

| 対象と主要指標 | 通常側 | MCP側 | 通常／MCPの平均秒数 | 導入判断 |
|---|---|---|---|---|
| Sequential Thinking：推論4問×2回の最終回答 | 8/8 | 8/8 | 33.271／34.975 | 正答増加なし。常用追加を見送る |
| Context7：未知URLからの文書探索・回答3問×2回 | 6/6 | 6/6 | 33.956／28.615 | 約16%短い観測。文書探索に条件付きで使う。出典不備も発生 |
| Context7：実際の生成コード、境界入力4件×2回 | 8/8 | 8/8 | 48.129／22.690 | 約53%短い観測。コードの正確さは同等 |
| Parallel Search：公開公式資料の探索2問×2回 | 4/4 | 4/4 | 21.397／30.048 | 今回の改善なし。代替検索が必要なときに選ぶ |
| Cloudflare Docs：alarm仕様1問×2回 | 2/2 | 2/2 | 15.643／34.915 | 今回の改善なし。Cloudflare用途で選ぶ |
| Playwright：複数画面の注文・障害診断2問×2回 | 4/4 | 4/4 | 69.029／42.322 | 約39%短い観測。対話的な操作に使う |
| Chrome DevTools：同じ注文・障害診断 | 4/4 | 4/4 | 78.753／47.350 | 約40%短い観測。console/network診断時に選ぶ |
| Token Optimizer：必要な5項目すべてを返す4条件×2回 | 8/8 | 6/8 | 作業全体の時間は未測定 | 新しい文脈で欠落。登録を見送る |

各値は小さな固定課題の観測です。2反復だけで一般的な速度差や統計的な優位は確定しません。推論では利益最大化・全最短経路・再試行期限・冪等処理を使いましたが、両条件とも満点になっています。主要指標は測定できており、この課題群で精度改善が観測されなかったという結論です。

workflowの秒数はモデル・ツール起動・webまたはMCP操作を含みます。ブラウザーは同じ所有済みChromeに接続し、共有起動時間は両条件の計時外です。生成コードの秒数には親の実行・採点を含みません。Token Optimizerの秒数は読取・キャッシュ再起動を前処理した後の回答モデル時間なので、全作業の短縮に使いません。課金額・人間の作業時間は測っていません。

## 同じ入力で何が変わったか

**推論の答えは同じでした。** `end+1`以上の開始時刻だけ許す8仕事の利益最大化では、両条件とも`{"profit":41,"schedules":[[1,3,5,7]]}`でした。6本ある全最短経路も両方が列挙しています。Sequential Thinkingへの検算要約の記録は成立しましたが、この試験では正答を追加せず、平均時間も短くしませんでした。[公式実装](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking)は検討項目を管理するためのもので、登録だけで別の推論モデルや独立正解判定器を追加しません。

**Context7では探索経路と所要時間が変わり、生成コードは同じでした。** ライブラリIDやURLを与えずに、Pydanticの既定値検証、HTTPXの接続プール待ち、Tenacityの待機を含む停止条件を探しました。通常側は標準検索、Context7側は`resolve-library-id`→`query-docs`を実行しました。回答はそれぞれ`validate_default`、`pool_acquire`、`stop_before_delay`で一致しました。[Context7の公式説明](https://github.com/upstash/context7)にある文書探索機能を実際に使った比較です。

生成コードも4試行とも次の実装でした。親がこのコードをネットワークなしの読み取り専用sandboxで実行し、`{}`は拒否、`{"count":"4"}`は整数4として受理、0と−1は拒否することを確認しました。[Pydantic公式文書](https://pydantic.dev/docs/validation/latest/concepts/fields/#validate-default-values)の既定値検証を使っています。

```python
from pydantic import BaseModel, Field

class Product(BaseModel):
    count: int = Field(default=0, ge=1, validate_default=True)
```

**正しい回答でも出典に欠陥がありました。** Context7はTenacityの両試行で`_autodocs/api-reference/stop-strategies.md`を引用しましたが、対応する[公式raw URL](https://raw.githubusercontent.com/jd/tenacity/main/_autodocs/api-reference/stop-strategies.md)は404でした。通常側が引用した[公式ソース](https://github.com/jd/tenacity/blob/main/doc/source/index.rst)のrawは200で、該当する説明を確認できました。GitHub閲覧URL自体はこの環境で503/504となり未確認です。回答の6/6を出典品質の6/6と読み替えません。Pydantic fieldsとHTTPX timeoutsの該当本文は取得・確認できています。

**ブラウザーは操作後の結果まで確認しました。** 単価170の商品2個に`SAVE10`を適用して注文すると、両条件とも`{"total":"306","confirmation":"order-2-SAVE10"}`を返しました。障害画面でも`{"status":503,"code":"E_CHECKOUT_RETRY"}`が一致しました。親が注文成立と診断分岐のサーバー記録を保存し、回答一致と実状態の両方を採点しています。保存した操作記録から、通常APIまたはMCPのクリック・入力・console/network取得も独立に追えます。[Playwright](https://github.com/microsoft/playwright-mcp)、[Chrome DevTools](https://github.com/ChromeDevTools/chrome-devtools-mcp)の用途に対応する実行です。

通常Playwright API側の2回目は、非同期応答の確認に失敗して操作を繰り返し、同じ注文を2件成立させていました。MCP側の2回とChrome比較の各試行は各1件でした。これは今回の具体的な操作差ですが、注文数は事前の採用指標に含めていないため、正答4/4は変更していません。「余分な副作用なく完了した」ことまで満点が保証するわけではありません。実業務の注文評価では重複件数を事前の必須条件に含める必要があります。

**Token Optimizerは文脈の条件によって結果が変わりました。** 同じ合成文書から`retry_limit=7`、`max_count=2439`、`request_id=req-6f93c1`、`error=E_CACHE_CONTEXT_29`、`guard=explicit_gate_b4`を抽出させました。全文再読は24,989バイトです。

| 条件 | Token Optimizerの返却量 | モデルの5項目回答 |
|---|---|---|
| 初回読取 | 25,064バイト | 2/2成功 |
| 前の本文をモデルへ渡した再読 | 27バイト | 2/2成功 |
| 新しい文脈・同じサーバーキャッシュ | 27バイト | `{}`、0/2成功 |
| 新しい文脈・`diffMode:false`で全文再取得 | 25,064バイト | 2/2成功 |

現在の文脈が本文を持たないのに「変更なし」だけが返ると、精度が下がりました。前の本文は明示的に入力した条件であり、実際の長い会話の保持能力を測ったものではありません。対照は全文再読で、通常側の最適なキャッシュ運用との比較ではありません。返却量削減を課金削減・一般的な推論精度改善に置き換えません。測定対象は`@ooples/token-optimizer-mcp@7.4.3`です。ECCに記載された無印`token-optimizer-mcp`へ結果を転用しません。

## 保存・再採点と実装への反映

固定した入力・正解・条件、最終回答、生成コード、操作記録、親の実行receiptは[保存データ](../../tools/ecc-on-demand/evaluation/workflows/)にあります。`check_workflows.py`はhash・実呼び出し・最終成果をオフラインで再採点します。用途別8試験、88件の回答または境界ケースの出力を確認し、異なる用途の精度は合算しません。生成コードはCLIのsandbox指定を修正して**同じ保存コードを再採点**したもので、モデルの再サンプリングではありません。

形式の曖昧さ、初期ブラウザーの起動／承認制約、採点アダプタの失敗、回答のみを採点した先行ブラウザー試験は`workflows/pilot/`に分けて保存しました。これらを本試験の精度低下やMCPの効果不合格に混ぜません。独立レビューは本試験のhash、採点、生成コードの同一性、ブラウザー操作とサーバー状態を確認しました。上記の出典欠陥、重複注文、計時範囲もそのレビューで確認した制約です。

```bash
python3 -B tools/ecc-on-demand/evaluation/check_workflows.py
bash install_codex_ecc.sh --mcps recommended
# 適用時だけ --apply。診断用は --mcps browser、不要なら --mcps none。
```

今回の再評価で対象34件すべての主要効果を測ったわけではありません。認証・専用サービス・特定プロジェクトを必要とするものは、[既存カタログの用途別判断](mcp-evaluation.md#eccカタログ34件の扱い)を維持します。通常のテストやインストールでモデル測定を自動実行せず、ローカル設定の承認範囲も広げません。
