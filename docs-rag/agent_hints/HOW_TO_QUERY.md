<!-- RAG_HINT: single-include hint header. Orchestrators `cat` this file into
     subagent prompts instead of pasting a per-script RAG_NOTE. Canonical path:
     rag-bootstrap/agent_hints/HOW_TO_QUERY.md — edit here, lands everywhere. -->
RAG retrieval (saves tokens vs full-file Read):
- Endpoint: `$RAG_ENDPOINT_URL` if set, else `http://127.0.0.1:10000`.
- DEPLOYMENT: the `frontend` container is the host reverse-proxy INGRESS; the `api` service is NOT host-published, so do NOT omit `frontend` to "save compute" — it carries ALL API access (dropping it removes access, not a UI) and costs ~3MiB / 0% CPU.
- Query: `curl -sf -X POST "$RAG/api/v1/search" -H 'Content-Type: application/json' -d '{"query":"...","limit":5}'` (older servers: same body to `/api/search`; optional `"corpus":"<filepath prefix>"` scopes hits).
- Or CLI: `python3 <rag-bootstrap>/client/ragq.py "your question"` (`--corpus PREFIX` to scope; exit 3 = RAG down, fall back).
- MULTIKB gotcha: on a multi-KB instance, a query WITHOUT `--kb <name>` (CLI) / `"kb":"<name>"` (API body) hits the EMPTY default `ragdb` → returns nothing + exit 0, which looks exactly like a failed ingest. `rag list-kbs` shows the KB names; pass `"kb":"all"` to search across all.
- Response: JSON list of `{document_filepath, chunk_index, content, score, ...}`.
- Score semantics (0.5.1+): in the DEFAULT `hybrid` mode `score` is a rank-only RRF value (top hit ~0.01), NOT a relevance magnitude — don't threshold on it. For a comparable ~[0,1] similarity use `mode="semantic"` (there `score == cosine`) or read the new `cosine` field on each hit; `cosine` is None for keyword-only hits.
- Cite hits as `[[RAG:<document_filepath>#<chunk_index>@<score>]]`.
- On 5xx/429/timeout: retry ONCE after 2s, then fall back to grep + Read for the rest of this turn. Never block the workflow on RAG.
- Retrieval-only: DO NOT integrate RAG into the consuming project's own runtime.

Cite-not-copy / doc-pruning (0.4.3+):
- ALL files where a topic appears (not just top-N): `curl -sf -X POST "$RAG/api/v2/search" -H 'Content-Type: application/json' -d '{"query":"...","kb":"all","all_mode":true,"group_by":"file","max_results":200}'` — every file above an ADAPTIVE relevance bar + `total_matched`; returns `[]` + a `warning` when the topic is absent (never padded/hallucinated), so "I checked everything and found N" is trustworthy.
- Find copy-paste to merge/cite: `curl -sf -X POST "$RAG/api/admin/similarity-report" -d '{"kb":"all","threshold":0.9,"classify":true,"copied_only":true}'` — near-dup pairs labelled `copy-paste` (verbatim, no attribution) vs spared `citation`/`same-topic`. Or CLI: `rag duplication-map --copied-only`.
- The HTTP API is the FULL contract — raw requests do everything. `client/ragq.py` is OPTIONAL ergonomics (adds the reload-window retry/fallback + `exit 3`); non-Python or minimal consumers can skip it and hit the API directly.
Full contract: `rag-bootstrap/docs/integration/CONSUMING_AGENTS_CONTRACT.md`.
