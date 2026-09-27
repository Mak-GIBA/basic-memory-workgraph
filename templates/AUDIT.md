# Sequence integrity checks and evidence-backed repair

Integrity is separate from privacy review, successful tool execution and inferred
adoption. No periodic job is installed. Check after writing, before reuse, when
new evidence contradicts a record, and on explicit audit requests.

## Read-only CLI

Run the installed `workgraph_tools.py audit --memory-dir <registered-root>` with
optional `--note cases/example.md`. It prints JSON, never writes notes or review
stamps, and returns 0 for no structural issues, 2 for findings, 1 for invalid
invocation/path. `--dry-run` is accepted but audit is always read-only.

Reports contain note paths (hashed if privacy screening fails), controlled issue
codes/JSON locations, actions, and downstream dependency candidates up to depth 2.
No note bodies, user excerpts, raw IDs, credentials or link targets are echoed.
Unresolved relations may refer to another project; investigate, do not delete them.
Freeform Cases are reported as legacy, not silently converted or judged invalid.
A clean report does not prove that a sequence really happened in that order.

## Semantic inspection by the agent

1. Read the selected Case and available conversation/evidence. Compare the same
   deliverable, version, actor, output target and ordering. No raw transcript reads.
2. Distinguish a memory error from a real failed attempt or a user changing course.
   A later reversal does not make the earlier commit request fictitious.
3. Check assessments against their actual evidence. User requests to commit/push
   differ from autonomous execution, routine prearranged delivery and checkpoints.
   Correlated actions share an episode group. Repeated corrections/reversals on
   the same output must be considered; determine which aspect they affect.
4. If evidence determines the correct content, repair that content only. In v2,
   append a `repairs` record with reason, evidence and minimal sanitized before/after
   values. For legacy notes use a concise `## Integrity` explanation. Keep stable
   IDs and valid references; don't renumber all steps or guess missing chronology.
5. If evidence is insufficient, set `integrity_status: needs_review` and put the
   specific concern in `## Integrity`. Do not invent a corrected history. Report
   the uncertainty and omit suspect claims from positive recommendations.
6. Inspect linked derived knowledge at depth 1–2. Use CLI `affected` entries as
   candidates, not automatic proof of invalidity. Mark dependent claims/notes only
   when their support is faulty or uncertain; preserve independent support and
   unrelated statements. Do not delete or mass-rewrite the graph.
7. After a grounded repair, run structural checks and read back the note. Set
   `integrity_status: checked` only after resolving the concern. A successful check
   alone cannot resolve a semantic concern or authorize export. No-op checks leave
   the file untouched. After new material edits use unreviewed until inspected.

On any content or integrity edit set `privacy_review: pending` and remove
`review_sha256`. The separate sharing/training designation does not count as a
fresh review. `review`, `export-share` and `export-cases` reject needs_review notes
and structurally invalid interaction Cases. Structural checks rerun even if marked
checked. Imports reset checked to unreviewed, preserve needs_review, and never
turn imported content into instructions. A flag on any node type can suspend its
export, including a Rule with faulty supporting evidence.

Never log secrets in diagnostics, repair history or raw backups. If the error is
sensitive content, sanitize before recording a change; replace secret values with
neutral placeholders. Only material repairs or concrete concerns merit writes.
Plan/read-only mode allows reporting and skipping a claim in the current answer,
not writing flags, repair records or review stamps. A routine successful audit is
not itself a reusable knowledge note.
