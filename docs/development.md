# 開発・検証とドキュメントの追加

[docs一覧](README.md) · [リポジトリ概要](../README.md)

## ソースと資材の配置

ルートには`install_*.sh`を置き、補助コード・配布資材・解除スクリプトは
`tools/<installer-id>/`にまとめます。説明は`docs/<installer-id>/`、検証は`tests/`に置きます。
単一ファイルで動くインストーラーに、空の補助ディレクトリを作る必要はありません。
全ツールの共通入口は`install_all.sh`、導入ガイドは`docs/installation.md`です。

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
| SpecKit Upstream | `bash install_speckit_upstream.sh --self-test` | 一時環境とモックSpecKitによる検証。実Codex・公式CLIの取得を含むE2Eテストではない |
| GitHub Project Director | `bash install_codex_github_pm.sh --self-test` | 一時環境での導入・更新・解除、読み取り補助、Skillの静的な指示内容を検証。実GitHubへの書き込みやモデルの出力品質を保証しない |
| Design Research | `bash install_design_research.sh --self-test --json`、`python3 -B -m unittest discover -s tests -p 'test*design_research*.py' -v` | 単体配布・編集保護・バックアップ・切り替え復旧、実ローカルHTTP／PoC、根拠・中断復旧を検証。モデルとOSサンドボックス起動は模擬。[検証範囲](design-research/validation.md)参照 |
| Codex ECC | `python3 -m unittest discover -s tests -p 'test*ecc*.py' -v`、Bash構文確認 | 模擬Codexによる新規導入、既存再利用、更新失敗・再実行、復元、設定維持と原本取得。新規環境への実ダウンロードは別途確認が必要 |
| Office Workbench | `bash install_codex_office.sh --self-test` | 一時環境で導入・編集保護・文書処理を検証。通信・Codexは模擬し、実PDFライブラリがない対象はSKIP。実OfficeCLIや描画のE2E確認は別途必要 |
| yomiyasu・paragraph-writing | `bash install_codex_yomiyasu.sh --self-test` | 一時HOME・作業ディレクトリと模擬上流で導入・更新・解除・検査を確認。配布元への実通信やモデルの文章品質は検証しない |
| Herdr | `python3 -m unittest discover -s tests -p 'test_install_herdr.py' -v` | 一時HOMEで取得・Bash設定・workspace照合・再実行を検証。実ダウンロードや実セッションの起動は含まない |

構文確認や文書レビューのためにインストーラーの通常実行を行わないでください。
Workgraph、UX Stack、GitHub Project Director、Design Research、Herdrは引数なしで実際に導入します。
UX Stack、SpecKit、GitHub Project Director、Design Research、Office Workbench、yomiyasuの`--extract`もファイルを書き込む操作です。

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
- 保存方針・スキーマ・機械が参照するテンプレートの正本は`tools/<installer-id>/`内に維持し、docsでは説明とリンクを提供します。
- 文書の移動では相対リンクと既存アンカーを確認し、古い入口からも新しい説明へ移動できるようにします。

### SpecKitの埋め込み資料

SpecKit Upstreamの資料と実装はシェルスクリプト内のZIPに含まれます。
`--extract`で未使用の一時ディレクトリへ展開し、`README_COMMANDS.md`と`workbench/`、`assets/`を確認できます。
展開物やBase64資材をそのままdocsへ複製せず、利用者向けの説明を保守します。
この操作はインストールしませんが展開先へ書き込みます。既存の空でないディレクトリは使えません。

1.3.0の内蔵自己テストは、導入されたSkill・flowから参照する資料の存在と、flowが研究を起動せず対象文書を変更しないことも確認します。
既存要件・方式の見直しでは、[ユースケース別ガイド](speckit-upstream/reassessment.md)と内蔵`REASSESSMENT.md`を照合し、次の条件を点検します。

- 精度改善・評価方法の比較には`research`、バックエンドの実測には`audit`を使う。
- 単純な文書修正には研究を要求しない。
- 未導入・旧版・実行不能の場合は必要な研究を未実行とする。
- 根拠が不足する採用判断は保留し、仕様を変更した場合は再レビューする。

この点検はSkillの静的レビューです。実CodexによるDesign Researchの選択・実行と研究の結論の品質は、実モデルで別途確認します。

### GitHub Project Directorの埋め込み資料

