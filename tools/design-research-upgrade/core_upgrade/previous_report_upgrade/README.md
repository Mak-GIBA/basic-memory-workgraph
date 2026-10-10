# Design Research：提案手法章・図解・5手法比較の拡張

## 今回の状態

改善コード、既存コードへの適用処理、回帰テスト、合成入力によるサンプルを同梱します。**GitHub本体への変更、ブランチ公開、PR作成は未完了です。** 2026-10-09のブランチ作成APIが `403 Resource not accessible by integration` を返しました。

参照した公開mainは `d3f46e0d591b45cb2423317030a489b91566e891`、公開版のDesign Researchは2.0.1です。本パッケージを適用するとバージョン宣言を2.2.0へ揃える設計です。これは公開リリース済みであるという意味ではありません。以前の会話にある未公開v2.1.0のチェックアウトは、この環境では確認できていないため含めていません。

## 変更すること

提案手法を設計・改善するSkill実行では、`research --report-profile proposed-method --target-methods 5` を選びます。単にテンプレートを変更するのではなく、ハーネスの実行プロンプト、生成前プレビュー、レビュー検証、終了判定、実際のレポート生成へ接続します。

レポートには独立した「提案手法」章を生成します。狙いと直感、具体例、構成要素の入出力・処理・役割、記号定義、数式または擬似コード、学習・準備と推論の区別、既存法との差分、他手法から借りた原理、実装箇所、計算コスト、失敗条件、批判と改訂、反証可能な実験との対応を記述します。

全体構成・提案部分の詳細・既存法との比較の3種類の図を、構造化したノードと矢印から実際のSVGとして生成し、本文に埋め込みます。図番号、キャプション、代替テキスト、図の読み方、編集用JSONを保存します。概念図は性能の実証ではありません。実測データがない場合は未測定と説明させます。

比較はベースライン込みで5手法が目安です。異なる作用原理を検討し、パラメータ違いやアブレーションで数を埋めません。少数とする場合は実質的な理由を記録します。5手法をすべて高コスト学習する義務や、検索・実験予算の自動増加はありません。

設計書で詳しく説明する候補と、実験後の採用判断を区別します。仮説段階、改善なし、悪化、保留という結果でも、記述が整合していれば提案の説明自体は可能です。候補を説明したことを採用・優位性の証明にしません。

## 適用

Python 3.10以降と既存のローカルチェックアウトを使用します。ZIPのディレクトリ構造を保って展開してください。

```bash
python3 /path/to/design_research_report_upgrade/apply_upgrade.py \
  --repo /path/to/basic-memory-workgraph --dry-run

python3 /path/to/design_research_report_upgrade/apply_upgrade.py \
  --repo /path/to/basic-memory-workgraph
```

適用前にdry-runと差分を確認してください。既存のharness.pyとreport.pyは確認済みのGit blob SHAと照合します。別バージョン、未公開v2.1.0、ローカル編集には無理に適用せず停止します。以前のv5拡張の管理対象ファイルは、その元の内容と一致する場合だけ更新できます。

適用時には対象外の設定やデータを変更せず、更新前のファイルをリポジトリ外へバックアップします。既存ビルダーによる `install_design_research.sh` 再生成、`--check`、生成物の `--self-test` を順に実行し、失敗時は変更したソースを戻します。同じ適用の再実行は検証後に何もしません。Git commit、push、PR作成はこの適用スクリプトでは行いません。

既存CLIとの互換性のため、フラグなしの `research` は従来相当のcomparisonです。Skillの提案手法設計用コマンドを明示的にproposed-methodへ更新します。audit/runと、プロファイルを持たない過去の実行のresumeは従来契約を維持します。既存トピックのファイル構成は移行しません。

## 使用例

```text
$design-research 現行法を含めて5手法を目安に検討して。各候補の原因仮説・作用原理・先行研究との差分を詰め、最終レポートでは提案手法章を独立させ、直感から定式化・擬似コードまで詳しく説明して。全体構成、提案部分の詳細、既存法との差分の3種類の図解も入れて。実測と未検証の仮説は区別して。
```

ハーネスを直接使う場合の新しい指定は次のとおりです。

```bash
bash <skill-dir>/scripts/gan-harness.sh research \
  --report-profile proposed-method --target-methods 5 \
  --project <target> --slug <topic> --brief '<目的と制約>'
```

既存のネットワーク許可・実行制限はそのままです。外部調査が許可される場面だけ既存の `--allow-network` を付けます。

## 単体で出力を確認する

以下は実在研究ではなく、図表と章構造の表示確認用の架空データです。

```bash
python3 overlay/tools/design-research/skill/scripts/proposal_report.py \
  validate samples/synthetic-dossier.json

python3 overlay/tools/design-research/skill/scripts/proposal_report.py \
  render samples/synthetic-dossier.json --out /tmp/new-method-report.md --strict
```

`samples/standalone-report.html` は図を埋め込んだ閲覧用サンプルです。`samples/report.md` と `samples/method-figures/` は編集・再利用できる形です。入力資料は架空であり、サンプルにある検証の説明を実行済みの結果として扱わないでください。

## 検証範囲

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s overlay/tests -v
```

56件のテストが成功しました。内訳は43件の設計・レポート機能テストと13件の適用処理テストです。後者は小型のupstream模擬ソースと模擬ビルダーを使います。overlay/testsの43件は同じ回帰テストをリポジトリへ持ち込める配置で実行したもので、別の43件を追加したという意味ではありません。

**この環境では完全な実リポジトリへの適用、実ビルダーでのインストーラー再生成、既存全テストの回帰確認、Codex CLIでの実モデル実行は未検証です。** 仕様の構造検証は、研究の新規性、数式の正しさ、実験の妥当性、文章の理解しやすさを自動認定するものではありません。詳細はVALIDATION.mdを参照してください。
