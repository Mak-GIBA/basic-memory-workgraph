## 読み手に伝わる報告と再検討

通常のresearch/audit/runでは`--reader-friendly`を付け、`references/readable-documents.md`に従う。
提案手法を扱う研究では既存の`--report-profile proposed-method --target-methods 5`を維持する。
audit/runでは、架空の内部構成を推測せず実際の検証範囲と確認フローを図で示す。
要旨・目的・具体例・用語から全体図、部品の説明、数式/擬似コード、検証、限界へ進む。図のキャプション・読み方・代替説明を省略しない。
提案手法章の3種類の図を再利用できる場合、reader_guide.diagram_source=proposed-methodとして重複を避ける。

完了済み研究を要件変更や別原理の探索で見直すときは`references/reassessment.md`を読み、
`gan-harness.sh reassess --prior-run <actual-state.json> --slug <new-topic> --brief "変更条件・再検討理由"`を使う。
`resume`は同じ条件で中断した実行の再開専用。新モードは新しい研究runであり、前回の報告を上書きしない。
過去の採用案と少なくとも1つの離れた原理を含む約5方式を検討し、必要な比較と反証実験を既存の隔離PoCで試せる形へ落とす。
前回の証拠を今回の成功証拠に転用しない。悪化・同等・保留でも、根拠に応じた結論として報告する。
upstream設計からの利用では`--requirements <actual-canonical-path>`を指定し、研究の前提と設計時点の要件を一致させる。
新たなUI画面例の設計は実在するUI/UX Skillに委ねる。設計のみの依頼ではアプリ本体の実装を開始しない。

## コアロジック単位の研究
upstreamから渡された研究テーマはreferences/workstreams.mdに従う。
--workstream-planと--workstream-idで渡された問い・要件ID・入出力・共通評価条件に範囲を限定する。
システム全体を再設計したり、隣の研究や共有design.mdを書き換えたりしない。
テーマごとに約5手法を比較し、実現方式・選定理由・接続制約・資源・未確認を親へ返す。
並列探索中の仮の固定入力と、選定結果を使った全体評価を区別する。runの完了を統合の合格へ読み替えない。
