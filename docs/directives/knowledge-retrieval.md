# Knowledge Retrieval

**Purpose.** Retrieve just-in-time, not just-in-case. Context is a finite budget; loading everything
"in case" is how you end up with less recall, not more.

- **Check before you build, closest first:**
  1. **This project's docs-rag** — `http://127.0.0.1:10060`, semantic search over our own `docs/` tree.
     Cheapest way to find which file answers a question without reading 1000-line documents.
     Start/stop/re-ingest: [../runbooks/docs-rag.md](../runbooks/docs-rag.md).
  2. `grep` over `docs/findings/` and `docs/research/` — still the fastest exact-match tool, and it
     always works even when the stack is down.
  3. **ResearchHub on pwnstar**, for ACADEMIC literature only. **Always query it through
     `./scripts/rh-query.sh "your question"`** — never raw curl. The wrapper runs a preflight that
     repairs a stale tunnel automatically and, crucially, tells three failures apart that otherwise
     look identical: tunnel down (**exit 3**), tunnel fine but ResearchHub down or mid-update
     (**exit 4**), and the query itself failing (**exit 5**). An empty result from it is a REAL empty
     result, not a silent network failure. `--check` runs the preflight alone; `--json` gives raw JSON.
     [../runbooks/researchhub-tunnel.md](../runbooks/researchhub-tunnel.md).
  4. Official LEGO Education docs → web.
  Stop at the first hit that answers. **Fail open:** if the docs-rag or the tunnel is down, grep and
  search the web — never stop to repair infrastructure mid-task.
- **Re-ingest after you write docs**, or the docs-rag answers from a stale corpus. It self-heals on a
  ~300 s reconcile, but `./rag ingest` is immediate and is the honest thing to do before relying on it.
- **Grep by keyword, don't `cat` folders.** Retrieve a path, then load that file.
- **Cite, don't recopy.** A plan cites findings by path. New web research becomes a NEW finding with
  its source URLs. Derived artifacts reference; they don't re-embody.
- **Trust official LEGO docs over tutorials** — the SPIKE 2 → SPIKE 3 API change silently invalidated
  most of the tutorial internet. Check what API generation a source targets before believing it.
- **Check maintenance dates on any community tool** before recommending it, and say the date out loud.
- **Document a finding when** it was non-obvious, needed research, or captures what did NOT work.
  Failed approaches are worth as much as successes here — they're the report's discussion section.
  Skip trivial one-offs.
