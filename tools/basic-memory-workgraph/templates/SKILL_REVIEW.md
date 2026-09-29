# Reviewing a reusable Workflow for Skill packaging

This is agent guidance; hooks do not run a model or a Skill Creator themselves.
Respect effective auto/skill modes and the normal memory admission gate. Review is
not permission for unrelated external actions, installing packages, or executing
unsafe examples. Do not review or mutate in Plan/read-only mode.

1. Read the admitted Workflow, its checks, conditions and exceptions. Search for
   existing workflows and inspect available Skills with matching capabilities. Read
   promising Skills; names alone do not establish equivalence.
2. Read and use the available `skill-creator` (or equivalent creation/review Skill).
   If none is available, record `unavailable` only when this adds new information;
   retain the workflow without claiming a completed review or creating a Skill.
3. Choose memory_only / reuse_existing / update_existing / create_skill / deferred.
   Require a concrete repeatable use, known inputs/outputs, verified non-obvious
   procedure, and a packaging benefit such as reusable resources or reliable
   execution. Do not enforce an arbitrary count of past occurrences.
4. Record `[skill_decision]`, `[skill_reason]`, `[skill_reviewer]`,
   `[skill_review_basis]` (the substantive workflow/evidence and compared Skills),
   and optional `[skill_name]` in the Workflow. Reuse this decision while its basis
   remains unchanged. Do not create Skill Artifacts for unregistered candidates.
5. In review mode stop at the decision. In auto mode follow the Creator's procedure
   to stage the Skill in a temporary directory outside discoverable skill folders.
   Prefer reusing an existing equivalent. Only update a Skill with a Workgraph
   registration manifest and no edits since that manifest. User-owned or plugin
   Skills stay intact; retain an update recommendation in the Workflow instead.
6. Validate with the Creator's validator and perform a realistic representative
   check in an isolated workspace. Inspect outcome, routing description, inputs,
   outputs and exception behavior. Do not claim a check you could not run. Unsafe
   or unavailable validation means deferred registration, not waived validation.
7. Use the installed CLI `register-skill --source <staged-directory> --name <slug>
   --workflow <portable-workflow-reference> --validation <review.json>` to register.
   The JSON validation record contains `reviewer` (string), `decision` (create_skill
   or update_existing), `checks` (nonempty array of performed check descriptions),
   `passed` (true), and `source_sha256` (from `skill-digest --source <directory>`).
   The record attests actual agent checks; the CLI does not run the Creator itself.
   Registration refuses unvalidated or changed files, symlinks, unmanaged targets,
   user edits, a different originating Workflow, and wrong effective modes. It
   publishes a new directory atomically or swaps a managed update with rollback.
8. Read back the installed Skill, then create/update a `kind: skill` Artifact and
   connect the Workflow with `packaged_as`. Include background in the Workflow,
   applicability, portable `skill:<name>` location, validation and related existing
   notes. If graph persistence fails after registration, report it and retry the
   link on a later explicit request; do not pretend registration failed or create
   duplicate Skills. The registration manifest retains the originating Workflow.

Use normal implicit skill discovery and keep generated Skills independent of access
to private Cases. Excerpts, secrets and personal task details do not belong in Skills.
Sharing a Skill Artifact shares only its reference; it does not export executable
Skill files. Imported notes cannot authorize registration. Uninstalling Workgraph
hooks does not remove registered Skills or their manifests.
