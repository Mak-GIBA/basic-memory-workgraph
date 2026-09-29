# 使い方

[docs一覧](../README.md) · [概要と収録ツール](README.md) · [導入手順](installation.md)

## 最初の操作

調査したいプロジェクトでCodexを開き、問題と制約を添えて呼び出します。
以下の`text`ブロックはCodexの会話欄へ入力する例です。

```text
$design-research
このプロジェクトの検索方式を見直したい。現行実装と要件を読み、現行方式を含む2〜3案を
精度・応答時間・運用負荷で比較して。論文と公式資料の根拠、未確認事項、必要なPoCを示して。
```

仕様書がなくても、目的・入力・利用規模・予算・既存環境など、分かる条件から始められます。
エージェント設計では、例えば次のように依頼します。

```text
$design-research
問い合わせ分類と回答案作成を自動化したい。通常のコード、単一エージェント、複数エージェントを
同じ条件で比較して。既存コードを基準にし、誤分類時の扱いと必要な評価データも整理して。
```

## 調査の進め方

1. 既存要件・実装を確認し、目的、必須条件、希望条件、調査の予算と範囲を整理します。
2. 現行方式または最も単純な実現案を含め、共通の評価軸で候補を比較します。
3. 重要な主張を論文・公式資料の該当箇所で確認し、適用条件と反対の証拠を記録します。
4. 評価・批判の観点から見直し、判断を変え得る不確実性には小さなPoCを計画します。
5. 条件付きの推奨案、根拠、限界、再検討条件を成果物にまとめ、証拠台帳の構造を検証します。

調査結果は提案です。承認された決定や実行済み実験と混同しません。
別エージェントでの評価が利用できない場合は、同じ実行内で順に観点を変えたことを明示します。
調査から依存導入・有料実験・実装・GitHubへの投稿まで自動で進めるものではありません。

## 調査CLIを使う

以下はターミナル用です。調査対象プロジェクトのルートで実行します。
まず導入したSkill内のスクリプトを指定します。

```bash
DR="${CODEX_HOME:-$HOME/.codex}/skills/design-research/scripts/research.py"
python3 -B "$DR" providers
```

`--project`で導入した場合は`DR="/path/to/repo/.codex/skills/design-research/scripts/research.py"`、
`--skills-dir`の場合はその配置先へ置き換えます。`providers`は通信せず、対応先と機能を表示します。

### 文献検索と照会

```bash
python3 -B "$DR" search --provider all --query 'agent memory evaluation' --limit 5 --allow-network
```

`--provider`は`all`、`arxiv`、`semantic-scholar`、`crossref`から選びます。
検索は1回につき各取得先の1ページで、`--limit`は取得先ごとの上限です。既定10件、指定可能範囲は1〜50件です。
`--offset`、`--year-from`、`--year-to`も指定できますが、各サービスで検索式や日付の意味は異なります。

検索で見つかった実際のIDを使い、メタデータや引用関係を確認できます。
次の`ACTUAL_DOI`は実際のDOIへ置き換えてください。

```bash
python3 -B "$DR" lookup --provider crossref --id 'ACTUAL_DOI' --allow-network
python3 -B "$DR" links --id 'DOI:ACTUAL_DOI' --direction citations --limit 5 --allow-network
```

`lookup`は各取得先のIDを指定し、`links`はSemantic Scholarの引用・参考文献を1ページ取得します。
`--direction references`で参考文献側を調べられます。自動で引用先を再帰的に巡回しません。
いずれかの取得先に失敗があれば終了コード2となり、成功分とエラーを結果に含めます。
取得できなかったことを「該当論文なし」と解釈しないでください。

### 通信・キャッシュ・任意設定

実検索には`--allow-network`が必要で、検索語やIDを選択した学術APIへ送ります。
私有コードや機密要件をそのまま検索語にしないでください。
結果は`${XDG_CACHE_HOME:-$HOME/.cache}/design-research/`にキャッシュされ、検索語・要旨を含み得ます。
`--cache-dir`で場所、`--cache-ttl`で有効期間を指定できます。既定の有効期間は86400秒です。

```bash
python3 -B "$DR" search --provider all --query 'agent memory evaluation' --limit 5 --offline
```

`--offline`は通信せず、一致するキャッシュだけを返します。古い結果にはその旨を付け、キャッシュがなければエラーです。
`--offline`と`--allow-network`は併用できません。

`SEMANTIC_SCHOLAR_API_KEY`と`CROSSREF_MAILTO`は補助コード上は任意です。
前者はサービスへのアクセス・割当量、後者はCrossrefへの連絡先通知に関わります。
必要な値は自分の環境管理の仕組みで設定してください。インストーラーは契約・取得・登録しません。
リクエスト間隔と再試行回数は制限されますが、複数マシンをまたぐ通信制御ではありません。

### 調査資料を初期化する

```bash
python3 -B "$DR" init --slug retrieval-options --question '検索方式を精度・応答時間・運用負荷で比較する'
```

`docs/design-research/retrieval-options/`に新しい雛形を作ります。
`--slug`は先頭が英小文字または数字の、英小文字・数字・ハイフン1〜64文字です。
`--root PATH`で保存先の親を変更できます。既存の同名ディレクトリは上書きしないため、
調査の続きでは既存資料を編集し、過去の判断を保持します。

### 証拠台帳を検証する

```bash
python3 -B "$DR" validate docs/design-research/retrieval-options/evidence.json
```

**初期化直後は未記入項目があるため、検証に通りません。**
資料を読み、基準案を含む候補、共通評価軸、主張と出典、未確認事項、判断を記入してから検証します。
台帳形式はSkill内の`references/evidence-format.md`、暫定判断の例は`references/provisional-example.json`を参照してください。
成功時は`valid: true`で終了コード0、構造エラーは終了コード1です。
この検証は形式と参照関係を扱い、証拠の真偽や推奨案の正しさを証明しません。

## 成果物の保存先

既定では対象プロジェクトの`docs/design-research/<slug>/`へ保存します。
これは利用先プロジェクトの調査資料であり、このリポジトリのインストーラー説明ページとは用途が異なります。

| ファイル | 内容 |
|---|---|
| `design-research.md` | 問題・制約、候補比較、根拠、推奨案、限界、PoCと次の作業 |
| `evidence.json` | 出典・主張・候補・実験・判断を結び付ける証拠台帳 |
| `decision.md` | 判断記録の案。採用候補、見送る案、影響、見直す条件 |
| `research-log.json` | 検索・読解の範囲、失敗、調査を終えた理由 |

`init`は4ファイルの雛形を生成するだけです。検索結果を自動で読み込んだり、完成した比較レポートを書いたりしません。
調査CLIの検索結果はJSONとして標準出力へ返り、Skillの手順に沿って必要な根拠を成果物へ整理します。

## 利用範囲と次の作業

要旨や検索結果だけで「論文全文を読んだ」と扱わず、判断に必要なページ・節・図表を確認します。
論文の報告値、ローカル実測、推測、仮説、未知を区別し、未実行のPoCを実測として記載しません。
外部ツールが使えない場合は暫定比較と必要な確認事項を示します。

調査結果はSpecKit等の設計資料やGitHubのタスク案へ引き継げます。
Basic Memoryへの保存は既存の保存方針に従い、論文・要旨を一括で取り込むことは前提にしません。
導入・設定上の問題は[導入手順](installation.md)を参照してください。
