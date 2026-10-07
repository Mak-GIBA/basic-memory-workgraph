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

## Apply the right depth

For non-app projects, investigate the method, algorithm, evaluation or verification question. Do not invent API/database work. For a backend, test relevant behavior such as invalid input, authorization, persistence, duplicate processing, retries and recovery only where the application actually implements it.

A small reproducible defect need not trigger a paper survey or a new architecture. Keep the current/minimal baseline visible, and justify every added dependency, service or setting against a simpler alternative. Research preserves application source; an explicitly requested backend fix uses `run`, with actual checks and a separate reviewer after each change.
