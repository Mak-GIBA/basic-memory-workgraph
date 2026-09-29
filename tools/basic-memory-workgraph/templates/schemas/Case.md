---
title: Case
type: schema
entity: Case
version: 3
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
    case_format_version?: integer, structured interaction format version 1 or 2
    integrity_status?(enum): [unreviewed, checked, needs_review]
    sharing_scope?(enum): [private, team, public]
    training_use?(enum): [excluded, approved]
    privacy_review?(enum): [pending, passed]
    review_sha256?: string, fingerprint required for export
---

# Case

A concrete past task. Preserve the conditions, what happened, and outcome.

Progressive v2 Cases preserve steps, adoption evidence and repairs per CAPTURE.md.
Integrity review is independent of privacy/training approval.

Optional structured interaction cases follow CAPTURE.md; legacy Cases remain valid.
