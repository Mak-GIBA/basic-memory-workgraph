# Codex環境の導入・運用ツール集

このリポジトリ（`basic-memory-workgraph`）は、Codexでの知識の蓄積、UI/UXの設計・実装支援、
要件・設計文書の整理、GitHubでのタスク管理、根拠に基づく技術選定に使うインストーラーと運用ツールをまとめています。
必要なものを個別に選んで導入できます。5つをすべて入れる必要や、決まった導入順序はありません。

## やりたいことから選ぶ

| やりたいこと | インストーラー | 主な導入対象 | 説明 |
|---|---|---|---|
| 作業から得た知識や修正指示を次の仕事で使う | `install_basic_memory_workgraph.sh` | Basic Memory、Codex plugin、独自のWorkgraph・hooks・管理CLI | [概要と収録ツール](docs/basic-memory-workgraph/README.md) |
| UI/UXを検討し、Webアプリを作り、ブラウザーで確認する | `install_codex_ux_stack.sh` | Product Design、Build Web Apps、UIレビューSkill、Playwright MCP | [概要と収録ツール](docs/codex-ux-stack/README.md) |
| 実装前の目的・要求・設計・検証計画を整理する | `install_speckit_upstream.sh` | SpecKit CLI、独自Workbench、8つの上流工程Skill | [概要と収録ツール](docs/speckit-upstream/README.md) |
| Issue・PRを読みやすく作成し、担当・期限・進捗をGitHubで管理する | `install_codex_github_pm.sh` | 独自のGitHub Project Director Skill、読み取り専用の調査補助スクリプト | [概要と収録ツール](docs/codex-github-pm/README.md) |
| 論文・公式資料・実験を根拠に実現方式を比較する | `install_design_research.sh` | 独自のDesign Research Skill、文献調査CLI、比較・判断のテンプレート | [概要と収録ツール](docs/design-research/README.md) |

組み合わせる場合は、SpecKit Upstreamで要件と設計を整理し、UX Stackで画面を検討・実装・確認し、
GitHub Project DirectorでIssueや進捗を整理し、Workgraphで他の仕事にも役立つ知識を残す、といった使い分けができます。
これは利用例であり、インストーラー同士を自動連携する仕組みではありません。
Design Researchは方式選定の根拠と判断をまとめ、要件・設計やIssue化の材料にできます。

## はじめに

基本はLinux / WSL2のターミナルで利用します。GitHub Project DirectorとDesign ResearchはmacOSにも対応します。
Codex CLIはあらかじめ用意してください。
必要なPython・Node.jsのバージョンなどは各導入ガイドに記載しています。

```bash
git clone https://github.com/Mak-GIBA/basic-memory-workgraph.git
cd basic-memory-workgraph
```

**引数なしで実行したときの動作はインストーラーごとに異なります。**
まず必要なものの導入ガイドを開き、前提条件と変更内容を確認してください。

| 対象 | 引数なしの動作 | 導入手順 | 導入後 |
|---|---|---|---|
| Basic Memory Workgraph | 実際に導入する。Basic Memory本体の更新も試みる | [インストール・更新・解除](docs/basic-memory-workgraph/installation.md) | [使い方と設定](docs/basic-memory-workgraph/usage.md) |
| Codex UX Stack | 不足するツールを実際に導入・登録する | [インストール・更新・解除](docs/codex-ux-stack/installation.md) | [使い方](docs/codex-ux-stack/usage.md) |
| SpecKit Upstream | 導入予定を表示する。適用には`--apply`が必要 | [インストール・更新・解除](docs/speckit-upstream/installation.md) | [使い方](docs/speckit-upstream/usage.md) |
| GitHub Project Director | ユーザー共通のSkillと共通AGENTSの適用ルールを導入する。既存の導入は保持する | [インストール・更新・解除](docs/codex-github-pm/installation.md) | [使い方](docs/codex-github-pm/usage.md) |
| Design Research | ユーザー共通のSkillを実際に導入する。既存の管理対象Skillは保持する | [インストール・更新・解除](docs/design-research/installation.md) | [使い方](docs/design-research/usage.md) |

