# Progressive interaction Case format v2

Use `cases/`, `type: case`, `schema: Case`, `capture_kind: interaction_case`, and
`case_format_version: 2`. Add `integrity_status: unreviewed` and the usual
`sharing_scope: private`, `training_use: excluded`, `privacy_review: pending`.
No schema migration or note rewrite is required for existing v1/freeform Cases.

One Case covers the same deliverable and purpose. Start after a meaningful correction
with future comparison value; append material steps from the available conversation
and evidence, including unfinished sequences. Search/read before creating or updating.
Similar work is not proof of continuity. Preserve old steps; do not invent missing ones.

Keep a compact searchable summary of context, mismatch and relevant changes in normal
Observations. The single JSON block under `## Interaction` is the canonical sequence.
Do not duplicate the full history in prose. Relations link real independently admitted
Corrections/Rules/Workflows; do not create a node per utterance.

## Strict v2 fields

- `version`: 2. `context`: purpose/audience/deliverable/constraints (strings or null),
  and a nonempty `scope` string. `request`: `{summary, excerpt}`. All excerpts are
  actual necessary sanitized text or null, never reconstructed quotations.
- `steps`: ordered observations with unique stable opaque `id`, `kind`, `actor`
  (user/assistant/tool), `target_id` (an earlier output or null if genuinely unknown),
  and `content` using the same text shape. Never use identities/paths as IDs.
- An `output` step additionally has `change` (text piece or null). Its target is
  the earlier output being revised; its content describes the new output.
- A `correction` or `action` step additionally has `signal` and `group_id`.
  Signals: none, commit_request, push_request, checkpoint_request, downstream_use,
  reuse_request, scope_narrowing, repeated_correction, revert_request,
  explicit_acceptance, explicit_rejection. Every signal needs observed evidence.
  group_id groups correlated requests, e.g. commit and push in one delivery episode.
  Requests and executed operations are separate observations with their real actors.
- A `verification` step additionally has `result`: passed/failed/inconclusive. Name
  the property actually checked in content; a passing check is not user satisfaction.
- `latest_output_id`: last recorded output ID or null. `state`: open/completed/abandoned;
  completed means the task phase is complete, not that the user is satisfied.
  `outcome`: unverified/partial/verified/rejected. Verified requires a passed check
  on that output and is limited to the described property. Recorded failures on the
  same output require a partial/rejected outcome until resolved against evidence.
- `acceptance`: unknown/accepted/rejected, plus `acceptance_evidence_ids`. Default
  unknown with an empty array. Accepted/rejected requires matching explicit user
  evidence on the latest output. Implicit behavior never populates this field; later contrary evidence requires
  reassessment rather than keeping stale acceptance.
- `assessments`: unique id, target_id (existing output), aspect (string), judgment
  (supported/tentative/unknown/contradicted), evidence_ids, counterevidence_ids,
  rationale (text piece). References must point to observations on that output.
  Inspect counterevidence before favorable reuse. Unknown may have empty evidence.
- `repairs`: concise corrections to the memory itself, not ordinary output revisions.
  Each has unique id, reason/evidence (text pieces), and nonempty changes with
  location (JSON pointer), before and after (sanitized JSON values). Follow AUDIT.md.
- `transfer_use`: concrete future comparison/learning use. Unknown context or results
  do not require inventing a universal lesson to justify a useful ongoing Case.

## Implicit adoption assessment

No evaluation prompt or praise is expected. Read the observed sequence:
user-requested delivery after revisions, downstream use, reuse of a format, explicit
narrowing of remaining changes, repeated corrections, or reversals. Autonomous
commits, prearranged delivery, backup/checkpoint requests and silence establish no
adoption. Merely changing topics also carries no positive/negative evidence.

Supported means an inference grounded in direct downstream/reuse behavior (or actual
explicit acceptance), never certainty of satisfaction. Delivery/narrowing alone is
at most tentative; no amount of commit/push counting upgrades it. Correlated actions
share a group, not independent votes. A user requesting a next task based on an output
supports use as a foundation, not truth of all its contents. A later reversal must
be considered; preserve the original action but revise the inference and its limits.
No probabilities or automatic global preference promotion.

Before reuse compare purpose, audience, deliverable, constraints and scope first,
then integrity and evidence. Read steps/assessments rather than trusting the search
summary. Extract applicable output characteristics and pitfalls for the initial
answer. Negative/unfinished Cases can help too. Current instructions take precedence.
A needs_review record is not a positive precedent. See AUDIT.md for grounded repair
and checking dependent knowledge. No-op recall/review produces no write.

## Fictional v2 example

This example has no explicit rating. Commit/push support tentative adoption only.
Never save the example as real user evidence.

