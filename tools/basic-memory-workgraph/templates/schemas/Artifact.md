---
title: Artifact
type: schema
entity: Artifact
version: 3
schema:
  kind: string, pdf / docx / pptx / code / report / skill / other
  location?: string, stable path or reference if safe to store
  produced_by?: Case, originating case
  skill_name?: string, registered skill identifier
  applicability?: string, conditions and exceptions
  check?(array): string, registration validation evidence
  implements_workflow?: Workflow, originating reusable workflow
settings:
  validation: warn
  frontmatter:
    integrity_status?(enum): [unreviewed, checked, needs_review]
    sharing_scope?(enum): [private, team, public]
    training_use?(enum): [excluded, approved]
    privacy_review?(enum): [pending, passed]
    review_sha256?: string, fingerprint required for export
---

# Artifact

A produced file or deliverable. Do not store secrets in paths or metadata.
