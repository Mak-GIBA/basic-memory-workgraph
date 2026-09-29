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
- `packaged_as [[Artifact]]`
- `implements_workflow [[Workflow]]`

## Principles
- Current user instructions override older memory.
- Automatically save only verified transferable knowledge or explicit lasting preferences.
- Search before creating a new entity; duplicates without new evidence require no write.
- Never create work diaries or automatic session checkpoints.
- Structured Cases require explicit capture or the reusable case mode.
- Skill Artifacts describe only reviewed, validated registered Skills.
- Sharing and training permissions are independent and default to disabled.
- Preserve conditions and exceptions.
- Do not infer success from silence.
- A graph connection is evidence of relevance, not proof that an old rule applies.
