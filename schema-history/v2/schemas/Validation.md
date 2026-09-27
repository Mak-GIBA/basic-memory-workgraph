---
title: Validation
type: schema
entity: Validation
version: 2
schema:
  check(array): string, checks to perform
  validates_rule?(array): Rule, rules checked
  validates_workflow?(array): Workflow, workflows checked
settings:
  validation: warn
  frontmatter:
    sharing_scope?(enum): [private, team, public]
    training_use?(enum): [excluded, approved]
    privacy_review?(enum): [pending, passed]
    review_sha256?: string, fingerprint required for export
---

# Validation

A verification procedure. Never mark an unperformed check as PASS.
