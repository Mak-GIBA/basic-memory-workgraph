---
title: Workflow
type: schema
entity: Workflow
version: 3
schema:
  steps(array): string, ordered or practical work steps
  used_in?(array): Case, cases where this workflow was used
  implements?(array): Rule, rules implemented by this workflow
  checked_by?(array): Validation, checks for this workflow
  trigger?: string, applicability conditions
  exception?(array): string, limits and recheck conditions
  skill_decision?(enum): [memory_only, reuse_existing, update_existing, create_skill, deferred, unavailable]
  skill_reason?: string, packaging value or reason to retain memory
  skill_reviewer?: string, available reviewer used
  skill_review_basis?: string, evidence and compared skills
  skill_name?: string, portable skill identifier
  packaged_as?(array): Artifact, registered Skill artifact
settings:
  validation: warn
  frontmatter:
    integrity_status?(enum): [unreviewed, checked, needs_review]
    sharing_scope?(enum): [private, team, public]
    training_use?(enum): [excluded, approved]
    privacy_review?(enum): [pending, passed]
    review_sha256?: string, fingerprint required for export
---

# Workflow

A reusable way of doing work.
