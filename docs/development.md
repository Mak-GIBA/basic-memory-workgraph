# 開発・検証とドキュメントの追加

[docs一覧](README.md) · [リポジトリ概要](../README.md)

## ソースと資材の配置

ルートには`install_*.sh`を置き、補助コード・配布資材・解除スクリプトは
`tools/<installer-id>/`にまとめます。説明は`docs/<installer-id>/`、検証は`tests/`に置きます。
単一ファイルで動くインストーラーに、空の補助ディレクトリを作る必要はありません。
全ツールの共通入口は`install_all.sh`、導入ガイドは`docs/installation.md`です。

Design Research 2.4.0とUpstream 2.0.5は組み立て用の配布物です。
固定版ベースの`tools/`と、配布スクリプトが内蔵する更新資材を分けて確認します。
現在の`tools/design-research/`・`tools/speckit-upstream/`だけを新版全体の正本として扱わないでください。

新版の更新元は`tools/design-research-upgrade/`です。固定版へ順に変更を適用し、
最終overlayからSkill・ハーネス・評価契約を組み立てます。埋め込み配布物は次で再生成・照合します。

```bash
python3 -B tools/design-research-upgrade/build_bootstraps.py
python3 -B tools/design-research-upgrade/build_bootstraps.py --check
bash install_design_research.sh --bundle-self-test
```

`--base-dir`に指定コミットの元インストーラー2本を用意すれば、`--offline --build-only`で通信せず
両配布物を組み立てて検証できます。新しい評価契約の試験は同梱testsの中にあり、
組み立て時は最終ソースに対して実行します。実モデルの品質検査はこの機械検査とは別です。

WorkgraphのPythonコード、hooks、保存方針、テンプレート、スキーマ履歴、依存一覧は
`tools/basic-memory-workgraph/`にあります。旧スキーマ履歴とハッシュは更新判定で使うため、Git管理を維持します。
補助コードは作業ディレクトリではなく、自身のファイル位置を基準に資材を参照します。

リポジトリ内の補助CLIを直接使う場合も、新しいパスを指定してください。

```bash
python3 tools/basic-memory-workgraph/workgraph_tools.py --help
```

旧ルートの補助CLI用ラッパーはありません。導入済みユーザー環境の配置とコマンドは変更していません。
`.vscode/`は個人のエディター設定として除外し、Pythonキャッシュ・バイトコード・仮想環境もGit管理しません。

<a id="development"></a>

## 開発・検証

