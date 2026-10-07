# Evidence providers and helper commands

## Select by question

| Question | Preferred source | Fallback / limitation |
|---|---|---|
| Published method and alternatives | Original paper, official proceedings/publisher, arXiv author version | Metadata/abstract is discovery, not an experimental verdict |
| References and follow-on work | Semantic Scholar Graph API | Coverage/rate limits vary; citations are not endorsements |
| DOI, venue, metadata updates | Crossref | Review status and retractions need direct verification; metadata can be incomplete |
| API guarantees / current limits | Vendor's official docs, standard/RFC, release notes | Context7 is an index: retain the underlying source and exact version |
| Existing project compatibility | Local repository and tests; existing GitHub connector/MCP | Do not export private source to public search |
| Broader candidate discovery | Existing web search or Exa MCP | Return to primary sources for the decision |
| Prior project decisions | Existing Workgraph/Basic Memory | Revalidate age and scope; do not overwrite policy |

## Locate the script

Resolve `scripts/research.py` relative to the directory containing the active `SKILL.md`, not the current project working directory.
For the default user install:

```bash
DR="$HOME/.agents/skills/design-research/scripts/research.py"
python3 -B "$DR" providers
```

For a new `--project` install, use that project's `.agents/skills/design-research/scripts/research.py` instead. Existing legacy installs are updated in place; use the actual path printed by the installer or resolve the active `SKILL.md` directory. Multiple existing placements require explicit `--skills-dir` selection.
The script needs Python 3.10+, network permissions for live search, and Linux/macOS/WSL for its per-host locking.
No pip/npm install, LLM API key, Spec Kit, Basic Memory, or MCP server is required by the script.
The scholarly CLI works without Codex. The separate `gan-harness.sh` needs structured Codex exec and a working command sandbox; see `runtime.md`.

## Bounded discovery

```bash
python3 -B "$DR" search --provider all --query 'agent memory retrieval benchmark' --limit 5 --allow-network
python3 -B "$DR" search --provider arxiv --query 'all:"agent memory"' --year-from 2024 --limit 10 --allow-network
python3 -B "$DR" search --provider crossref --query 'agent memory evaluation' --limit 5 --offset 5 --allow-network
```

Query syntax and date semantics differ: arXiv uses its advanced syntax and submission dates; Semantic Scholar uses its search grammar and publication-date/year filter; Crossref uses bibliographic relevance and publication dates. Do not claim identical corpus coverage.
`--limit` is per provider. The output includes `next_offset` when known; fetch another bounded page only when useful.
Do not retry forever or replace an API failure with a claimed zero-result search. Exit 2 means one or more providers failed, even if others returned usable results.
`family_id` links records sharing DOI/arXiv identity within a response; titles alone are not merged. Manually reconcile missing IDs and cross-response duplicates.

## Exact lookup and citation traversal

```bash
# Replace identifier values with IDs actually returned by search.
python3 -B "$DR" lookup --provider crossref --id '10.1234/replace-with-real-doi' --allow-network
python3 -B "$DR" lookup --provider arxiv --id '2501.00001v1' --allow-network
python3 -B "$DR" links --id 'ARXIV:2501.00001' --direction citations --limit 10 --allow-network
```

These IDs illustrate syntax; they are not recommendations or verified references.
Semantic Scholar also accepts `DOI:...`, `CorpusId:...`, or its 40-character paper ID.
`links` returns one page only. Inspect reference/citation papers; the existence of an edge does not establish agreement or replication.
Crossref preserves `relation` and `update-to` metadata. The helper does **not** query every inverse notice or authenticate the absence of retractions.

## Network, credentials, and cache

Network requests are GET-only to the three fixed academic hosts; there is no generic fetch, PDF downloader, or code executor.
`--allow-network` is explicit permission to send the query from the local CLI. The surrounding agent must still follow host policies and avoid restricted information.
`SEMANTIC_SCHOLAR_API_KEY` is optional at the code level but may be necessary for reliable service access/quota. `CROSSREF_MAILTO` optionally identifies a contact in Crossref requests. Set these through your own secret/environment manager; do not put real values in a repository, prompt, URL, or shell history.
No credential is written to the cache or printed by diagnostics. Existing MCP providers may have their own paid plans/keys; this installer does not subscribe to anything.

Responses are cached under `${XDG_CACHE_HOME:-$HOME/.cache}/design-research/`; query/abstract content can be sensitive even without credentials. Keep the cache local. Response files use owner-only permissions.
Use `--cache-dir` for an isolated cache. `--cache-ttl` defaults to 86400 seconds. `--offline` makes no request, returns exact cached data only, and marks stale responses. A cache miss is an error, not an empty result.
Per-host locks serialize local CLI processes using the same cache. arXiv waits at least 3.1 seconds between requests and permits one in flight. This is not a distributed limiter: coordinate all machines under your control under the provider terms.
Retries are bounded. Long Retry-After instructions stop the request rather than retrying early.

## Full-text and technical-document reading

Use the host's existing browser/fetch/PDF capability, lawful institutional access, or user-provided documents.
Open the original passage and record a page/section/table locator. Inspect rendered figures/tables where they matter.
No PDF extraction/OCR service is installed; abstracts and open-access links do not mean the full paper has been read.
For vendor-specific research without web/docs tools, list the exact official checks still required instead of inventing limits.
Optional MCP registration examples are in `mcp-examples.toml`; the installer only prints them when asked and never applies them.

## Ledger validation

```bash
python3 -B "$DR" validate docs/design-research/TOPIC/evidence.json --check-artifacts
```

Plain `validate` remains the schema-v1 structural check. `--check-artifacts` additionally requires local artifacts to exist and verifies optional hashes. `--artifacts-root PATH` selects the original workspace when validating an archived ledger. This does not authenticate execution or scientific conclusions; parent-owned harness receipts and independent review provide additional checks.
