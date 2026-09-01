# ADR-0006 — The docs-rag's LLM is an operator-gated decision; remote 9B is the target

> **DEPLOYED 2026-08-27 — the decision stands; the model NAME differs, and that is recorded here
> rather than by editing the decision below.**
>
> This ADR names **`qwen3.5:9b` remote** as the quality unlock. **That model is not installed on
> skytracker and never was.** The only generation model there is **`qwen3:14b`**, dated 2026-02-21 —
> months older than this project. docs-rag was pointed at it, and `/api/ask` works: ~79 s warm,
> correct answers with correct citations.
>
> **Nothing was pulled.** The constraints this ADR actually imposes are all satisfied: remote not
> local, above the 5B floor (14B), and the shared GPU untouched on our initiative. The operator was
> asked and answered *"whatever is running on skytracker."*
>
> Config: [`docs-rag/.env`](../../docs-rag/.env) · runbook: [../runbooks/docs-rag.md](../runbooks/docs-rag.md)


- **Date:** 2026-08-26
- **Status:** Accepted
- **Deciders:** Operator (correcting Claude)

## Context

The docs-rag is only **partially working**: search answers, `/api/ask` returns HTTP 500 because no
generation model is pulled. `ask` is the capability that offloads tokens
([ADR-0005 context](./0005-no-test-suite-verify-on-hardware.md), and the lesson
[a-tool-works-when-it-does-its-job](../lessons_learned/a-tool-works-when-it-does-its-job.md)).

Seeing `docs-rag/.env` already specify `LLM_MODEL=llama3.2:3b`, I started pulling it on my own
initiative. The operator stopped it: **do not use sub-5B models for this.**

## What the upstream guidance actually says

I checked rather than assuming, and it is worth recording precisely, because it is more specific than
either of us stated. From `~/exudeai/rag-bootstrap/docs/reference/MODEL_SELECTION.md` and
`docs/findings/assess_model_selection_vram_tiering.md`:

- **There is no literal "never sub-5B" rule.** `llama3.2:3b` is in fact rag-bootstrap's pinned default.
- **But it is pinned as an *availability floor*, "chosen for footprint, not answer quality"** — it exists
  so the stack has *something* on a shared 6 GB GPU, not because it answers well. **The operator's
  instinct was right and better founded than my action.**
- **7–8B local is explicitly NOT recommended** — at Q4 they run ~4.5–5 GB resident, evicting other
  tenants or forcing CPU offload.
- **`qwen3.5:9b` LOCAL is explicitly ruled out**: ~6.3–6.6 GB of weights on a 6 GB card spills 58–65 % to
  CPU → **~5 minutes per query**. This matters: we cannot fix this by "getting more resources" on *this*
  machine.
- **`qwen3.5:9b` REMOTE is named as "the real quality unlock"**, requiring an external endpoint and a
  tunnel dependency.
- `qwen3.5:4b` (~2.5 GB Q4, 256 K context, toggleable thinking) is the *designated* local upgrade
  candidate, and even that is gated on an explicit GPU-budget decision.

## Decision

1. **The docs-rag's generation model is an operator decision. Never pull one on initiative.** It consumes
   shared GPU on a multi-tenant card, and the footprint gate is a policy, not a preference.
2. **No sub-5B model for this project's `/api/ask`.** `llama3.2:3b` is an availability floor and would
   give exactly the low-quality synthesis that makes token-offload worthless.
3. **The target is `qwen3.5:9b` running REMOTELY on skytracker**, reached through
   `./scripts/sky-ollama.sh`. This is not a workaround — it is the path the upstream guidance itself
   names as the genuine unlock, and the only one available, since 9B local is ruled out on a 6 GB card.
4. **Until then `/api/ask` stays broken and docs-rag stays PARTIAL.** Say so plainly; do not soften it.

## Consequences

- **`/api/ask` is blocked on the ERAU VPN**, which is currently failing (authenticates, then dies before
  installing routes). That is the single blocker on the docs-rag being fully working.
- Search keeps working on local `nomic-embed-text` (~0.3 GB) meanwhile — useful for *finding* a file,
  which is the smaller half of the value.
- **Before pointing docs-rag at skytracker, confirm it serves `nomic-embed-text` too.** The index is
  768-dimensional and pinned; a different embedder is an index wipe and full re-embed, not a config edit.
  If skytracker has the 9B but a different embedder, the right move is to forward it **for generation
  only** and keep embeddings local.
- ~700 MB of partial `llama3.2:3b` blobs were downloaded before the stop and have been **deleted**;
  `~/.ollama/models` is back to 262 MB and the model was never registered.

## The general rule this establishes

**Anything that consumes shared or scarce resources — GPU residency, disk at the GB scale, another
project's services — is operator-gated, however obvious the local config makes it look.** A default value
sitting in a `.env` is not permission; it is a default someone else chose for a different deployment.
