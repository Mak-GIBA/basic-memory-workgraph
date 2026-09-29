---
title: Correction
type: schema
entity: Correction
version: 2
schema:
  instruction: string, what the user explicitly corrected
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