```json
{
  "version": 2,
  "context": {
    "purpose": "Choose between options",
    "audience": "Decision makers",
    "deliverable": "Comparison briefing",
    "constraints": "Readable at a glance",
    "scope": "This briefing; cross-project preference not established"
  },
  "request": {
    "summary": "Compare the options and recommend one",
    "excerpt": null
  },
  "steps": [
    {
      "id": "o1",
      "kind": "output",
      "actor": "assistant",
      "target_id": null,
      "content": {
        "summary": "Long explanations before comparison",
        "excerpt": null
      },
      "change": null
    },
    {
      "id": "c1",
      "kind": "correction",
      "actor": "user",
      "target_id": "o1",
      "content": {
        "summary": "Put the comparison and recommendation first",
        "excerpt": null
      },
      "signal": "none",
      "group_id": "revision"
    },
    {
      "id": "o2",
      "kind": "output",
      "actor": "assistant",
      "target_id": "o1",
      "content": {
        "summary": "Comparison table and recommendation first",
        "excerpt": null
      },
      "change": {
        "summary": "Reordered the briefing; retained supporting detail",
        "excerpt": null
      }
    },
    {
      "id": "c2",
      "kind": "correction",
      "actor": "user",
      "target_id": "o2",
      "content": {
        "summary": "Only shorten the table labels now",
        "excerpt": null
      },
      "signal": "scope_narrowing",
      "group_id": "revision2"
    },
    {
      "id": "o3",
      "kind": "output",
      "actor": "assistant",
      "target_id": "o2",
      "content": {
        "summary": "Comparison first with shorter labels",
        "excerpt": null
      },
      "change": {
        "summary": "Shortened labels without changing the recommendation",
        "excerpt": null
      }
    },
    {
      "id": "v1",
      "kind": "verification",
      "actor": "tool",
      "target_id": "o3",
      "content": {
        "summary": "Checked that the label changes retained the quantities and units",
        "excerpt": null
      },
      "result": "passed"
    },
    {
      "id": "a1",
      "kind": "action",
      "actor": "user",
      "target_id": "o3",
      "content": {
        "summary": "Commit these revisions",
        "excerpt": null
      },
      "signal": "commit_request",
      "group_id": "delivery"
    },
    {
      "id": "a2",
      "kind": "action",
      "actor": "user",
      "target_id": "o3",
      "content": {
        "summary": "Push the committed revision",
        "excerpt": null
      },
      "signal": "push_request",
      "group_id": "delivery"
    }
  ],
  "latest_output_id": "o3",
  "state": "completed",
  "outcome": "verified",
  "acceptance": "unknown",
  "acceptance_evidence_ids": [],
  "assessments": [
    {
      "id": "assessment1",
      "target_id": "o3",
      "aspect": "Readiness to retain and share the briefing",
      "judgment": "tentative",
      "evidence_ids": [
        "a1",
        "a2"
      ],
      "counterevidence_ids": [],
      "rationale": {
        "summary": "The user requested retention and sharing after revisions. Both requests belong to one delivery episode; no satisfaction claim follows.",
        "excerpt": null
      }
    }
  ],
  "repairs": [],
  "transfer_use": "Compare presentation choices for future decision briefings with matching audience and purpose"
}
```

## Export and compatibility

The CLI accepts v1 and v2 without conversion and rejects unsupported/mismatched
versions. The JSONL envelope remains format_version=1; `interaction.version`
distinguishes payloads. V2 exports preserve steps, assessments, uncertainty and
repairs without turning an inference into a training label. Export still requires
separate training approval and a current privacy fingerprint. Needs-review or
structurally invalid notes cannot be reviewed/exported. Share/import also preserve
payloads; import resets checked integrity to unreviewed. Freeform Cases remain
valid memory but are not silently converted to training examples.

# Legacy interaction Case format v1

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
checks must describe performed checks, not future promises. An unverified v1 case is allowed only under an explicit scoped save request.
Progressive automatic capture uses v2 below; reusable mode still requires an observed result.

The CLI validates this shape strictly for JSONL; missing/unsupported versions are
reported, not silently repaired. Record related notes in normal typed Relations,
for example `- generalized_to [[rules/compare-compatible-quantities]]`. Create links
only when the target exists. JSONL includes the structured interaction and graph
relations; it is not a ready-to-train SFT messages file. Missing acceptance remains
unknown in exports, and downstream selection must preserve that distinction.

For abstract memories use normal observations, not this interaction block. For a
Skill Artifact use `kind: skill`, Skill name and a portable `skill:<name>` reference;
never put user-specific absolute paths into shareable content.
