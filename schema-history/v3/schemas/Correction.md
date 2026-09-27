---
title: Correction
type: schema
entity: Correction
version: 3
schema:
  instruction: string, what the user explicitly corrected
  context?: string, purpose audience output type and constraints actually known
  previous_output?: string, observed mismatch in the initial output or approach
  desired_output?: string, output characteristics explicitly requested by the user
  scope?: string, task or context where the correction applies
  exceptions?: string, known limits and conditions not established
  instruction_evidence?: string, sanitized user instruction supporting the desired output
  verification?: string, unverified partial verified or rejected with its tested scope
  result?: string, observed result only or unknown
  acceptance?: string, accepted rejected or unknown based on explicit user evidence
  reason?: string, why the previous result was inadequate
  occurred_in?: Case, originating case
  generalized_to?(array): Rule, reusable rules derived from this correction
settings:
  validation: warn
  frontmatter:
    sharing_scope?(enum): [private, team, public]
    training_use?(enum): [excluded, approved]
    privacy_review?(enum): [pending, passed]
    review_sha256?: string, fingerprint required for export
---

# Correction

An explicit user correction. Do not infer corrections from silence.

In scoped correction mode, retain context and desired output even before the
result is known. User instruction evidence is distinct from outcome verification.
Optional fields keep existing notes valid; new scoped captures follow CORRECTIONS.md.
