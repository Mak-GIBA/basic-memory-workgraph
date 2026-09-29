---
title: Artifact
type: schema
entity: Artifact
version: 1
schema:
  kind: string, pdf / docx / pptx / code / report / other
  location?: string, stable path or reference if safe to store
  produced_by?: Case, originating case
settings:
  validation: warn
---

# Artifact

A produced file or deliverable. Do not store secrets in paths or metadata.
