# Comparing agent designs

Start with the task and representative failure cases, not a framework name.

Compare, where relevant:
- Deterministic pipeline, single-agent tool loop, explicit state-machine workflow, supervisor/worker, and truly independent parallel researchers.
- Planner/executor split, tool-selection boundaries, retry/termination rules, checkpoints, human approvals, and recovery from partial failure.
- Memory strategy: no persistent memory, summaries, retrieval store, structured facts/graph, episodic traces, reusable workflows. Define what is stored, updated, forgotten, and scoped to a tenant.
- Tool permissions, prompt injection resistance, credential exposure, untrusted external content, and public/private information boundaries.
- Task success, factual/quotation accuracy, citation faithfulness, constraint violations, tool-call reliability, latency, token/tool cost, variance, and human correction burden.
- Operational burden: deployment, observability, evaluation data, schema/version migration, rollback, and debugging traces.

Document model/version, sampling settings, task set, tool API versions, concurrency, allowed retries, compute/token budget, cache state, and grading method.
Use a held-out or otherwise non-cherry-picked evaluation set. Prefer objective checks when available and describe limitations of LLM-as-judge.
Ablate one disputed component at a time: memory/no memory, single/multi-agent, planner/no planner, or retrieval strategy. Do not attribute gains to a component when model, budget, or data changed at the same time.
Report distributions/repeated trials when stochastic behavior could change the decision. No universal seed count or confidence threshold is required; justify effort according to the decision risk.

A valid conclusion may be “the single-agent baseline is sufficient; defer graph memory until error type X exceeds threshold Y.”
Do not force a complex architecture just to match a research paper or to justify this skill.
