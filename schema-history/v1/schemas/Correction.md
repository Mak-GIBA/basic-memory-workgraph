---
title: Correction
type: schema
entity: Correction
version: 1
schema:
  instruction: string, what the user explicitly corrected
  reason?: string, why the previous result was inadequate
  occurred_in?: Case, originating case
  generalized_to?(array): Rule, reusable rules derived from this correction
settings:
  validation: warn
---

# Correction

An explicit user correction. Do not infer corrections from silence.
