---
title: Case
type: schema
entity: Case
version: 2
schema:
  task_type: string, kind of work performed
  status?: string, accepted / rejected / unverified / partial
  belongs_to?: Project, project or scope
  received?(array): Correction, explicit user corrections
  used?(array): Workflow, workflows used
  validated_by?(array): Validation, checks applied
  produced?(array): Artifact, output artifacts
  learned?(array): Rule, rules learned from the case
  request?: string, sanitized user request summary
  check?(array): string, performed checks
  transfer_use?: string, concrete future comparison or learning use
  generalized_to?(array): Rule, independently admitted lessons
settings:
  validation: warn
  frontmatter:
    capture_kind?: string, interaction_case for structured cases
    case_format_version?: integer, structured interaction format version
    sharing_scope?(enum): [private, team, public]
    training_use?(enum): [excluded, approved]
    privacy_review?(enum): [pending, passed]
    review_sha256?: string, fingerprint required for export
---

# Case

A concrete past task. Preserve the conditions, what happened, and outcome.

Optional structured interaction cases follow CAPTURE.md; legacy Cases remain valid.
