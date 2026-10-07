# Bounded role prompts

Use these as perspectives in one session or as prompts for native subagents if the host actually supports them.
They are not executable agent registrations. Do not assume parallelism, independent runs, or improved accuracy without evidence.
Share the same user goal, hard constraints, allowed tools, privacy rules, evaluation criteria, and budget with every role.
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
