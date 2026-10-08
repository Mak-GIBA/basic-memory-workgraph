---
name: ux-gan-harness
description: Run the installed Bash harness to review a rendered web app with screenshots and actual operations, using OOUI and cognitive-load guidance, compare similar apps, and optionally iterate UX fixes. Review-only requests use audit; fixing requires a request to improve or fix the app.
---

# UI/UX GAN Harness

Use the real [gan-harness.sh](scripts/gan-harness.sh). Do not replace its execution with a prose review or invent a successful run.

The harness supplies the same bundled OOUI and cognitive-load review policy to its planner,
reference researcher, fixer and independent reviewer. Follow the audience in the user's brief.
Evaluate object/action context, retained state and unnecessary remembering/searching/backtracking,
as well as functional completeness, visual defects and actual outcomes. Fixed-target procedures,
search, bulk actions and necessary confirmations are judged in context. Element counts alone
do not establish improvement or regression. Reading the available yomiyasu skill and polishing
Japanese UI drafts, design notes and review/fix-report prose is recommended. Preserve claims,
terms, IDs, numbers, conditions, outcomes, evidence and certainty; keep short labels concise.
For child results, polish narrative fields before returning JSON, retaining its keys/enums and
evidence references. Do not rewrite generated reports or archived results after publication.
If yomiyasu is unavailable, continue the writing checks without installing it during a run.

Before design, review or fixes, search and read relevant past feedback in the configured
Basic Memory project when available. Follow the recall procedure in the bundled OOUI
review policy, supplied as design_guidance to every role.
Compare the prior context, scope, exceptions and evidence with the current audience and brief.
Use matching feedback as a design/check candidate, verifying current issues and resolutions
with fresh screenshots and operations. Cite an applied note and why it fits in existing
findings; do not create another report. Memory recall is read-only, and unavailable Memory
or no matching notes does not block a run.

1. Read the target repository's rules. Discover its start command, test commands and URL from the supplied context, README, manifests and running servers. This setup discovery is allowed before screenshots; do not infer UX findings from UI code.
2. Choose `audit` when the user asks for review only, forbids code edits, or has not requested fixes. Choose `run` when fixes are requested. A request to install or author this harness does not authorize fixing an unrelated app.
3. Resolve this skill's own directory. Run `bash <skill-dir>/scripts/gan-harness.sh doctor --project <app-dir>`; address discoverable setup problems within the authorized scope. Do not change the user's personal Codex settings to make a test pass.
4. Launch the Bash entry point, reporting the exact command and run ID:

   ```bash
   bash <skill-dir>/scripts/gan-harness.sh audit --project <app-dir> --url <app-url>
   bash <skill-dir>/scripts/gan-harness.sh run --project <app-dir> --url <app-url> --test-command '<required check>'
   ```

   If the harness must own the preview process, add `--start-command '<repo start command>'`. Repeat `--test-command` for required checks. Use test data and the app's isolated test environment for create/edit/delete operations. Public send, publish, charge and production-data actions need authorization from the user's request.
5. Keep the process running until it completes, updating the user from its phase messages. Inspect its status and exit code; an interrupted, blocked or incomplete run is not a pass. Resume with `resume <run-id> --project <app-dir>` after resolving the cause.
6. Open the report and representative before/after images. Report screen/flow counts, severity counts, changes, remaining issues and limits, with links. Say that this is AI evaluation from the novice perspective; do not claim human usability testing.

The harness uses existing Codex model/auth settings and independent planner/reviewer/fixer executions. `UX_GAN_CHILD=1` marks a child execution: in that case follow the supplied role and **never start another harness**.

For controls, artifact layout and execution limits, read [the runtime guide](references/runtime.md). The child role prompts enforce screenshot-first decisions and assess whether each fix keeps the UI simple.
