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
