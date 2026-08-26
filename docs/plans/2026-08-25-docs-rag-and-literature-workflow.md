# Docs-RAG and Academic Literature — DELIVERED

**Type:** FORWARD-PLAN · **Status:** SUPERSEDED by delivery, same day 2026-08-25

> **This plan's recommendation was overtaken.** It argued for doing nothing; the operator directed
> otherwise and both pieces were built and verified the same day. The reasoning below is kept because
> the *constraints* it identifies still hold — but the decision it recommends no longer does.
>
> **What actually exists now:**
> - **docs-rag**, deployed from `~/exudeai/rag-bootstrap` 0.8.3 as a local instance in `docs-rag/`
>   (the upstream tool is read-only to us). Semantic search over this repo's `docs/` at
>   `http://127.0.0.1:10060`. 65 of 65 markdown files indexed. Runbook:
>   [../runbooks/docs-rag.md](../runbooks/docs-rag.md). **`/api/ask` does not work** (HTTP 500, no LLM
>   pulled) — search works, answer-generation does not.
> - **ResearchHub**, reached over an SSH tunnel to pwnstar (10.231.80.91:5347, port discovered not
>   guessed) via `./scripts/rh-tunnel.sh`, with stale-tunnel detection and repair.
>   Runbook: [../runbooks/researchhub-tunnel.md](../runbooks/researchhub-tunnel.md).
> - **`scripts/fetch_paper.py`** — fetch a paper by URL / DOI / arXiv id into `docs/research/papers/`
>   with a grep-able text sidecar, per the convention this plan set out below (which was kept).
> - **Cost: ~1.9 GB**, almost all of it ollama's embedding-model runner; the four containers are ~143 MB.
>   On a host with ~4 GB free that is the first thing to stop when memory is tight.
>
> Retrieval order and fail-open rules now live in
> [../directives/knowledge-retrieval.md](../directives/knowledge-retrieval.md).

## Why this exists

The pain is real and measured: [../research/detection-and-sweep-techniques.md](../research/detection-and-sweep-techniques.md)
is ~1150 lines and [spike-prime-linux-toolchain.md](../research/spike-prime-linux-toolchain.md) is ~440.
Re-reading them every session costs tokens. A retrieval layer would help.

## The decision as originally written — SUPERSEDED

*(Kept per the "keep wrong ideas WITH the why" rule. The reasoning was sound given what was known at
the time; the operator had better information about the tooling's readiness.)*

> **Not now.** This is a two-week course project with Demo Day on 10 SEP. Standing up retrieval
> infrastructure competes directly with building the robot, and the robot is what gets graded.

What changed: `rag-bootstrap` turned out to be **current, not stale** (0.8.3, committed the same day),
so the setup cost was hours rather than days; and pwnstar's ResearchHub was **reachable**, so no local
deployment was needed for the literature half.

## What is actually on this machine (measured 2026-08-25)

| Thing | State |
|---|---|
| ResearchHub running locally | **Not running** — no process, no container. Nothing to stop |
| `~/researchhub/` source tree | Present, but the operator says the local copy is **not current** |
| `~/exudeai/rag-bootstrap/` | Present, but the operator says it is **not current enough to set up** |
| `rag_qdrant`, `rag_pg` containers | Running — but they belong to the **`cars_demo_13`** compose project, not to us. Do not disturb |
| `ollama` | Installed, **inactive** |

## The corpus habits — still in force, infrastructure or not

These outlive the tooling and are the reason retrieval works at all:

1. **Every research document carries a tight `Summary` section at the top.** A future session reads the
   summary and the `INDEX.md` row, and only opens the full document when it needs the detail. This is
   the single highest-leverage habit here and it costs nothing.
2. **`grep` first.** Retrieval order for this project is `docs/findings/` and `docs/research/` → official
   LEGO docs → web. Stop at the first hit that answers.
3. **Academic PDFs**, when we download them: store under `docs/research/papers/`, named
   `<firstauthor><year>-<short-topic>.pdf`, with a `.txt` sidecar produced by `pdftotext` so `grep`
   works on them. **Gitignore the PDFs, track the sidecars and the citations** — the repo should not
   carry tens of megabytes of copyrighted papers. Claude can read a PDF directly; the text extraction
   exists for searching, not for reading.
4. **Cite, never recopy.** A finding cites the paper; it does not reproduce its prose.

## If we revisit — the trigger and the lead

Revisit **only** if the corpus outgrows grep (roughly: more than ~15 substantial research documents, or
a real literature review for the Intro Report), **and** Demo Day is already behind us.

The lead worth following then, from the operator: ResearchHub is running on **pwnstar, `10.231.80.91`**,
reachable over SSH — possibly with `~/.ssh/id_git`. An SSH port-forward to that instance would give us a
search corpus **without deploying anything locally**. The port is unknown. **Nothing has been attempted:
no connection to pwnstar has been made, and none should be without the operator asking for it.**

## Still deliberately NOT doing

- **Running ResearchHub locally** — we tunnel to pwnstar's instance instead. This repo does not need
  its own, and the local `~/researchhub/` copy is not current.
- **Modifying anything under `~/exudeai/`** — the upstream rag-bootstrap is read-only to us; our
  instance's config lives in this repo.
- Pulling an ollama model or otherwise loading an embedding backend on a host with ~3 GB free and
  `earlyoom` inactive

Host measurements behind these calls: [../findings/host-environment.md](../findings/host-environment.md).
