# Working with the operator: the corrections that keep recurring

**Date:** 2026-08-26 · **Source:** a session's worth of operator corrections, distilled

The other lessons here are about research and code. This one is about **project management** — the
collaboration failures that cost the most time, none of which were technical mistakes.

Each is a real correction from this project, with the underlying rule.

---

## 1. Anything scarce or shared is operator-gated, however obvious the default looks

**What happened.** `docs-rag/.env` named `LLM_MODEL=llama3.2:3b` and there was free VRAM, so I started
pulling it. Stopped: *"I like your initiative but you are incorrect on that one so check with me on
that because this happens to be important."*

**The rule.** A default value sitting in a config file **is not permission** — it is a default someone
else chose for a different deployment. Shared GPU, disk at the GB scale, another project's services,
anything outward-facing: ask, even when the local config makes it look settled.
[ADR-0006](../decisions/0006-docs-rag-llm-is-operator-gated.md).

**And the part worth keeping:** when told I was wrong, I checked the upstream source rather than just
complying — and found the guidance was **more specific than either of us had said**. There is no literal
"never sub-5B" rule; `llama3.2:3b` *is* the pinned default, but as an *"availability floor… chosen for
footprint, not answer quality"*. That reframing is what revealed the real answer: remote 9B on skytracker,
because 9B *local* is ruled out outright. **Complying would have closed the question; checking answered it.**

---

## 2. The operator's definition of "working" governs

**What happened.** I called the docs-rag working because search returned correct results. Corrected:
*"the docs rag is not working if you cannot use the api ask, that is part of offloading tokens."*

**The rule.** Report status against **the purpose the thing was built for**, not the component you
happened to test. And when the operator defines a term differently from you, **their definition wins** —
they know what they needed it for. Full lesson: [a-tool-works-when-it-does-its-job.md](./a-tool-works-when-it-does-its-job.md).

**The sharp edge:** permission-to-use is not the same as status. When the operator later granted a
temporary pass to use search-only docs-rag, the honest status stayed **PARTIAL**. Being allowed to use a
half-working tool does not make it a working tool, and letting that drift would be the same error again.

---

## 3. Script the ritual — a re-typed pipeline costs the operator, not just you

**What happened.** I ran the same link-check, INDEX-check and purity-grep as inline shell one-liners a
dozen times. Corrected: *"please try to never run very complex bash commands, use scripts for that…
I need to allow the complex ones."*

**The rule.** `automation-first.md` already said to script a ritual the second time. What I had missed is
that the cost is not only drift and unrepeatability — **every complex command is an approval the operator
has to give.** Re-improvising is a tax on them, not on me. One `./scripts/check-docs.py` replaced all of
it, and — importantly — I proved it *fails* when it should before trusting it.

---

## 4. Deliver what was asked, in the place it belongs

**What happened.** I created `README.md` files in `src/`, `tests/` and `scripts/`. Corrected: *"why are
there readme files in every folder of this project including where code should be? that is going to get
messy real quick, all docs should be in docs."*

**The rule.** The standard said all `*.md` lives in `docs/`, and the README-per-subfolder rule applies to
`docs/` subfolders only. I had generalised a rule past its scope. **When a standard seems to conflict
with itself, the narrower reading is usually right** — and the operator noticing before I did means I
was not reading it carefully enough.

---

## 5. Do not build ahead of a dependency that might not exist

**What happened.** After being asked for the motor/sensor self-check I kept going into mission logic.
Redirected: *"why are you writing code? are all research and planning fully done as much as possible?"*

**The rule.** Later stated explicitly and generalised well: research the telemetry *analysis*, but do not
write it, **because we do not yet know whether any transport works.** Code written against an unproven
dependency is code written twice. Research is cheap and reusable; implementation is neither.
See [../plans/telemetry-and-analysis.md](../plans/telemetry-and-analysis.md).

---

## 6. Research broadly, implement narrowly — they are different disciplines

**The operator's framing**, worth quoting because it is the cleanest statement of it:

> *"You can for sure research and plan for more than what is needed, but implementation should always be
> more concise and better quality and easier to maintain."*

**The rule.** Breadth in research is a virtue; breadth in implementation is a liability. Every plan should
end with a deliberately **small** subset that gets built, and that subset is a contract. A "what gets
implemented" section that keeps almost everything has failed its brief.

---

## 7. Scope creep hides in bookkeeping

**What happened.** A measurement plan grew a minute-by-minute time budget. Ruled out: *"don't worry about
keeping track of session time stuff, that is irrelevant."*

**The rule.** Ask what a piece of tracking **changes**. Dependency *order* between measurements prevents a
wasted class session, so it earns its place; a minute total does not, and keeping it current costs effort
forever. The same test applies to status fields, progress percentages, and any tally nobody acts on.

---

## How to apply all of this

Before acting, three questions:

1. **Is this mine to decide?** Scarce/shared resources, anything outward-facing, anything a default
   merely *implies* — those are the operator's.
2. **Am I building ahead of an unproven dependency?** If yes, research it and stop.
3. **Would I run this command more than once?** If yes, it is a script.

And when corrected: **check the source before complying.** Agreeing immediately feels cooperative and
often leaves the real answer undiscovered.

**Related:** [a-tool-works-when-it-does-its-job.md](./a-tool-works-when-it-does-its-job.md) ·
[bound-the-inputs-before-trusting-a-conclusion.md](./bound-the-inputs-before-trusting-a-conclusion.md) ·
[model-only-to-the-next-decision.md](./model-only-to-the-next-decision.md)