[Python環境](basic-memory-workgraph/installation.md#python-tools)を用意し、リポジトリで実行します。

```bash
python3 -m unittest discover -s tests -v
bash -n install_all.sh
bash -n install_basic_memory_workgraph.sh
bash -n install_codex_ux_stack.sh
bash -n install_speckit_upstream.sh
bash -n install_codex_github_pm.sh
bash -n install_design_research.sh
bash -n install_codex_ecc.sh
bash -n install_codex_office.sh
bash -n install_codex_yomiyasu.sh
bash -n install_herdr.sh
bash -n tools/basic-memory-workgraph/remove_workgraph_hooks.sh
```

テストは一時ディレクトリと架空の事例を使用します。実際の個人MemoryやSkillへは書き込みません。
設定維持、スキーマ移行、保存モード、共有境界、JSONLの情報保持、importの衝突、Skill登録の保護、
更新のdry-run・再実行・失敗時の復元などを確認します。外部パッケージ導入はモックで検証します。
意味内容の判断例は[tests/POLICY_SCENARIOS.md](../tests/POLICY_SCENARIOS.md)にあります。
機械テストは、実際の会話に対する抽象化品質やCreatorレビューの正しさを証明するものではありません。

リリース時は、変更前の配布済みテンプレートを `tools/basic-memory-workgraph/schema-history/<version>/` に残してから
現行テンプレートを変更します。更新処理はこの履歴を使い、実行時にGitやネットワークから取得しません。
policy変更はリポジトリの `tools/basic-memory-workgraph/memory-policy.md` を編集し、`--configure-only` または `--update` で反映します。

## インストーラーごとの検証範囲

| 対象 | 検証方法 | 分かること・制限 |
|---|---|---|
| 一括インストーラー | `python3 -m unittest discover -s tests -p 'test_install_all.py' -v`、Bash構文確認 | 一時HOMEと模擬インストーラーで全9ツール・個別選択・予定表示・設定保持の更新経路・失敗集計・中断を確認。実取得や全ツールの連続導入は含まない |
| Workgraph | 上記のPythonテスト | 設定、保存形式、共有、更新等のローカル処理。実際の外部パッケージ導入は含まない |
| UX Stack | Pythonテスト、Skill・配布物の検査、任意の実Chromiumチェック | OOUI資料の標準導入・更新・共有、編集保護、反復・停止、関連移動と状態保持、画像管理を一時環境で確認。実モデル反復の完了とGUI呼び出しは未確認。[検証範囲](codex-ux-stack/validation.md) |
| SpecKit Upstream | `bash install_speckit_upstream.sh --bundle-self-test`、固定版からの組み立てと内蔵試験 | 同梱契約試験と組み立て後の本体試験を区別する。組み立て・内蔵166件と、このPCでの更新・診断を確認。[検証結果](design-research/validation.md) |
| GitHub Project Director | `bash install_codex_github_pm.sh --self-test` | 一時環境での導入・更新・解除、読み取り補助、Skillの静的な指示内容を検証。実GitHubへの書き込みやモデルの出力品質を保証しない |
| Design Research | `bash install_design_research.sh --bundle-self-test`、固定版からの組み立てと内蔵試験 | 両配布物に同じ更新資材を内蔵。2.4.0の同梱287件と組み立て・更新・診断を確認。実モデルの検証範囲は[検証結果](design-research/validation.md)を参照 |
| Codex ECC | `python3 -m unittest discover -s tests -p 'test*ecc*.py' -v`、Bash構文確認 | 模擬Codexによる新規導入、既存再利用、更新失敗・再実行、復元、設定維持と原本取得。新規環境への実ダウンロードは別途確認が必要 |
| Office Workbench | `bash install_codex_office.sh --self-test` | 一時環境で導入・編集保護・文書処理を検証。通信・Codexは模擬し、実PDFライブラリがない対象はSKIP。実OfficeCLIや描画のE2E確認は別途必要 |
| yomiyasuと補助Skill | `bash install_codex_yomiyasu.sh --self-test` | 一時HOME・作業ディレクトリと模擬上流で3スキルの導入・更新・解除・検査を確認。配布元への実通信やモデルの文章品質は検証しない |
| Herdr | `python3 -m unittest discover -s tests -p 'test_install_herdr.py' -v` | 一時HOMEで取得・Bash設定・workspace照合・再実行を検証。実ダウンロードや実セッションの起動は含まない |

リポジトリの既存テストには、2.0.1系の通常インストーラーを前提とするDesign Research・Upstreamの検査があります。
新版の組み立て用スクリプトに、そのまま従来の再生成一致検査を適用しません。
固定版の試験、更新資材の試験、組み立て後の試験、実モデルの動作確認を分けます。

構文確認や文書レビューのためにインストーラーの通常実行を行わないでください。
Workgraph、UX Stack、GitHub Project Director、Design Research、Herdrは引数なしで実際に導入します。
UX Stack、SpecKit、GitHub Project Director、Design Research、Office Workbench、yomiyasuの`--extract`もファイルを書き込む操作です。
Design ResearchとUpstreamの`--extract-bundle`は通信なしで展開し、`--extract`・`--doctor`・`--self-test`は先に組み立てるため通信が発生し得ます。

## 新しいインストーラーの説明を追加する

1. [共通雛形](_templates/installer/README.md)の3ファイルを`docs/<installer-id>/`へコピーします。
   IDは小文字の英数字とハイフンで、用途を識別できる名前にします。
   補助資材が必要な場合は、同じIDの`tools/<installer-id>/`へ配置します。
2. 各ファイルの`TODO`と仮の名称を実装に基づいて置き換えます。スクリプトへの相対リンクも追加します。
3. [トップREADME](../README.md)の用途別一覧と実行時の挙動、[docs索引](README.md)へ同じIDで登録します。
4. 実行例、相対リンク、アンカーを確認し、説明とコードを同じ変更でレビューします。

一括導入の対象にも追加する場合は、`install_all.sh`のID・スクリプト・説明・実行引数、
[一括ガイド](installation.md)の一覧、`tests/test_install_all.py`を揃えます。
通常実行が予定表示のみのインストーラーには、適用に必要な引数を付けます。
既存設定を初期化する経路や、編集を強制的に上書きするオプションは既定で使いません。

雛形のコピー例です。`example-tool`は実際のIDに置き換えてください。

```bash
mkdir -p docs/example-tool
cp docs/_templates/installer/*.md docs/example-tool/
```

各フォルダーは次の役割を共通にします。

| 文書 | 説明する内容 |
|---|---|
| `README.md` | 何のためのものか、導入する各ツールの用途・提供元・関係、読む順序 |
| `installation.md` | 前提条件、取得方法、導入・確認・更新・解除、オプション、取得元・配置・変更範囲、困ったとき |
| `usage.md` | 導入後の最初の操作、ツールごとの利用例、成果物の場所、機能の限界 |

長くなるテーマは同じフォルダー内へ追加し、概要からリンクします。
たとえばWorkgraphでは、共有、内部構成、トラブルシューティングを分けています。
別のインストーラーと同じツールを扱う場合は、共通の説明へリンクし、その組み合わせでの違いを記載します。

## 説明を保守するルール

- 実際の引数解析と処理を基準にします。コメントやヘルプと実装が違う場合は、確認した差異を明記します。
- 「ツールができること」「インストーラーが行うこと」「導入後に別途必要な作業」を分けます。
- dry-run、更新、解除、バックアップ等が未提供なら明記し、架空のオプションを例示しません。
- 外部取得元、固定版か最新版か、既存設定への変更、再実行時の挙動を確認します。
- 外部ツールの機能は公式資料または配布済み資料で確認し、出典と必要に応じて確認日・対象版を記載します。
- 個人の絶対パスや機密情報を例に含めません。仮のパスやIDは置き換えが必要だと明記します。
- 保存方針・スキーマ・機械が参照するテンプレートは、それぞれの保守元に維持し、docsでは説明とリンクを提供します。通常は`tools/<installer-id>/`、研究の組み立て版は固定版ベースと内蔵の更新資材を確認します。
- 文書の移動では相対リンクと既存アンカーを確認し、古い入口からも新しい説明へ移動できるようにします。

### SpecKitの埋め込み資料

現在のDesign ResearchとUpstreamは、同じ更新用ZIPを配布スクリプトへ内蔵しています。
固定コミット`d3f46e0d591b45cb2423317030a489b91566e891`の元インストーラー2本を照合し、
一時領域で更新を適用・生成・検証してから、通常の単一ファイル配布物を出力します。

更新元を読むには、未使用または空の一時ディレクトリへ展開します。通信・導入は行いません。

```bash
bash install_speckit_upstream.sh --extract-bundle /tmp/codex-research-upgrade
bash install_speckit_upstream.sh --bundle-self-test
```

展開される`codex_interface_upgrade/`で、次の役割を確認します。

| 保守元 | 役割 |
|---|---|
| `bootstrap.py`・`build_installers.py`・`pinned_base.py` | 配布入口、固定版の取得・照合、組み立てと検証 |
| `integrate.py`・`installer_commands.py`・`command_assets.py` | 更新の適用、単一研究入口、旧ショートカットの退役 |
| `overlay/tools/design-research/skill/` | Codexからの入口選択、状態確認と実行準備 |
| `core_upgrade/`とその`previous_report_upgrade/` | 研究分割、再評価、提案方式の報告、Upstreamのv2連携 |
| `tests/`と各更新層の`tests/` | 独立した契約試験。実モデルの評価とは別 |

組み立てを確認する場合は、固定版の元スクリプト2本を用意します。
更新用ラッパーや、固定版を編集したファイルはベースに使えません。

```bash
bash install_speckit_upstream.sh \
  --base-dir /absolute/path/pinned-base --offline --build-only /absolute/path/empty-output
```

成功時の出力は両インストーラー、`build-summary.json`、`validation/`のログ、`sources/`の組み立て済みソースです。
組み立て版を保守するときは、展開した更新元と固定版への適用を照合し、両配布物の更新資材・版を揃えます。
既存の`tools/speckit-upstream/build_single.py`や`tools/design-research/build_installer.py`は、組み立て途中の通常配布物を作るビルダーです。
現在のリポジトリでそのまま実行して、ルートの組み立て用スクリプトを旧形式で上書きしないでください。

`--bundle-self-test`と、組み立て後の`--self-test`は異なります。
2026-10-10の初回確認では同梱249件は成功し、組み立て後のUpstream試験166件は2 failure・6 errorで停止しました。
停止原因の修正後は組み立て・自己テスト・このPCの更新が成功し、2.4.0では同梱287件も成功しています。
[再現条件と検証結果](design-research/validation.md)

Upstreamの連携方針は、更新元の`RESEARCH_FIRST.md`・`RESEARCH_WORKSTREAMS.md`と利用ガイドを照合します。

- ストーリー・懸念・ユースケースから要件へ進み、必要なレビュー・明示承認後に研究へ渡す。
- 新規・実現方式を変える設計は、該当テーマの研究と統合を経て確定する。標準実装は根拠付きで分類する。
- 未導入・実行不能では必要な研究を未実行にし、要件・As-Isを整理しても方式設計を確定しない。
- v2の要件・計画ハッシュ、テーマ別run・保存版報告、統合状態とUI/UX適用を対応させる。旧v1を勝手に書き換えない。
- 画面例に実際のUI/UX Skillを適用し、静止画・プロトタイプ・実際の操作確認を区別する。

これらはSkillの指示・CLIの契約・実行結果を分けて確認します。
実Codexで短い依頼から研究が選ばれ、設計へ反映されるかは別途評価が必要です。

### GitHub Project Directorの埋め込み資料

GitHub Project Directorも単一ファイル内に資料と実装を持ちます。
`bash install_codex_github_pm.sh --extract /tmp/github-pm-review`で、未使用または空のディレクトリへ展開できます。
`README_EXTRACTED.md`、`scripts/install_github_pm.py`、`skills/github-project-director/`を確認し、
利用者向けの説明は[専用ガイド](codex-github-pm/README.md)で保守します。
展開物を補助ディレクトリへ複製する必要はありません。

### Design Researchの埋め込み資料

組み立てと展開の共通手順は[SpecKitの埋め込み資料](#speckitの埋め込み資料)を参照してください。
更新元の`workflow-guide.md`、`readable-documents.md`、`reassessment.md`、`workstreams.md`と、
`codex_interface.py`・`workflow_overview.py`・`research_workstreams.py`を照合します。

`$design-research`が目的から工程を選び、計画だけの依頼では実験を始めず、状況確認では記録だけを読みます。
`prepare`が対象と入力を解決し、`run --expect-dispatch`が同じ入力・ハッシュで実際のハーネスを起動します。
候補比較は1テーマにつき約5案を目安にし、提案方式は独立した節と全体・詳細・差の図、式や擬似コード、成立条件・限界を説明します。
再評価は完了runの保存版を参照して別slug・runで行い、同一条件の中断再開と区別します。

研究の依存順は計画です。同じプロジェクトの実行はロックで直列化され、自動並列起動や結果回収を実装したとは扱いません。
モデルの判断品質、一次文献の読解、PoCの科学的な妥当性は、モック試験やファイルの存在だけでは確認できません。

導入・状態確認のオプションは[導入手順](design-research/installation.md)、ローカルHTTP・PoC・根拠・復旧の過去の試験は[検証結果](design-research/validation.md)を参照してください。
Memory保存は外側のSkillが担当し、既存の保存基準・モードと許可に従います。ハーネスの子役は書き込みません。

### Office Workbenchとyomiyasuの埋め込み資料

どちらもスクリプト単体に独自資材とテストを含み、`--extract DIRECTORY`で展開できます。
Office Workbenchは`README_JA.md`と`install.py`を確認します。yomiyasuは`tools/codex-yomiyasu/`の編集用ソースを確認し、`python3 tools/codex-yomiyasu/build_installer.py`で単一ファイルを再生成します。`--check`では配布物と編集用ソースの一致を検査します。展開時は`installer.py`、`SKILL.md`、`references/`、`scripts/`、`paragraph-writing/`、`japanese-direct-writing/`と、検査用の`tests/`・`evals/`を配置します。評価資材はSkillの導入先には配置しません。

2.0.0-proposal.1では、補助2スキルの本文を部分作業用に限定しています。現在の本文のhashと由来は`UPSTREAM.json`・`SOURCE.json`に記録し、発動設定は導入時の`auto`/`explicit`に応じて生成します。資材を差し替える場合は、出典とhash、revisionを更新し、再生成と自己テストを行います。
展開物はレビュー用の一時ディレクトリに置き、利用者向けの説明は専用ガイドで保守します。

1.1.0と1.2.0の文章比較を再測定する場合は、`tools/codex-yomiyasu/evaluate_writing.py`を明示実行します。比較対象の入口・参照資料と4件の原稿は、`tools/codex-yomiyasu/evaluation-v130/`に旧版のまま保持しています。Python 3.11以降、ログイン済みのCodex CLI、yomiyasuの上流原本が必要です。設定済みのモデルと推論設定で実際のモデル利用が発生するため、インストールや`--self-test`からは呼びません。

```bash
python3 tools/codex-yomiyasu/evaluate_writing.py --out /tmp/paragraph-writing-comparison
```

結果には実行条件、入力hash、出力全文、条件名を伏せた評価を残します。数値やコードの機械差分に加え、原文の各事実・条件・断定の強さを本文で照合してから結論を記載します。[検証結果](codex-yomiyasu/validation.md)には実際の修正前後と限界を載せます。

現在の統合工程の生成比較は、`evals/prepare_generation_eval.py`で別途準備します。[比較手順](../tools/codex-yomiyasu/evals/PROTOCOL.md)に条件と採点方法をまとめています。`evals/evaluate.py`は60件の人工データによる検出器の試験、`evals/review_examples.py`は推敲例の機械点検です。どちらもモデルを呼びません。生成比較、自動選択の試験、読者の理解度測定と混同しないでください。

### 日本語の説明を推敲する

yomiyasuを使う場合は、修正前後を別のUTF-8ファイルに残してlintとcompareを実行します。
コマンド、設定名、数値、条件、否定、断定の強さを保持し、表や番号付き手順は用途に合えば残します。
検査結果は見直し候補として扱い、警告を消すためだけに意味を変えません。

## ドキュメントだけを変更した場合の確認

- トップREADMEから各概要・導入・利用ページへ進み、戻り先も確認します。
- Markdownのローカルリンクについて、ファイルの存在と見出し・明示アンカーを確認します。
- コマンド名、引数、既定値、配置先、版を実装と照合します。組み立て・導入状態・実研究の通信範囲を区別します。説明確認のための実インストールは不要です。
- Mermaid図は構文と、依存・処理・引き渡しを示す矢印の意味を確認します。計画図から自動実行や測定成功を推定しません。
- 既存説明を移した場合は、すべての項目に移動先があることを確認します。
- `git diff --check`を実行します。新規docsは未追跡の間は通常のdiffに出ないため、別途内容を確認します。

文書だけの変更では新しい機能テストやCIを追加しません。実装も変更した場合は、その対象の検証を行います。
