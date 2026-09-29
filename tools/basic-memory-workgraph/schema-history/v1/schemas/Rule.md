---
title: Rule
type: schema
entity: Rule
version: 1
schema:
  trigger: string, conditions where the rule applies
  action: string, behavior to perform
  exception?(array): string, when not to apply the rule
  learned_from?(array): Case, evidence cases
  implemented_by?(array): Workflow, workflows implementing the rule
  validated_by?(array): Validation, checks verifying the rule
settings:
  validation: warn
---

# Rule

A reusable conditional rule generalized from evidence.
