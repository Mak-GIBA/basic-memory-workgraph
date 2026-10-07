---
name: ux-gan-harness
description: Run the installed Bash harness to review a rendered web app with screenshot evidence, compare similar apps, and optionally iterate UX fixes. Use for visual UI/UX audits or improving novice user flows. Review-only requests use audit; fixing requires a request to improve or fix the app.
---

# UI/UX GAN Harness

Use the real [gan-harness.sh](scripts/gan-harness.sh). Do not replace its execution with a prose review or invent a successful run.

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
