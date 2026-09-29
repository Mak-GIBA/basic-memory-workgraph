---
title: Project
type: schema
entity: Project
version: 3
schema:
  scope: string, what this project represents
settings:
  validation: warn
  frontmatter:
    integrity_status?(enum): [unreviewed, checked, needs_review]
    sharing_scope?(enum): [private, team, public]
    training_use?(enum): [excluded, approved]
    privacy_review?(enum): [pending, passed]
    review_sha256?: string, fingerprint required for export
---

# Project

A project, repository, workstream, or durable scope.
