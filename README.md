# Codex環境の導入・運用ツール集

このリポジトリ（`basic-memory-workgraph`）は、Codexでの知識の蓄積、UI/UXの設計・実装支援、
要件・設計文書の整理、GitHubでのタスク管理、技術選定、文書編集、日本語の段落構成・推敲に使うインストーラーと運用ツールをまとめています。
ECCのスキルを必要なときに読む構成や、作業ディレクトリからHerdrを開く設定も用意しています。
全ツールを一括導入するか、必要なものを選んで導入できます。すべてを入れる必要はありません。

## やりたいことから選ぶ

| やりたいこと | インストーラー | 主な導入対象 | 説明 |
|---|---|---|---|
| 作業から得た知識や修正指示を次の仕事で使う | `install_basic_memory_workgraph.sh` | Basic Memory、Codex plugin、独自のWorkgraph・hooks・管理CLI | [概要と収録ツール](docs/basic-memory-workgraph/README.md) |
| OOUIから画面と操作を設計し、実装・画像付き検証・改善を進める | `install_codex_ux_stack.sh` | ooui-design、認知負荷の参照資料、UI/UX GAN Harness、Product Design、Build Web Apps、UIレビューSkill、Playwright | [概要と収録ツール](docs/codex-ux-stack/README.md) |
| ストーリーから要件・方式研究・全体設計・検証計画を整理する | `install_speckit_upstream.sh` | SpecKit CLI、独自Workbench、8つの上流工程Skill | [概要と収録ツール](docs/speckit-upstream/README.md) |
| Issue・PRを読みやすく作成し、担当・期限・進捗をGitHubで管理する | `install_codex_github_pm.sh` | 独自のGitHub Project Director Skill、読み取り専用の調査補助スクリプト | [概要と収録ツール](docs/codex-github-pm/README.md) |
| 目的に貢献するコアロジックの方式を比較・検証・改善する | `install_design_research.sh` | 単一入口のDesign Research Skill、テーマ別研究・再評価、Bashハーネス、文献調査CLI | [概要と収録ツール](docs/design-research/README.md) |
| ECCの原本を保持し、必要なスキルだけ参照する | `install_codex_ecc.sh` | ECC標準プラグイン、入口4件、適用・更新・復元用の管理CLI | [概要と収録ツール](docs/codex-ecc/README.md) |
| PDF・Word・PowerPointを読み、原本を保護して編集する | `install_codex_office.sh` | OfficeCLI、文書処理ライブラリ、Office Workbench Skill・CLI | [概要と収録ツール](docs/codex-office/README.md) |
| 日本語の説明・仕様・報告を意味を保って整える | `install_codex_yomiyasu.sh` | yomiyasu原本、paragraph-writing、japanese-direct-writing、Codex用の入口、ローカル検査ツール | [概要と収録ツール](docs/codex-yomiyasu/README.md) |
| 作業ディレクトリに対応するターミナルworkspaceを開く | `install_herdr.sh` | Herdr、`herdr-open`、Bashの呼び出し設定 | [概要と収録ツール](docs/herdr/README.md) |

システム全体を整理する入口は`$upstream-new`・`$upstream-change`、特定の方式を研究する入口は`$design-research`です。
Codexで対象プロジェクトを開き、目的を短く伝えます。

```text
$upstream-new 社内文書を検索し、根拠を確認して回答できるアプリを作りたい。
```

```text
$design-research このプロジェクトの検索精度を改善する方法を調べて。
```

Upstream 2.0.5がストーリー・懸念・ユースケース・要件を整理し、Design Research 2.4.0がコアロジックの問いをテーマ別に比較・検証します。
Upstreamは研究結果の組合せと全体制約を確認し、設計・検証計画へ反映します。その後、レビューと明示承認へ進みます。
「計画だけ」の依頼は計画で止まり、研究の状況確認では実験を開始しません。研究完了と採用承認、アプリ実装は別の段階です。
[一連の使い方](docs/speckit-upstream/usage.md)と[テーマ分割・既存判断の見直し](docs/speckit-upstream/reassessment.md)に具体例があります。

UX Stackで画面を設計・確認し、GitHub Project DirectorでIssueや進捗を整理し、Workgraphへ後の仕事に役立つ知識を残すこともできます。
各キットは別途導入し、利用時の依頼と許可の範囲で使います。
Design ResearchとUX Stackはそれぞれ単独でも利用でき、既存のUI/UXレビューは任意で研究へ渡せます。

## はじめに

基本はLinux / WSL2のターミナルで利用します。GitHub Project DirectorとDesign ResearchはmacOSにも対応します。
Codex用のツールを使う場合は、Codex CLIをあらかじめ用意してください。
HerdrはCodexから独立して使えます。OSへの対応範囲は各ガイドで確認してください。
必要なPython・Node.jsのバージョンなどは各導入ガイドに記載しています。

```bash
git clone https://github.com/Mak-GIBA/basic-memory-workgraph.git
cd basic-memory-workgraph
```

全9ツールの標準導入は、[一括インストーラー](docs/installation.md)から実行できます。
引数なしでは予定を表示し、`--apply`を付けると導入します。個別選択にも対応します。
実行前に、導入ガイドで前提条件と変更範囲を確認してください。

```bash
bash install_all.sh --list
bash install_all.sh --dry-run
bash install_all.sh --apply
```

UI/UX設計と日本語の推敲だけを導入する例です。

```bash
bash install_all.sh --only ux-stack,yomiyasu --apply
```

**各ツールの個別インストーラーは、引数なしで実行したときの動作が異なります。**
まず必要なものの導入ガイドを開き、前提条件と変更内容を確認してください。

