---
title: Rule
type: schema
entity: Rule
version: 2
schema:
  trigger: string, conditions where the rule applies
  action: string, behavior to perform
  exception?(array): string, when not to apply the rule
  learned_from?(array): Case, evidence cases
  implemented_by?(array): Workflow, workflows implementing the rule
  validated_by?(array): Validation, checks verifying the rule
  reason?: string, why the action helps
  transfer_use?: string, concrete use outside the originating project
  check?(array): string, evidence supporting the claimed effect
settings:
  validation: warn
  frontmatter:
    sharing_scope?(enum): [private, team, public]
    training_use?(enum): [excluded, approved]
    privacy_review?(enum): [pending, passed]
    review_sha256?: string, fingerprint required for export
---

# Rule

A reusable conditional rule generalized from evidence.
