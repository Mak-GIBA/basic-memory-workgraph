# Implementation references

Implementation references checked for the standalone installer and harness v1.2.0 on 2026-10-04. The v1.2.1 instruction update on 2026-10-07 focuses on core logic, multi-source reading and optional Workgraph retention; it does not revalidate these external references. These are implementation references, not evidence that a particular architecture is universally best.

- [OpenAI, Build skills](https://learn.chatgpt.com/docs/build-skills): current local repository/user discovery uses `.agents/skills`; keep instructions focused and supporting scripts/resources in the skill. Older installs are detected and reused rather than duplicated.
- [OpenAI, Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode): structured `codex exec` output, output files, sandboxes and reuse of saved CLI authentication. Actual local capabilities are checked by doctor.
- [ECC GAN harness, immutable reference](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/scripts/gan-harness.sh): planner/generator/evaluator iteration and plateau stopping inspired this workflow. This kit supplies its own Codex-based implementation with parent-owned receipts and bounded scope; it does not install ECC or require Claude.
- [Agent Skills specification](https://agentskills.io/specification): portable `SKILL.md` conventions. Compatibility is not end-to-end testing in every host.
- [OpenAI Docs MCP](https://developers.openai.com/learn/docs-mcp): optional documentation source; no automatic registration.
- [arXiv API manual](https://info.arxiv.org/help/api/user-manual.html): query parameters and Atom responses.
- [arXiv API terms](https://info.arxiv.org/help/api/tou.html): request spacing/concurrency and service terms.
- [Semantic Scholar Graph API](https://api.semanticscholar.org/api-docs/graph): metadata search/lookup, references/citations and date filters.
- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/): work metadata and provenance.
- [Crossref REST filters](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/): publication-date filtering.
- [Context7](https://context7.com/docs/resources/all-clients): optional current-library documentation discovery; retain the underlying source/version.
- [Exa MCP](https://exa.ai/mcp): optional broader discovery; return to primary sources for a decision.

The scholarly provider references are retained from v1.1.0; provider behavior and terms must be rechecked when changing that code. The October update checked the skill/exec documentation and ECC reference; it did not repeat a live API evaluation of every optional service.

No third-party implementation is vendored. The maintained installer and skill sources live in `tools/design-research/`; the generated Bash distribution embeds those resources so it still works alone. Payload/file hashes detect accidental changes, not publisher authenticity. Mocked model tests do not establish real-model quality, GUI invocation or OS sandbox enforcement; see the repository's validation report.
