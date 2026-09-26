# Interaction Case format v1

Use a Basic Memory `type: case` Markdown note in `cases/`. Existing freeform notes
need not change. Add `schema: Case` to explicitly resolve the existing capitalized
schema name. Fields shared by all new notes:

```yaml
sharing_scope: private
training_use: excluded
privacy_review: pending
```

Structured Cases additionally have `capture_kind: interaction_case` and
`case_format_version: 1`. Keep normal Observations (`task_type`, `status`, `check`)
and Relations for graph discovery. Put the canonical interaction data in exactly
one fenced `json` block under the exact heading `## Interaction`. Other prose may
explain applicability; do not duplicate the interaction in multiple formats.

```json
{
  "version": 1,
  "request": {"summary": "Produce an accurate comparison", "excerpt": null},
  "initial": {"summary": "Compared quantities with different denominators", "excerpt": null},
  "corrections": [
    {
      "feedback": {"summary": "The denominators differ", "excerpt": null},
      "change": {"summary": "Aligned denominators and labeled the comparison", "excerpt": null},
      "result": {"summary": "The comparison is now consistent", "excerpt": null}
    }
  ],
  "final": {"summary": "Delivered the corrected comparison", "excerpt": null},
  "outcome": "verified",
  "acceptance": "unknown",
  "checks": ["Recomputed both values with the same denominator"],
  "lessons": ["Compare quantities only after checking their denominator definitions"],
  "transfer_use": "Comparative reports in other projects"
}
```

This is a fictional format example, not knowledge to persist or automatic proof of
admission. `request`, `initial`, `final`, and each correction's feedback/change/result
use `{summary: string, excerpt: string|null}`. A missing initial or round result may
be null; do not invent it. `corrections` is ordered and may be empty for success cases.
Use sanitized excerpts only when they add value. No unredacted conversation logs.
`outcome` is verified/partial/unverified/rejected; `acceptance` is accepted/rejected/
unknown and requires explicit user evidence. `checks` and `lessons` are string arrays;
checks must describe performed checks, not future promises. An unverified case is
allowed only under an explicit scoped save request, not automatic reusable capture.

The CLI validates this shape strictly for JSONL; missing/unsupported versions are
reported, not silently repaired. Record related notes in normal typed Relations,
for example `- generalized_to [[rules/compare-compatible-quantities]]`. Create links
only when the target exists. JSONL includes the structured interaction and graph
relations; it is not a ready-to-train SFT messages file. Missing acceptance remains
unknown in exports, and downstream selection must preserve that distinction.

For abstract memories use normal observations, not this interaction block. For a
Skill Artifact use `kind: skill`, Skill name and a portable `skill:<name>` reference;
never put user-specific absolute paths into shareable content.
