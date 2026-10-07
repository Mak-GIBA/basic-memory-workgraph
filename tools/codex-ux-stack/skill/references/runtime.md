# Runtime guide

`audit` writes evidence and reports without editing application source. `run` captures a baseline and iterates up to five times. `resume RUN_ID` keeps the original baseline and evidence; it refuses unrelated source changes. Interrupted or unvalidated fixes preserve the diff and require a new audit/run. `doctor` checks CLI capabilities, the host's Codex sandbox and Chromium by actually launching the local browser bridge on a blank page.

Common flags: `--project PATH`, `--url URL`, `--start-command COMMAND`, repeatable `--test-command COMMAND`, `--review PATH`, repeatable `--reference-url URL`, `--max-iterations N`, `--phase-timeout SECONDS`, `--model MODEL`, `--browser auto|local-playwright`. The normal browser order is Browser plugin, configured Playwright MCP, then the bundled local Playwright bridge after a recorded failure. Explicit `local-playwright` chooses that bridge directly.

The role execution timeout defaults to 1800 seconds; readiness waits up to 60 seconds. There is no automatic dependency installation in a target project. Source changes stay as a diff; there are no automatic commits, resets or deployments. The harness stops if it sees source changes outside a fixer's declared files or during a review. It cannot attribute simultaneous edits to the same file by another process: avoid concurrent editing of the target while running fixes.

Results: `reviewed` means a review completed, not that the app passed. `passed` means the scoped improvement gates passed. `incomplete` or `stalled` exits 2; `blocked` exits 1; interrupt exits 130. Missing screenshots, malformed output and blocked required flows cannot pass.

Per-run artifacts live in `artifacts/ux-gan/RUN_ID/`, with JSON role results, redacted JSONL logs, coverage, tests and status. Images are archived under `docs/ui-ux-review-assets/RUN_ID/` after each role; they are not kept in `test-results`. The latest report is `docs/ui-ux-review.md`; comparison and before/after results are `docs/ui-ux-reference-apps.md` and `docs/ui-ux-fix-report.md`. Previous reports and their linked local images are copied into the run's `input/` directory before replacement. Each run also holds its own report copies.

Structured results and screenshot existence checks support reproducibility; they do not prove that an AI's severity judgement matches an actual novice's experience. Native Browser/MCP screenshots must be copied into the run's `screenshots/` directory and referenced in the role's evidence list. The local bridge additionally records tool-generated frame hashes and before/after action history. Public reference screenshots and live target screenshots remain distinct.

Version 1.1.0 bundles its own `references/design/` copy of the canonical ooui-design guidance,
including an index, shared review policy, modeling decisions, all 29 cognitive-load tips,
quality checks and sources. It does not depend on a sibling skill or the target app to supply
these files. Source checkouts/extracted distributions read the canonical files in the same
distribution. `doctor` and execution preflight reject missing, empty or invalid bundles.
Each role's `prompt.txt` includes the policy summary, version, reference paths and hashes;
read the detailed references only when relevant. Role result schemas and CLI flags are unchanged.

OOUI observations go into screen information/interaction; remembering, searching, comparing,
guessing, backtracking and re-entry go into flow friction and simplicity. The representative
flow and counting method belong in simplicity's rationale. Required information, appropriate
confirmations and state recovery matter alongside density. These are AI observations supported
by operations and images, not measured cognitive workload or human satisfaction.
When resuming older runs, prior evidence remains intact; newly executed roles receive the
current policy. An already completed older run is not re-evaluated by `resume`; start a new
audit/run to assess it under the new guidance.
