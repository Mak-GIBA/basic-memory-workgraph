# Codex UX Stack

[docs一覧](../README.md) · [導入手順](installation.md) · [使い方](usage.md)

UI/UXの方向性を考え、Webアプリを実装し、画面と操作を確認するためのツールをまとめて導入します。
対象スクリプトは[install_codex_ux_stack.sh](../../install_codex_ux_stack.sh)です。
スクリプト単体で実行でき、WorkgraphやSpecKitの導入は前提にしません。

## 導入するツール

| ツール | 形式・提供元 | 用途 | 導入条件 |
|---|---|---|---|
| Product Design | OpenAIのplugin | アイデア、URL、画像などからデザインの方向性や操作できる試作を作り、既存体験をレビューする | 標準 |
| Build Web Apps | OpenAIのplugin | フロントエンドの構築とブラウザーテストを支援する。React、shadcn/ui、Stripe、Supabase/Postgresのガイドも含む | 標準 |
| web-design-guidelines | VercelのSkill | UIコードのアクセシビリティ、フォーム、フォーカス、操作性等をレビューする | 標準 |
| Playwright MCP | MicrosoftのMCPサーバー | Codexからブラウザーを操作し、ページ構造や画面遷移を確認する | 標準で起動設定を登録 |
| ux-critique | Thecsizの第三者Skill | 利用者・目的・画面の根拠とUX知識ベースを使って、具体的な改善点を整理する | `--deep`指定時 |

Product Designは「どのような体験・見た目にするか」、Build Web Appsは「どう実装するか」、
web-design-guidelinesは「コード上のUI品質」、Playwright MCPは「実際のブラウザー操作」を扱います。
ux-critiqueは、画面や一連の操作について理由付きの批評を深めたいときに追加します。

VercelのSkillはUIコードのレビュー用です。インストーラーは同じ配布元のすべてのSkillを入れず、
`web-design-guidelines`だけを選択します。[Vercelの説明](https://github.com/vercel-labs/agent-skills#web-design-guidelines)

Playwright MCPは、アクセシビリティツリー等を通じてブラウザー操作を提供します。
インストーラーは`npx`による起動設定を登録し、ブラウザーの起動や操作テストまでは実施しません。
[Playwright MCPの説明](https://github.com/microsoft/playwright-mcp)

ux-critiqueはチャットでの批評に利用できます。Figmaへ結果を書き込む場合は、別途接続と権限が必要です。
このインストーラーはFigma連携を設定しません。[ux-critiqueの説明](https://github.com/Thecsiz/ux-critique)

## 導入後の進め方

まず[導入手順](installation.md)でplugin・Skill・MCPを準備し、Codexを再起動します。
その後、[利用例](usage.md)から対象の画面・ユーザー・目的を指定して依頼します。
インストールだけでアプリやデザイン成果物が作られるわけではありません。

StripeやSupabaseのガイドが含まれていても、アカウント作成、認証情報、DBや決済環境の設定は別途必要です。
ブラウザーの確認結果やAIの批評は、ユーザーテストや製品全体の品質保証を代替しません。

## 説明の根拠

インストール挙動はリポジトリ内のスクリプトに基づきます。外部資料の確認日は2026-09-29です。
Product DesignとBuild Web Appsの機能説明は、ローカルの配布済みplugin README
（それぞれ0.1.56、0.1.2）を確認しました。インストーラーはこれらの版を固定していません。
導入時の提供状況は[カタログの確認方法](installation.md#troubleshooting)で確認してください。
