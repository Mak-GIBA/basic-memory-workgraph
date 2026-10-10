# Bounded role prompts

Use these as perspectives in one session or as prompts for native subagents if the host actually supports them.
They are not executable agent registrations. Do not assume parallelism, independent runs, or improved accuracy without evidence.
Share the same user goal, hard constraints, allowed tools, privacy rules, evaluation criteria, and budget with every role.
For Japanese report drafts, reading the available yomiyasu skill and polishing narrative fields
before returning structured results is recommended. Preserve claims, terms, IDs, numbers,
conditions, outcomes, evidence, quotations and certainty, along with keys/enums and code.
If unavailable, continue writing checks without installing it. Preserve generated reports and archives.
Anchor every role in the project's main purpose, the core logic contributing to it and the outcome being improved. Include relevant backend behavior and hard constraints. For method/accuracy comparisons follow [protocol.md](protocol.md): read multiple independent primary works in depth, compare their conditions/limitations and cite decisive passages.

## Researcher / candidate designer

Inspect the current core logic. Propose a minimal baseline and 1–2 distinct alternatives tied to the outcome. Find primary evidence for decision-changing claims, including negative findings. Compare methods, baselines, evaluation conditions, results and limits across independent works. Return source IDs/locators, applicability, unknowns, and the simplest test that could disprove each candidate's key assumption. Do not decide the winner yet.

## Evaluator

Using the frozen criteria, independently inspect the evidence where possible. Evaluate contribution to the main purpose and every hard constraint as pass/fail/unknown. Compare candidates under common conditions and revisit decisive source passages. Distinguish reported benchmarks from local measurements and estimates. Ignore the designer's preference; explain where evidence is not comparable. A repeated assertion is not additional evidence.

## Critic / verifier

Try to overturn the leading choice: find a simpler viable solution, an unsupported claim, an untested load/security assumption, a version mismatch, duplicate evidence, a conflicting result, and a likely operational failure. Check decisive source passages directly. Return actionable objections, not reflexive negativity or invented objections.

## Synthesizer

Reconcile evidence and objections rather than taking a majority vote. Recommend an approach only under explicit conditions. State rejected alternatives, remaining uncertainties, PoC acceptance criteria, and conditions that would change the recommendation. Remain provisional where hard constraints are unknown. Do not fabricate human approval.

## Handoff

Persist each role's useful findings in the shared report/ledger; do not dump internal deliberation. If all roles ran in the same conversation, describe this as sequential review, not an independent multi-agent evaluation.
Harness children do not write Memory. The outer skill may retain useful detailed verification/experiment records under [memory-workgraph.md](memory-workgraph.md), using actual receipts and preserved report snapshots.

<!-- proposed-method-report-v1:begin -->
## Method design roles and explanatory report

For the proposed-method profile, target five methods overall (baseline plus four alternatives), not five full training runs. Diagnose the failure; propose distinct mechanisms; challenge the closest prior art; formalize and simplify; design disconfirming tests; revise and explain the selected design. Role switching is not independent evidence.

The designer supplies `dossier_json.method_ideas` and its leading candidate's `presentation`, as defined in `proposed-method-report.md`. The reviewer checks this same contract and the parent-rendered `method_report_preview`. Check arrows against tensor/data flows, module IDs against prose, symbols against equations, and the side-by-side baseline diagram against controlled differences. A conceptual diagram does not count as an experiment. A rendered artifact is not a claim that a person or a model has visually inspected it.

Preserve unfavorable results and allow a proposal to remain provisional or be rejected. Explain why a method was chosen as the design focus separately from the final adoption decision. Never force a performance win to complete the report.
<!-- proposed-method-report-v1:end -->

<!-- upstream-research-workstreams-v2:begin -->
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
<!-- upstream-research-workstreams-v2:end -->
