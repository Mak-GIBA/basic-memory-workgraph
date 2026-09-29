---
title: Workflow
type: schema
entity: Workflow
version: 1
schema:
  steps(array): string, ordered or practical work steps
  used_in?(array): Case, cases where this workflow was used
  implements?(array): Rule, rules implemented by this workflow
  checked_by?(array): Validation, checks for this workflow
settings:
  validation: warn
---

# Workflow

A reusable way of doing work.
