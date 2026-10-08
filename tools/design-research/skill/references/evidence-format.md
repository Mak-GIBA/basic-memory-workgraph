# Evidence ledger contract (schema_version: 1)

Use `evidence.json` as the machine-checkable companion to the report, not as a replacement for readable analysis.
The default `validate` command checks structure and selected consistency rules. Add `--check-artifacts` to require actual local files and verify optional SHA-256 values. Neither mode verifies scientific interpretation or authenticates a human's approval.

## Top-level fields

| Field | Content |
|---|---|
| `schema_version` | Integer 1 |
| `question`, `scope` | Decision and applicability boundaries |
| `checked_as_of` | ISO date/datetime |
| `constraints` | `{id, text, kind}`; kind is hard/soft |
| `sources` | Source records below |
| `claims` | Claim records below |
| `candidates` | At least two candidates, with at least one baseline |
| `comparison` | Common-criteria findings, one entry per candidate/criterion |
| `experiments` | Planned/executed validation work; an empty list is allowed when no experiment is needed |
| `decision` | Conditional recommendation and approval state |

All IDs start with a letter and contain only letters/digits/underscore/hyphen, at most 64 characters.
Do not copy API search output directly into this ledger: first select the relevant works, actually read them, and write claims with correct scope.

## Source

```json
{
  "id": "S1",
  "title": "Actual source title",
  "url": "https://example.org/replace-with-real-source",
  "local_path": null,
  "source_type": "official_doc",
  "read_level": "relevant_sections",
  "peer_review_status": "not_applicable",
  "peer_review_evidence": null,
  "retrieved_at": "2026-09-30",
  "published_at": null,
  "version": "the version actually read",
  "study_id": "study-or-document-family-1",
  "correction_status": "not_checked"
}
```

`source_type`: paper / preprint / official_doc / standard / repository / experiment / secondary.
`read_level`: metadata / abstract / relevant_sections / full_text. Never promote this automatically because a PDF link exists.
`peer_review_status`: unverified / verified / not_applicable. `verified` needs `peer_review_evidence` identifying the actual proceedings/publisher confirmation and version, not an invented venue.
`study_id` groups the same research across preprint, conference, publisher, and repository pages. More records do not necessarily mean more independent evidence.
`correction_status`: not_checked / no_notice_found / notice_found / not_applicable. `notice_found` needs `correction_note`. `no_notice_found` means “none in the checks performed,” not “certainly never retracted”; describe the checked venues/date in the report.
Use a valid http(s) URL or a workspace-relative `local_path`, such as `experiments/run-01/results.json`. No fabricated local artifact.
Include DOI/arXiv ID, authors, license and exact code ref when available; additional fields are preserved by your JSON editor but not all are checked.

## Claim

```json
{
  "id": "C1",
  "statement": "Narrow claim supported under the stated conditions",
  "status": "reported",
  "confidence": "medium",
  "context": "Applicable version, task, dataset, or workload",
  "limitations": ["What this source does not establish"],
  "evidence": [{"source_id": "S1", "relation": "supports", "locator": "Section 4.2 / Table 2"}]
}
```

`status`: observed / reported / inferred / hypothesis / unknown. Local `observed` findings require an `experiment` source; published measurements are `reported` until reproduced here.
`relation`: supports / challenges / mixed / context. Keep contradictory evidence rather than silently deleting it.
`confidence`: unassessed / low / medium / high. High confidence requires supporting material read beyond metadata/abstract and cannot describe a hypothesis/unknown. This gate is necessary, not sufficient, for justified confidence.
Reported/observed/inferred claims need supporting evidence; use hypothesis/unknown for unsupported assumptions.

## Candidate and comparison

```json
{
  "id": "A",
  "name": "Minimal baseline",
  "baseline": true,
  "summary": "Components and execution flow",
  "hard_constraints": [{"constraint_id": "K1", "result": "unknown", "claim_ids": [], "reason": "Representative load not measured"}]
}
```

