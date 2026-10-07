# Codex UX Stack

[docs一覧](../README.md) · [導入手順](installation.md) · [使い方](usage.md) · [検証範囲](validation.md)

Webアプリを初見ユーザーの視点で画像からレビューし、主要操作の改善と再確認を反復するツールを導入します。
入口は[install_codex_ux_stack.sh](../../install_codex_ux_stack.sh)です。スクリプト単体で使え、WorkgraphやSpecKitは前提にしません。

## 導入するもの

| ツール | 提供元・形式 | 用途 | 条件 |
|---|---|---|---|
| UI/UX GAN Harness | このリポジトリのBash・Python・Skill | 画像付きレビュー、類似アプリ比較、修正、独立した再確認 | 標準 |
| Product Design | OpenAIのplugin | デザイン案、試作、既存体験のレビュー | 標準 |
| Build Web Apps | OpenAIのplugin | フロントエンドの構築とブラウザーテスト | 標準 |
| web-design-guidelines | VercelのSkill | 観察した問題についてUIコードの品質を確認 | 標準 |
| Playwright MCP | MicrosoftのMCP | Codexからブラウザーを操作 | 標準 |
| ローカルPlaywright | Microsoftのライブラリと専用アダプター | 通常の経路が使えない場合に操作前後の画像を記録 | 標準 |
| ux-critique | Thecsizの第三者Skill | UX知識ベースを使った詳細な批評 | --deep |

[ECCの反復構成](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/scripts/gan-harness.sh)を参考にした、既存アプリ向けの独自実装です。
モデルの学習ではなく、調査・修正・評価を別のCodex実行に分けます。

「このサービスを知らず、ITや業務の知識が少ない人にも、次の操作・結果・戻り方が分かるか」を確認します。
説明やボタンの追加より、情報整理、重複削除、操作の統合、文言の置き換えを優先します。
修正後は手順、判断する箇所、Mobileの情報量を見直します。指摘には画像、解消した指摘には修正前後の画像を付けます。
類似アプリは原則3候補を探し、公開画面や公式の画像から良い工夫と適用案を比較します。

## 最初の操作

導入後、Codexで専用スキルを指定します。

~~~text
$ux-gan-harness
インストール済みのgan-harness.shを実際に起動し、このアプリを画像でレビューして、
初見ユーザーが迷わず使えるよう修正と再確認を反復してください。
説明やボタンを増やしすぎず、主要操作の分かりやすさを優先してください。
~~~

レビューだけなら「コードを変更しない」と指定します。詳しくは[使い方](usage.md)を参照してください。
インストールだけではアプリは修正されません。対象アプリ、URL、テスト環境を指定して実行した段階で始まります。
AIによる評価と人間のユーザーテストは別です。[検証範囲と制限](validation.md)
