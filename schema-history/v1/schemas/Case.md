---
title: Case
type: schema
entity: Case
version: 1
schema:
  task_type: string, kind of work performed
  status?: string, accepted / rejected / unverified / partial
  belongs_to?: Project, project or scope
  received?(array): Correction, explicit user corrections
  used?(array): Workflow, workflows used
  validated_by?(array): Validation, checks applied
  produced?(array): Artifact, output artifacts
  learned?(array): Rule, rules learned from the case
settings:
  validation: warn
---

# Case

A concrete past task. Preserve the conditions, what happened, and outcome.