Every candidate must evaluate every hard constraint: pass/fail/unknown. Pass/fail needs a supporting `claim_ids` entry.
The validator does not infer whether the cited claim really proves that constraint; the evaluator must inspect it.

```json
{
  "criterion": "p95 latency under representative load",
  "candidate_id": "A",
  "finding": "Not yet measured",
  "basis": "unknown",
  "claim_ids": []
}
```

`basis`: measured / reported / estimated / unknown. Measured requires an observed claim; reported requires a claim reference; estimated requires `assumptions`. Add value/unit/conditions where actually known. Avoid false precision and compare all candidates on the same criteria.

## Experiment

```json
{
  "id": "E1",
  "hypothesis": "The additional planner improves success enough to justify its cost",
  "candidate_ids": ["A", "B"],
  "controls": ["Same task set, model version, permissions, and resource budget"],
  "metrics": ["Success rate", "Total tool/token cost", "p95 latency"],
  "acceptance": "Agree the success/cost threshold before running",
  "status": "planned",
  "artifacts": []
}
```

Executed experiments require actual `artifacts`; a plan is never reported as a measured result.
The scholarly CLI does not run experiments. The installed Bash harness can execute a declared bounded local PoC in a scratch workspace and record its actual command, status and results.

## Decision

```json
{
  "status": "provisional",
  "candidate_id": "A",
  "rationale": "The minimal baseline currently satisfies the known scope; decisive load behavior remains unverified",
  "claim_ids": [],
  "unresolved": ["Validate the workload-dependent hard constraint"],
  "revisit_when": ["The baseline fails the predeclared acceptance test"],
  "accepted_by": null,
  "accepted_at": null
}
```

`status`: provisional / proposed / accepted / deferred. Proposed/accepted needs a candidate and claim references, and all selected hard constraints must be known passes. A failing hard constraint is never selectable. Unknowns require provisional/deferred.
Accepted additionally needs authentic `accepted_by` and ISO `accepted_at`; the agent must not fabricate them.
`provisional-example.json` is an intentionally evidence-limited, synthetic example that passes structural checks with a warning. It is not a researched recommendation.

## Strict artifact checks and parent receipts

Schema version 1 remains compatible with the existing ledger and structural validator. Local source paths and experiment artifact paths are relative to the ledger's workspace, never absolute paths, traversal paths or symlinks. Optional `sha256` values must match the actual file. An executed experiment with a nonexistent or empty artifact is rejected by strict checks even if its schema is valid.

```bash
python3 -B <skill-dir>/scripts/research.py validate PROJECT/docs/design-research/SLUG/.internal/evidence.json --check-artifacts
python3 -B <skill-dir>/scripts/research.py validate PROJECT/docs/design-research/SLUG/runs/RUN_ID/reports/evidence.json --check-artifacts --artifacts-root PROJECT/docs/design-research/SLUG
```

The default artifact root is the ledger's parent. Archived ledgers retain original workspace-relative paths, so use `--artifacts-root` as above.

The harness adds a stronger provenance gate: an `executed` experiment must cite a successful parent-owned receipt for the same experiment ID, with no timeout/truncation. An `observed` claim must support its actual local experiment. Parent records include EV IDs, source fingerprints, command, exit code, timestamps, output hashes and declared generated artifacts. Files and stdout/stderr are checked again before evaluation and resume. A reviewer cannot create a receipt by claiming that a test passed.

Source-access receipts distinguish local/retrieved/unavailable and preserve access metadata. Fetching a page does not prove it was read or that it supports a claim. Decisive external claims still need primary sources, relevant-section reading and exact locators. The automated research workflow refuses an `accepted` decision; human adoption remains a separate decision.

For planned commands, declare generated files in `artifact_paths` if they need to survive scratch cleanup. Receipts and reports link real JSON, raw output, plots or images; missing output from a successful command blocks the run. A backend receipt does not prove a visual user flow, and a screenshot does not prove storage or authorization behavior.
