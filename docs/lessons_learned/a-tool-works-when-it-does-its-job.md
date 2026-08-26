# A tool "works" when it does the job it was built for, not when its parts respond

**Date:** 2026-08-26 · **Source:** the operator, on my calling the docs-rag "working"

**WHEN** reporting whether a tool or service works,

**DON'T** report the component you happened to test. Report against **the reason the thing was built**.

**BECAUSE** a partial capability described as working stops the remaining work from being done — the
operator reasonably stands down, and the gap only surfaces later when the missing half is needed.

## What happened

I deployed the docs-rag, ran a search, hand-checked the answer against the source file, and reported it
**working**. Search genuinely did work. But `/api/ask` returned HTTP 500 the whole time, and I filed that
as a footnote — a known limitation rather than a failure.

The operator corrected it: *"the docs rag is not working if you cannot use the api ask, that is part of
offloading tokens."*

They are right, and the distinction is not pedantic:

| | What it saves | What it costs the caller |
|---|---|---|
| **Search** | Finding *which* file answers the question | You still read the chunks and reason over them — the tokens are still spent |
| **`/api/ask`** | Finding *and reading and synthesising* | You read one short answer |

The docs-rag existed to **offload token cost**. Search alone offloads *lookup*, not *reading* — the
smaller half. So "working" was measured against a component that responded, not against the purpose.

This is the same failure I had already flagged in the vendored app and did not notice myself committing:
its `/api/health` reports `embedding_service: true` while embeddings are unreachable. **I criticised a
green-when-broken health check and then wrote one in prose.**

## How to apply

- Before calling anything working, ask: **what was this built to do, and did I just observe it doing
  that?** Not "did it respond", not "did the part I tested pass".
- **State partial capability as PARTIAL, never as working-with-a-caveat.** The caveat gets skimmed; the
  status word is what people act on.
- A status check should assert the **job**, not the component. `stack.sh status` now reports docs-rag
  *search* and *ask* on separate lines and counts a broken `ask` as a real failure — because that is the
  line that determines whether the tool is doing what it is for.
- When the operator defines "working" differently from you, **their definition governs** — they know what
  they needed it for.

**Related:** [../directives/honest-instrumentation.md](../directives/honest-instrumentation.md) (a probe
that cannot run returns UNKNOWN, never a pass) · [bound-the-inputs-before-trusting-a-conclusion.md](./bound-the-inputs-before-trusting-a-conclusion.md)