## このリポジトリで管理するもの

- 5つのインストーラーと、それぞれの導入・利用ガイド。
- Workgraphの保存方針、フック、ノートのスキーマ、更新・共有・点検用のPythonコード。
- SpecKit Upstream、GitHub Project Director、Design Researchの単一ファイル配布物。独自資材はスクリプト内に埋め込まれています。

ルートには実行するインストーラーを置き、補助コードと資材は用途別のディレクトリにまとめています。

```text
install_basic_memory_workgraph.sh   知識の蓄積・再利用
install_codex_ux_stack.sh            UI/UXの設計・実装支援
install_speckit_upstream.sh          要件・設計文書の整理
install_codex_github_pm.sh          GitHubのIssue・PR・Projects・進捗管理
install_design_research.sh          根拠に基づく実現方式・技術の比較
tools/basic-memory-workgraph/       Workgraphの補助コード・配布資材・解除スクリプト
docs/                              インストーラー別の説明
tests/                             検証コードとテスト用データ
```

Workgraphは`tools/basic-memory-workgraph/`も含むリポジトリ一式で使用します。
UX Stack、SpecKit、GitHub Project Director、Design Researchはスクリプト単体で使用できます。
個人のエディター設定（`.vscode/`）、Pythonキャッシュ、仮想環境はGit管理の対象外です。

Basic Memory、OpenAIのplugin、VercelのSkill、Playwright、SpecKit、GitHub CLI等の外部ツールは、
各提供元が管理しています。このリポジトリのインストーラーとWorkgraph／Workbench／GitHub Project Director／Design Researchの独自機能を、
それらの公式配布物と混同しないでください。ECC自体を導入するインストーラーは含みません。

[ドキュメント一覧](docs/README.md)から詳細を探せます。
開発・検証や新しいインストーラーの説明追加は、[開発ガイド](docs/development.md)を参照してください。

## 旧Workgraph READMEからの移動先

これまでトップREADMEにあったWorkgraphの説明は、以下へ移動しました。
既存の明示アンカーは、この案内に残しています。

| 旧項目 | 新しい説明 |
|---|---|
| <a id="start"></a>初回インストール | [初回インストール](docs/basic-memory-workgraph/installation.md#start) |
| <a id="python-tools"></a>Python環境の準備 | [Python環境の準備](docs/basic-memory-workgraph/installation.md#python-tools) |
| <a id="update"></a>アップデート | [アップデート](docs/basic-memory-workgraph/installation.md#update) |
| <a id="daily"></a>日常の使い方 | [日常の使い方](docs/basic-memory-workgraph/usage.md#daily) |
| <a id="modes"></a>設定を変更する | [設定を変更する](docs/basic-memory-workgraph/usage.md#modes) |
| <a id="correction-mode"></a>文脈付き修正指示の保存 | [文脈付き修正指示の保存](docs/basic-memory-workgraph/usage.md#correction-mode) |
| <a id="progressive-mode"></a>段階的なCase保存 | [段階的なCase保存](docs/basic-memory-workgraph/usage.md#progressive-mode) |
| <a id="share"></a>Memoryを共有する | [Memoryを共有する](docs/basic-memory-workgraph/sharing.md#share) |
| <a id="training"></a>学習用JSONL出力 | [学習用JSONL出力](docs/basic-memory-workgraph/sharing.md#training) |
| <a id="troubleshooting"></a>困ったとき | [困ったとき](docs/basic-memory-workgraph/troubleshooting.md#troubleshooting) |
| <a id="audit"></a>記憶の点検 | [記憶の点検](docs/basic-memory-workgraph/troubleshooting.md#audit) |
| <a id="details"></a>保存方針・配置・仕組み | [保存方針・配置・仕組み](docs/basic-memory-workgraph/reference.md#details) |
| <a id="update-details"></a>更新の詳細 | [更新の詳細](docs/basic-memory-workgraph/installation.md#update-details) |
| <a id="uninstall"></a>解除 | [解除](docs/basic-memory-workgraph/installation.md#uninstall) |
| <a id="development"></a>開発・検証 | [開発・検証](docs/development.md#development) |
