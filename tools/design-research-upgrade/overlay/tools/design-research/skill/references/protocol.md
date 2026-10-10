# Research protocol and stop rules

The table below sets per-task reading/discovery budgets. The installed Bash harness additionally enforces execution limits described in `runtime.md`.
The CLI independently caps each request to one page of 1–50 results and at most two HTTP attempts.

| Mode | Search calls | Decisive sources to read | Candidates | Citation expansion |
|---|---:|---:|---:|---|
| Quick | Up to 4 | Up to 4 | 2 | Usually none |
| Standard (default) | Up to 8 | Up to 10 | 2–3 | One hop from at most 2 seed papers |
| Deep (explicitly justified/requested) | Up to 20 | Up to 25 | Up to 5 | One hop from at most 5 seed papers |

A search call with `--provider all` contacts up to three services; include these requests in the privacy/time budget.
The harness's frozen plan permits at most 8 provider requests with 1–10 results each, including all-provider expansion. Deep work beyond this limit requires separately scoped research, not silent budget growth. Each iteration allows at most 3 local PoCs, at most 5 evaluations including the first, and two consecutive non-improving evaluations stop the loop.
Use provider-specific queries for precise search semantics. No automatic pagination or recursively expanding citations.
Stop when hard constraints and decision-changing claims are adequately covered, or when the budget is reached.
State unsearched areas and unresolved contradictions. Two consecutive search passes adding no material evidence is a useful stop signal, not proof of exhaustiveness.

## Quality gates

1. Problem gate: a concrete decision, context, hard requirements, and explicit assumptions exist.
2. Alternative gate: include a viable minimal/current baseline and a genuinely different option.
3. Evidence gate: important claims have direct sources/locators; unread sources and inferences are labeled.
4. Comparison gate: common conditions; no fabricated metrics; hard constraints evaluated separately.
5. Challenge gate: inspect failure modes, contradictory sources, and reversibility of the choice.
6. Validation gate: decisive uncertainty is measured or has an explicit bounded PoC plan.
7. Decision gate: a conditional recommendation, rejected alternatives, unresolved risks, and revisit triggers exist.

Do not increase confidence just because more agents repeat a claim. Separate roles can diversify scrutiny but do not guarantee accuracy or independence.
Conclusions outside a paper's dataset/task/model/resource conditions are inferences, not reproduced findings.
Prefer qualitative trade-off explanations to false numerical precision. Evaluate time-to-deliver and operational complexity alongside experimental performance.

## Read multiple works in depth

For method or accuracy comparisons, normally read at least two independent relevant primary works, including papers where applicable. Compare their methods, evaluation data/task/model/version, metrics, baseline/control, resources, results and limitations. Read the decisive methods, evaluation and discussion sections; inspect rendered tables/equations/figures when the decision depends on them. An abstract, search snippet or retrieval receipt does not establish this depth.

Record source IDs and exact pages/sections with claims and applicability conditions in the existing dossier. Group preprint/published versions and mirrored material as one study. Include conflicting or negative evidence, explain differences in conditions, and distinguish literature results from this project's measurements. The reviewer revisits decisive passages rather than accepting the producer's summary.

Use the existing budget; thorough reading does not require expanding search calls. If access or the budget prevents sufficient reading, identify what is missing and keep the affected recommendation provisional/deferred. Do not invent additional works or claim full-text reading from partial access. This is a skill/role instruction; the harness does not add a numerical source-count gate or prove reading quality.

## Apply the right depth

Start with the project's main purpose and the core logic contributing to it: retrieval/ranking, extraction, classification, inference, decision rules or other domain computation. Define outcome metrics and representative success/failure cases against the current/minimal baseline. Prioritize improvements that affect that purpose while preserving hard constraints.

For non-app projects, investigate the method, algorithm, evaluation or verification question. Do not invent API/database work. Backend behavior is included when relevant; test invalid input, authorization, persistence, duplicate processing, retries and recovery where the application actually implements them and they affect the requested outcome or constraints.

A small reproducible defect need not trigger a paper survey or a new architecture. Keep the current/minimal baseline visible, and justify every added dependency, service or setting against a simpler alternative. Research preserves application source; explicitly requested core-logic/backend improvements use `run`, with actual checks and a separate reviewer after each change.

<!-- proposed-method-report-v1:begin -->
## Proposed-method profile: five-way reasoning and required Methods chapter

The Skill selects proposed-method when a detailed proposed Methods chapter is part of the requested outcome. General selection/effectiveness comparisons default to comparison. First freeze purpose, final-outcome metrics and measurement scope using [effectiveness-evaluation.md](effectiveness-evaluation.md). For proposed-method the generic two/three-candidate guidance above is superseded by a target of five methods including the baseline. The fixed search/PoC budgets remain unchanged. Fewer methods require `comparison_plan.exception_reason`; do not pad the count or quietly increase the budget.

Follow `proposed-method-report.md`: include a deeply specified design, three kinds of explanatory figures, exact source/experiment/component cross-links and the hypothesis-to-test mapping. The parent renders deterministic SVGs from a safe graph representation before review and includes the final chapter and images in the canonical report and its archived snapshot. It does not execute diagram code, call an image service, install rendering dependencies, or infer empirical support from file existence.

`--report-profile comparison` retains comparison-only reporting. The persisted profile and target count remain fixed on resume. Historical runs without these fields retain their historical contract.
<!-- proposed-method-report-v1:end -->

<!-- upstream-research-workstreams-v2:begin -->
## 読み手に伝わる報告と再検討

通常のresearch/audit/runでは`--reader-friendly`を付け、`references/readable-documents.md`に従う。
提案手法の詳細章が必要な研究では`--report-profile proposed-method --target-methods 5`を選ぶ。
汎用比較ではcomparisonを使い、主要効果の実測と設計・文献調査の未測定を区別する。
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
