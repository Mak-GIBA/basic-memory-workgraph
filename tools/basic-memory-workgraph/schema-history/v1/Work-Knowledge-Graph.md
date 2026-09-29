---
title: Work Knowledge Graph
type: note
tags: [knowledge-graph, workflow, memory]
---

# Work Knowledge Graph

## Node Types
- [[Case]]
- [[Correction]]
- [[Rule]]
- [[Workflow]]
- [[Validation]]
- [[Artifact]]
- [[Project]]

## Relation Conventions
- `belongs_to [[Project]]`
- `received [[Correction]]`
- `generalized_to [[Rule]]`
- `learned_from [[Case]]`
- `used [[Workflow]]`
- `implements [[Rule]]`
- `validated_by [[Validation]]`
- `produced [[Artifact]]`
- `related_to [[Case]]`

## Principles
- Current user instructions override older memory.
- Automatically save only verified transferable knowledge or explicit lasting preferences.
- Search before creating a new entity; duplicates without new evidence require no write.
- Do not automatically create work diaries, Cases, or session checkpoints.
- Preserve conditions and exceptions.
- Do not infer success from silence.
- A graph connection is evidence of relevance, not proof that an old rule applies.