GitHub Project Directorも単一ファイル内に資料と実装を持ちます。
`bash install_codex_github_pm.sh --extract /tmp/github-pm-review`で、未使用または空のディレクトリへ展開できます。
`README_EXTRACTED.md`、`scripts/install_github_pm.py`、`skills/github-project-director/`を確認し、
利用者向けの説明は[専用ガイド](codex-github-pm/README.md)で保守します。
展開物を補助ディレクトリへ複製する必要はありません。

### Design Researchの埋め込み資料

Design Researchは圧縮JSON内にSkill・Pythonコード・参照資料・テンプレートを持ちます。
`bash install_design_research.sh --extract /tmp/design-research-review`で、未使用または空のディレクトリへ展開できます。
正本は`tools/design-research/skill/`と`tools/design-research/install_design_research.py`です。
`python3 -B tools/design-research/build_installer.py`で単体配布物を再生成し、
`python3 -B tools/design-research/build_installer.py --check`で正本と一致するか確認します。
展開先の`SKILL.md`、`scripts/`、`references/`、`templates/`と正本を照合できます。
利用者向けの説明は[専用ガイド](design-research/README.md)で保守します。
コアロジック・複数文献の読解・Memory保存について、Skillとハーネスの各役割の指示を揃えます。
Memory保存は外側のSkillが担当し、ハーネスの子役は書き込みません。詳細は`references/memory-workgraph.md`です。
ローカルリンク先の存在は導入テストで確認し、指示の点検と実モデルの動作評価は区別します。
`--dry-run --json`で予定、`--status --json`で導入状態、`--doctor --json`で環境を確認できます。
これらは実インストールを行いません。`--doctor`は導入済み資材の整合性と
構造化Codex実行・コマンド用サンドボックスの準備を分けて診断します。
`scripts/gan-harness.sh`の実行テストはCodex判断とサンドボックス起動を模擬し、
ローカルHTTP・PoC・実ファイル・ログは実際に扱います。モデルの判断品質と実機の隔離効果は別途確認します。

### Office Workbenchとyomiyasuの埋め込み資料

どちらもスクリプト単体に独自資材とテストを含み、`--extract DIRECTORY`で展開できます。
Office Workbenchは`README_JA.md`と`install.py`を確認します。yomiyasuは`tools/codex-yomiyasu/`の編集用ソースを確認し、`python3 tools/codex-yomiyasu/build_installer.py`で単一ファイルを再生成します。`--check`では配布物と編集用ソースの一致を検査します。展開時は`installer.py`、`SKILL.md`、`references/`、`scripts/`、`paragraph-writing/`に両方の資材を配置します。
展開物はレビュー用の一時ディレクトリに置き、利用者向けの説明は専用ガイドで保守します。

yomiyasuとparagraph-writingの文章比較は、`tools/codex-yomiyasu/evaluate_writing.py`を明示実行します。Python 3.11以降、ログイン済みのCodex CLI、yomiyasuの原本が必要です。設定済みのモデルと推論設定で実際のモデル利用が発生するため、インストールや`--self-test`からは呼びません。

```bash
python3 tools/codex-yomiyasu/evaluate_writing.py --out /tmp/paragraph-writing-comparison
```

入力4件と構成条件は`tests/evaluation_cases.json`、既存入口の比較用原本は`tests/baseline-yomiyasu.md`で固定しています。結果には実行条件、入力hash、出力全文、条件名を伏せた評価を残します。数値やコードの機械差分に加え、原文の各事実・条件・断定の強さを本文で照合してから結論を記載します。[比較検証](codex-yomiyasu/validation.md)には実際の修正前後と限界を載せます。

### 日本語の説明を推敲する

yomiyasuを使う場合は、修正前後を別のUTF-8ファイルに残してlintとcompareを実行します。
コマンド、設定名、数値、条件、否定、断定の強さを保持し、表や番号付き手順は用途に合えば残します。
検査結果は見直し候補として扱い、警告を消すためだけに意味を変えません。

## ドキュメントだけを変更した場合の確認

- トップREADMEから各概要・導入・利用ページへ進み、戻り先も確認します。
- Markdownのローカルリンクについて、ファイルの存在と見出し・明示アンカーを確認します。
- コマンド名、引数、既定値、配置先を実装と照合します。説明確認のための実インストールは不要です。
- 既存説明を移した場合は、すべての項目に移動先があることを確認します。
- `git diff --check`を実行します。新規docsは未追跡の間は通常のdiffに出ないため、別途内容を確認します。

文書だけの変更では新しい機能テストやCIを追加しません。実装も変更した場合は、その対象の検証を行います。
