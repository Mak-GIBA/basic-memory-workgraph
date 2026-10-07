# Codex UX Stack

[docs一覧](../README.md) · [導入手順](installation.md) · [使い方](usage.md) · [検証範囲](validation.md)

Webアプリの画面と操作をOOUIから設計し、認知負荷、機能、表示、実操作を確認するスキルとツールを導入します。
入口は[install_codex_ux_stack.sh](../../install_codex_ux_stack.sh)です。スクリプト単体で使え、WorkgraphやSpecKitは前提にしません。

## 導入するもの

| ツール | 提供元・形式 | 用途 | 条件 |
|---|---|---|---|
| ooui-design | このリポジトリのSkill・参照資料 | 対象・画面・操作の設計、認知負荷の29項目、実装と確認への引き継ぎ | 標準 |
| UI/UX GAN Harness | このリポジトリのBash・Python・Skill | 画像付きレビュー、類似アプリ比較、修正、独立した再確認 | 標準 |
| Product Design | OpenAIのplugin | デザイン案、試作、既存体験のレビュー | 標準 |
| Build Web Apps | OpenAIのplugin | フロントエンドの構築とブラウザーテスト | 標準 |
| web-design-guidelines | VercelのSkill | 観察した問題についてUIコードの品質を確認 | 標準 |
| Playwright MCP | MicrosoftのMCP | Codexからブラウザーを操作 | 標準 |
| ローカルPlaywright | Microsoftのライブラリと専用アダプター | 通常の経路が使えない場合に操作前後の画像を記録 | 標準 |
| ux-critique | Thecsizの第三者Skill | UX知識ベースを使った詳細な批評 | --deep |
| yomiyasu | 別配布の日本語推敲Skill | 日本語UI文言の下書きの確認 | 利用を推奨。UX Stackからは導入しない |

新規アプリでは、**OOUI設計 → デザイン・実装 → ブラウザー検証**の順で進めます。
ooui-designで利用者、対象、属性、関係、一覧と詳細、操作、状態保持を整理し、短い設計メモを
Product Design / Build Web Appsへ渡します。画像生成や実装にも必須機能と情報の優先順位を引き継ぎます。

検索、一括操作、対象が固定の操作、意味のあるウィザードは、利用者の目的に応じて使い分けます。
「主要目的を明確にする」を操作の制限にせず、情報を隠すことで増える探索や往復も見ます。
日本語のラベルや説明は、利用可能ならyomiyasuで意味を保って確認することを推奨します。
未導入の場合は[別インストーラー](../codex-yomiyasu/installation.md)を利用できます。

[ECCの反復構成](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/scripts/gan-harness.sh)を参考にした、既存アプリ向けの独自実装です。
モデルの学習ではなく、調査・修正・評価を別のCodex実行に分けます。

利用者は案件の指定を優先し、初見・誤操作・急いでいる・説明を読まない視点も補助に使います。
必要な情報と操作を保ち、情報整理、重複削除、操作の統合、文言の置き換えから改善案を検討します。
修正後は手順、判断する箇所、Mobileの情報量を見直します。指摘には画像、解消した指摘には修正前後の画像を付けます。
類似アプリは原則3候補を探し、公開画面や公式の画像から良い工夫と適用案を比較します。

## 最初の操作

新規設計・実装では、導入後にCodexで次のように指定します。

~~~text
$ooui-design
このアプリを、利用者が扱う対象から設計して実装してください。
画面と操作の関係を整理してからデザインし、必須機能と状態保持をブラウザーで確認してください。
日本語UIの文言には利用可能なyomiyasuを使うことを推奨します。
~~~

実装済みアプリのレビューと修正反復では、次のように指定します。

~~~text
$ux-gan-harness
インストール済みのgan-harness.shを実際に起動し、このアプリを画像でレビューして、
初見ユーザーが迷わず使えるよう修正と再確認を反復してください。
説明やボタンを増やしすぎず、主要操作の分かりやすさを優先してください。
~~~

レビューだけなら「コードを変更しない」と指定します。詳しくは[使い方](usage.md)を参照してください。
インストールだけではアプリは修正されません。対象アプリ、URL、テスト環境を指定して実行した段階で始まります。
AIによる評価と人間のユーザーテストは別です。[検証範囲と制限](validation.md)

## 設計資料

[エムニの記事](https://zenn.dev/emuni/articles/ooui-agent-skill)を手順と検証範囲、
[スターフェスティバルの記事](https://zenn.dev/stafes_blog/articles/shota1995m-ooui)を使い分けの参考にし、
[OOUIの一次資料](https://www.sociomedia.co.jp/7279)と、提供されたUI/UX設計Tipsも参照しています。
29項目の設計・確認・例外は[認知負荷のTips](../../tools/codex-ux-stack/ooui-design/references/cognitive-load.md)へ整理しています。
独自に整理した[参照資料と出典](../../tools/codex-ux-stack/ooui-design/references/sources.md)を同梱しているため、
インストールや通常の利用に記事への接続は必要ありません。OOUIの構造と、機能・表示・操作の完成度は別々に確認します。
