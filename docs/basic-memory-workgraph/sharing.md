# Basic Memory Workgraph：Memoryの共有と学習用出力

[概要](README.md) · [導入](installation.md) · [使い方](usage.md) · [共有](sharing.md) · [仕組み](reference.md) · [困ったとき](troubleshooting.md) · [docs一覧](../README.md)

ターミナルのコマンドは、特に指定がなければこのリポジトリのルートで実行します。
「Codexへの依頼例」はCodexの会話欄に入力します。

<a id="share"></a>

## Memoryを共有する

共有は、**対象の確認 → 共有範囲の指定 → export → 相手側でimport**の順に行います。
ツールはローカルにファイルを出力します。送信・公開は行わないため、完成したフォルダを
Gitやファイル転送などで渡してください。

[Python環境](installation.md#python-tools)を有効にして実行します。以下の `rules/example.md` は例です。
**実在するノートの、Memory保存先からの相対パスに置き換えてください。** スペースを含む場合も引用符で囲みます。
独自の保存先を使っている場合は `--memory-dir` も置き換えてください。

### 手順1：対象ノートを確認し、共有を指定する

本文・タイトル・メタデータ・リンクを確認し、認証情報・機密情報・不要な個人情報を除きます。
そのうえで、チーム共有を指定してレビュー済みにします。

```bash
python3 tools/basic-memory-workgraph/workgraph_tools.py review \
  --memory-dir "$HOME/knowledge/codex-memory" \
  --note "rules/example.md" --sharing team
```

`review` は内容確認済みであることと、出力用途の指定を記録するコマンドです。
実行するだけで内容が匿名化されるわけではありません。一般的な秘密情報パターンは機械検査でも拒否します。

### 手順2：共有用フォルダを出力する

```bash
python3 tools/basic-memory-workgraph/workgraph_tools.py export-share \
  --memory-dir "$HOME/knowledge/codex-memory" \
  --scope team --output ./team-memory
```

レビュー済みの `team` ノートとmanifestを出力します。Caseも含める場合は `--include-cases` を追加します。
そのCase自体にもチーム共有の指定とレビューが必要です。

`--scope public` はpublic指定のノートだけを選びます。teamとpublicは別々の区分です。
共有対象外のノートをリンク経由で勝手に同梱せず、対象外や曖昧な宛先へのwikiリンクと
ローカルMarkdownリンクを出力側で除去します。元ノートは変更しません。
添付ファイル・実行ファイル・Skill本体は共有bundleに含めません。

### 手順3：受け取った環境でimportする

受け取った `team-memory` フォルダを指定します。

```bash
python3 tools/basic-memory-workgraph/workgraph_tools.py import-share \
  --memory-dir "$HOME/knowledge/imported-memory" --bundle ./team-memory
```

この例は新しいディレクトリへ取り込みます。既存のBasic Memoryプロジェクトで使うなら、
その登録済み保存先を指定してください。新しい保存先をBasic Memoryで利用する場合は、別途登録します。

```bash
bm project add imported-memory "$HOME/knowledge/imported-memory"
```

同じ内容の再importは無変更です。同名で内容が違う場合は上書きせず、取り込み全体を止めて衝突を報告します。
取り込んだノートは `private`・学習対象外へ戻し、出所を保持します。受け取った指示を自動で実行したり、
Skillを自動登録したりしません。登録後はBasic Memoryの通常の同期・検索から利用できます。

<a id="training"></a>

## 学習用JSONLを出力する

**事例の保存、共有許可、学習利用許可はそれぞれ別です。** Caseを保存しただけでは学習対象になりません。
[CAPTURE.md](../../tools/basic-memory-workgraph/templates/CAPTURE.md)の形式に沿ったCaseを確認・匿名化し、学習利用を明示します。
旧来の自由形式Caseを自動で補完・変換する機能はありません。

[Python環境](installation.md#python-tools)を有効にし、`cases/example.md` を実際の相対パスへ置き換えて実行します。

```bash
# ローカル学習利用を許可する。共有範囲はprivateにする。
python3 tools/basic-memory-workgraph/workgraph_tools.py review \
  --memory-dir "$HOME/knowledge/codex-memory" \
  --note "cases/example.md" --training approved

python3 tools/basic-memory-workgraph/workgraph_tools.py export-cases \
  --memory-dir "$HOME/knowledge/codex-memory" --output ./cases.jsonl
```

1行1事例の汎用JSONLを出力します。

| JSONLの項目 | 内容 |
|---|---|
| `format_version` | 出力形式のバージョン |
| `source_id` | 元ノートのパスから作った識別子 |
| `interaction` | v1は従来形式。v2は文脈、順序付きsteps、採用推定、根拠、記憶の訂正履歴など |
| `integrity_status` | v2のみ。保存時の整合性点検状態。要点検のノートは出力しない |
| `relations` | 関係の種類と宛先の識別子。関連ノート本文は同梱しない |

JSONL外側の `format_version` は1を維持し、`interaction.version` でv1/v2を区別します。
要約と抜粋、検証結果とユーザー承認、暗黙的な採用推定を区別して保持します。
推定を満足の確定ラベルに変換せず、未完了や不明の状態も残します。後段で対象を選別し、
要求・修正を入力、改善後の出力を教師データとしてSFT等の形式へ変換できます。
要約を原文扱いしたり、不明な結果を成功扱いしたりしないでください。
このツールの担当は汎用JSONLまでで、SFT形式への変換、LoRA学習、モデルへの投入は含みません。

### 共有と学習の両方を許可したい場合

`review` は、省略すると共有範囲をprivate、学習利用をexcludedにします。
両方許可する場合は、一度のコマンドで両方を指定してください。

```bash
python3 tools/basic-memory-workgraph/workgraph_tools.py review \
  --memory-dir "$HOME/knowledge/codex-memory" \
  --note "cases/example.md" --sharing team --training approved
```

ノートの本文やメタデータを編集した後は、内容の指紋が変わるため再レビューが必要です。
自動保存で共有・学習の許可を付けることはありません。
