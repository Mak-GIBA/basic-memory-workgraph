# Contextual correction capture and recall

Use `type: correction`, `schema: Correction` in `corrections/`. This is ordinary
Basic Memory Markdown, not an interaction Case or an automatically approved Rule.
Existing freeform Corrections remain valid. In `correction=scoped`, explicitly
observed user adjustments qualify even before their outcome is known. In `off`,
capture requires an explicit request to save the correction.

Record the narrowest scope supported by the conversation. Use concise observations
with the names below; unknown context can be stated as unknown. Initial output,
motives, excerpts, results and acceptance must never be reconstructed. Summaries
and actual necessary sanitized excerpts must be distinguished.

```markdown
---
title: Comparison requested before detail in a decision briefing
type: correction
schema: Correction
sharing_scope: private
training_use: excluded
privacy_review: pending
---

## Observations
- [context] Purpose: choose between options. Audience: decision makers. Output: briefing. Length constraint: unknown.
- [previous_output] The initial response led with detailed explanations of each option.
- [instruction] Summary: show a comparison and recommendation first, then supporting detail.
- [desired_output] Comparison table, recommendation and reason, followed by supporting explanations.
- [scope] The current decision briefing. Cross-project standing preference not established.
- [exceptions] Applicability to tutorials or detailed technical references is unknown.
- [instruction_evidence] User explicitly requested this order in response to the initial briefing; summarized, not quoted.
- [verification] unverified: the revised briefing has not been checked.
- [result] unknown
- [acceptance] unknown
```

This is a fictional example, not evidence to persist. Reason is optional: record
it only when the user gave it or an observed check supports it. Instructions are
evidence of desired behavior, not proof of effectiveness. Even a task-specific
visual adjustment can be captured with that limited scope; never turn it into a
global preference. Ordinary new task requests and acknowledgments are not corrections.

Before capture, search the same contextual correction and read likely matches.
No new information means no write. New results or a revised instruction in the same
scope update the existing note, keeping useful conditions. Distinct contexts may
coexist; do not overwrite a technical reference preference with a briefing preference.
Remove secrets, confidential information and unnecessary personal data before any
write, including from titles and links. Clear privacy_review/review_sha256 after
edits, leaving privacy_review=pending. Read back once after writing.

## Recall before drafting

1. Identify known purpose, audience, output type and constraints in the current request.
2. Search Corrections with those terms and likely requested output characteristics.
   Read promising notes; optionally follow real Case/Rule/Workflow relations at depth 2–3.
3. Compare scope and exceptions. Apply supported matching scope; analogous scoped
   examples can inform a suitable output choice but are not instructions for all work.
4. Prefer current user instructions over older corrections. If context differs,
   do not import the old choice blindly. Unknown outcome does not erase an explicit
   request, but cannot support claiming the old output succeeded.
5. Use applicable evidence in the initial output. Do not persist a recall diary.

Only independently admitted abstract lessons become Rules. A useful full interaction
may become a Case under its separate admission rules. In case=progressive, useful
ongoing sequences use v2 and keep the observed stages instead of overwriting them. Link existing nodes with
`occurred_in [[Case]]` or `generalized_to [[Rule]]` when meaningful. No companion
nodes are required. Corrections are excluded from `export-cases`; they can inform
a later approved structured Case, without inventing unknown outcomes. Sharing
still requires independent explicit designation and content review.

Before reuse also check integrity under AUDIT.md. A suspected sequence error is not
proof that the user changed their mind. Mark unresolved notes needs_review; resolve
only with evidence and inspect affected derived knowledge. No integrity edits in Plan.
