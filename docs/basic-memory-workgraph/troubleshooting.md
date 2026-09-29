# Basic Memory Workgraph：困ったとき・記憶の点検

[概要](README.md) · [導入](installation.md) · [使い方](usage.md) · [共有](sharing.md) · [仕組み](reference.md) · [困ったとき](troubleshooting.md) · [docs一覧](../README.md)

ターミナルのコマンドは、特に指定がなければこのリポジトリのルートで実行します。
「Codexへの依頼例」はCodexの会話欄に入力します。

<a id="troubleshooting"></a>

## 困ったとき

| 状況 | 確認・対処 |
|---|---|
| 新機能が動かない | 新しいCodexセッションを開始し、`/plugins` と `/hooks` を確認する |
| 教訓が保存されない | `mode`、検証根拠、再利用価値、既存Memoryとの重複を確認する。価値がなければ保存しないのが正常 |
| 修正指示が保存されない | `correctionMode=scoped`、実装モード、重複や機密情報の有無を確認する |
| 終了時の評価が出ない | Planでは正常。実装モードでも当該ターンの有効化が必要。更新後は新しいセッションを開始する |
| 具体事例が増えない | 既定は `caseMode=off`。明示保存依頼、`reusable`、`progressive` を用途に応じて使う |
| Skillが作成されない | 既定は `skillMode=review`。`auto` でもCreator・検証・追加価値が必要 |
| `PyYAML` が必要と表示された | [Python環境の準備](installation.md#python-tools)を実行し、同じ環境でコマンドを使う |
| 更新で終了コード2になった | `preserved` を確認。対象を上書きせず保持した通知であり、全更新の失敗ではない |
| 保存先が見つからない／不一致 | `primaryProject` とBasic Memory登録情報を確認。[更新の詳細](installation.md#update-details)を参照 |
| 記憶の順序や解釈がおかしい | [audit](#audit)で構造を確認し、会話の根拠と照合する |
| `needs_review` でexportが止まる | 根拠付きの訂正・点検後に共有／学習レビューをやり直す。フラグだけ消して通さない |
| exportの件数が0になった | 共有／学習用途の指定とレビュー状態を確認。編集後は再レビューが必要 |
| `Missing or stale privacy review` | 内容を確認して `review` を再実行する。共有・学習両方を許可するなら両引数を指定する |
| `Output already exists` | 既存の出力は上書きしないため、新しい `--output` を指定する |
| importで `conflicts` が返った | 同名ノートの差分を確認するか、別の保存先へ取り込む。既存ノートは上書きされない |
| 秘密情報の検査で拒否された | 内容を匿名化して再レビューする。検査を通っても人名・業務機密の確認は必要 |

共有・学習CLIでは `--dry-run` を付けると書き込みせず確認できます。
ただし、出力先がすでに存在する場合など、通常実行と同じ入力制約は適用されます。
CLIの終了コードは0が成功、1が入力・処理エラー、2が除外項目またはimport衝突ありです。
exportは安全に出力できた項目を出し、`skipped` に除外理由を表示します。

<a id="audit"></a>

### 保存した記憶を点検する

点検するタイミングは、保存・更新後、再利用前、新しい情報と矛盾したとき、手動依頼時です。
定期巡回ジョブは追加していません。まず構造だけを読み取り専用で確認できます。

```bash
# 保存先全体を点検。ノートやレビュー情報は変更しない。
python3 tools/basic-memory-workgraph/workgraph_tools.py audit --memory-dir "$HOME/knowledge/codex-memory"

# 対象のCaseだけ点検。パスは実在するノートに置き換える。
python3 tools/basic-memory-workgraph/workgraph_tools.py audit \
  --memory-dir "$HOME/knowledge/codex-memory" --note "cases/example.md"
```

JSONで問題種別・位置・対応候補と、影響がありそうな派生ノート（最大2段）を報告します。
終了コードは0＝構造上の指摘なし、2＝指摘あり、1＝入力・処理エラーです。
`--dry-run` も指定できますが、auditは常に読み取り専用です。
既存の自由形式Caseは未対応扱いで捨てず、構造検査の対象外として報告します。

CLIが検出するのはID重複、参照切れ、記録順序と対象の矛盾、根拠なしの採用推定などです。
**構造検査に通っても、実際の会話の順序や解釈が正しいとは限りません。**
Codexへの依頼例:

```text
このCaseの修正順序と評価対象を、利用可能な会話の根拠と照合して。
確定できる誤りは根拠と訂正履歴を残して直し、不明なら要点検として扱って。
このCaseから導いたRuleやWorkflowへの影響も確認して。
```

実装モードでは、確定できる誤りを必要な範囲だけ訂正し、匿名化した変更前後・理由・根拠を残します。
実際に失敗した試行や後からの方針変更は、記憶の誤りと混同して消しません。
判断できなければ `integrity_status=needs_review` と具体的な懸念を残し、成功事例としての参照やexportを保留します。
派生知識は独立した根拠を確認し、一括削除・一括修正はしません。
Plan／読み取り専用では、報告とその回答での参照見送りまでです。

点検状態は `unreviewed` / `checked` / `needs_review` で、共有・学習許可とは別です。
訂正後は根拠との照合と構造チェックを行い、読み返して懸念を解消してからcheckedに戻します。
内容や状態を変えたら既存のprivacyレビューは失効し、exportには再レビューが必要です。
何も変わらない点検では日時だけの更新をしません。importされたcheckedはunreviewedに戻り、
needs_reviewは保持されます。詳細は[AUDIT.md](../../tools/basic-memory-workgraph/templates/AUDIT.md)を参照してください。