| 対象 | 引数なしの動作 | 導入手順 | 導入後 |
|---|---|---|---|
| Basic Memory Workgraph | 実際に導入する。Basic Memory本体の更新も試みる | [インストール・更新・解除](docs/basic-memory-workgraph/installation.md) | [使い方と設定](docs/basic-memory-workgraph/usage.md) |
| Codex UX Stack | 不足するツールを実際に導入・登録する | [インストール・更新・解除](docs/codex-ux-stack/installation.md) | [使い方](docs/codex-ux-stack/usage.md) |
| SpecKit Upstream | 通信せず組み立て予定を表示する。組み立て・導入には`--apply`が必要 | [インストール・更新・解除](docs/speckit-upstream/installation.md) | [使い方](docs/speckit-upstream/usage.md) |
| GitHub Project Director | ユーザー共通のSkillと共通AGENTSの適用ルールを導入する。既存の導入は保持する | [インストール・更新・解除](docs/codex-github-pm/installation.md) | [使い方](docs/codex-github-pm/usage.md) |
| Design Research | 固定版から組み立て・検証後にSkillを導入する。既存の管理対象Skillは保持する | [インストール・更新・解除](docs/design-research/installation.md) | [使い方](docs/design-research/usage.md) |
| Codex ECC | 通信せず予定を表示する。導入・設定には`--apply`が必要 | [インストール・更新・復元](docs/codex-ecc/installation.md) | [使い方](docs/codex-ecc/usage.md) |
| Office Workbench | 導入予定を表示する。実行には`--apply`が必要 | [インストール・更新・解除](docs/codex-office/installation.md) | [使い方](docs/codex-office/usage.md) |
| yomiyasu | 導入予定を表示する。実行には`--apply`が必要 | [インストール・更新・解除](docs/codex-yomiyasu/installation.md) | [使い方](docs/codex-yomiyasu/usage.md) |
| Herdr | 不足するHerdrを導入し、Bash設定を変更する。予定表示は`--dry-run` | [インストールとBash設定](docs/herdr/installation.md) | [使い方](docs/herdr/usage.md) |

## このリポジトリで管理するもの

- 用途別のインストーラーと、それぞれの導入・利用ガイド。
- Workgraphの保存方針、フック、ノートのスキーマ、更新・共有・点検用のPythonコード。
- UX Stack、GitHub Project Director、Office Workbench、yomiyasuの単一ファイル配布物。独自資材はスクリプト内に埋め込まれています。
- Design Research 2.4.0とUpstream 2.0.5の組み立て用スクリプト。内蔵の更新資材を、取得・照合した固定版へ適用します。

ルートには実行するインストーラーを置き、補助コードと資材は用途別のディレクトリにまとめています。

```text
install_all.sh                     全9ツールの一括導入・個別選択
install_basic_memory_workgraph.sh   知識の蓄積・再利用
install_codex_ux_stack.sh            UI/UXの設計・実装支援
install_speckit_upstream.sh          要件・設計文書の整理
install_codex_github_pm.sh          GitHubのIssue・PR・Projects・進捗管理
install_design_research.sh          コアロジックの方式比較・実測と改善
install_codex_ecc.sh                ECC導入と必要なときに読む入口4件の設定
install_codex_office.sh             PDF・Word・PowerPointの閲覧・編集
install_codex_yomiyasu.sh           日本語の段落構成・推敲・不要な留意書きの点検
install_herdr.sh                   作業ディレクトリに対応するHerdrの起動
tools/basic-memory-workgraph/       Workgraphの補助コード・配布資材・解除スクリプト
tools/ecc-on-demand/               ECCの管理CLI・入口資材・導入処理
tools/speckit-upstream/            固定版ベースの上流整理・承認・任意移行の実装
tools/design-research/             固定版ベースの報告書・ハーネス・導入処理
tools/codex-ux-stack/              OOUI設計・認知負荷の資料・画像付きレビュー・単体配布の正本
docs/                              インストーラー別の説明
tests/                             検証コードとテスト用データ
```

一括インストーラーはリポジトリ一式で使用し、各ツールの個別インストーラーを呼び出します。
Workgraphは`tools/basic-memory-workgraph/`も含むリポジトリ一式で使用します。
Codex ECCも`tools/ecc-on-demand/`を含むリポジトリ一式で使用します。
UX Stack、SpecKit、GitHub Project Director、Design Research、Office Workbench、yomiyasu、Herdrはスクリプト単体で使用できます。
Design ResearchとUpstreamは通常の組み立てで通信します。オフラインでは固定版の元スクリプト2本が必要です。
`tools/design-research/`・`tools/speckit-upstream/`だけでは新版全体を再生成できません。[組み立て版の保守](docs/development.md#speckitの埋め込み資料)
2026-10-10に組み立ての停止原因を修正し、両ツールの組み立て・自己テストと、このPCでの更新・診断を確認しました。[現在の検証範囲](docs/design-research/validation.md)
個人のエディター設定（`.vscode/`）、Pythonキャッシュ、仮想環境はGit管理の対象外です。

Basic Memory、OpenAIのplugin、VercelのSkill、Playwright、SpecKit、GitHub CLI等の外部ツールは、
各提供元が管理しています。このリポジトリのインストーラーとWorkgraph／Workbench／GitHub Project Director／Design Researchの独自機能を、
それらの公式配布物と混同しないでください。ECCの原本はCodex標準のプラグイン機能で導入します。

ECC導入済みの環境では、[ECCを必要なときに読む](docs/ecc-on-demand.md)の管理CLIで、
原本を保持したまま常設スキルを4つの入口に絞れます。

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
