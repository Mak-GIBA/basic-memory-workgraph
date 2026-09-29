---
title: Validation
type: schema
entity: Validation
version: 1
schema:
  check(array): string, checks to perform
  validates_rule?(array): Rule, rules checked
  validates_workflow?(array): Workflow, workflows checked
settings:
  validation: warn
---

# Validation

A verification procedure. Never mark an unperformed check as PASS.
