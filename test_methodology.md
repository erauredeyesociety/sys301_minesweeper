# Test methodology — what we run, what we don't, and why

> Written 2026-08-26 because the operator asked a fair question: *"you seem to be running tests on the
> code regardless of me saying 'do not write test scripts'… I don't really understand what is going on."*
>
> **This is at the repo root by explicit operator request**, against the usual "all `.md` in `docs/`" rule.

---

## The short answer

**There is no test suite in this repository, and there never has been one since ADR-0005.**
`tests/` was deleted. No `pytest`, no `conftest.py`, no `test_*.py`. Verified as of 2026-08-26.

What I have been running is **three different things that all look like "testing" from the outside**, and
conflating them is my fault — I never named the distinction.

---

## The three things, and which are persistent

| | What it is | Persistent? | Costs tokens? |
|---|---|---|---|
| **1. Throwaway verification** | A one-line `python3 -c "..."` to answer a question *right now* — "does the edge counter return 2 on this stream?" | **No.** Never saved, never re-run | Yes, but once |
| **2. `scripts/check-docs.py`** | A **lint**: broken links, missing INDEX, docs over 1200 lines, the `src/` import boundary | **Yes** — one file, run on demand | No — it runs, it doesn't get regenerated |
| **3. Hub diagnostics** | `find_spike_prime.py`, `setup-host.sh` — they touch real hardware, so they can never be tests | **Yes** | No |

**None of these is a test suite.** A test suite is a standing body of assertions re-run on every change.
That is what ADR-0005 rejected, and it stays rejected.

### 1. Throwaway verification — this is what you were seeing

When I wrote the edge counter, I ran a synthetic stream through it with a deliberate mid-note dropout and
checked it counted **2, not 3**. When I fixed `MissionResult`, I printed a truncated run and checked it
said `PARTIAL total>=8` instead of `total=8`.

**Those commands are gone.** They were never written to a file, never committed, never re-run. They are
the equivalent of you typing something into a REPL to see if it works — which is exactly the role you
identified for the debugger.

**Why not just use the debugger?** For an interactive bug hunt, the debugger is better and I should reach
for it. But for *"I just wrote this, does it do the obvious thing"*, one line of output is faster than
stepping through, and it produces something I can paste to you as evidence rather than asserting "it
works". That evidence is the point — this project's standard is *never report a result you did not
observe*.

**The token cost is one command, once.** It is not a suite being maintained.

### 2. `check-docs.py` — a lint, and the one persistent check I'd defend

This is the one that could reasonably be called a test, so let me make the case and let you kill it if you
disagree.

It checks five things, none of which are about program behaviour:
links resolve · every docs folder has an INDEX · no docs over 1200 lines · **`src/` imports nothing
hub-only** · every `src/` module still imports on the host.

**The fourth one matters more than it looks.** ADR-0004 made "pure modules never import hub modules" the
architecture boundary, and named a floor test as its guard. ADR-0005 then removed the test suite — so that
boundary had **no guard at all** until this script. One accidental `import motor` in `detector.py` and
nothing on the laptop runs any more, discovered at the worst possible moment.

It replaced a dozen hand-typed shell pipelines. That was the *other* reason: **every complex command is an
approval you have to give.** One script is one approval.

### 3. Hub diagnostics — definitionally not tests

Anything needing the hub cannot be deterministic and cannot run in a loop. It depends on the hub being
present, charged, connected, wired right, on a particular floor, under particular lighting. A "test" whose
outcome depends on whether someone plugged in a cable will get skipped the first time it is inconvenient.

---

## So do we need persistent test scripts?

**My honest answer: no, with one exception that already exists.**

**No, because** the failure modes that will actually cost us are physical — heading drift, a note missed at
a lane edge, a threshold wrong for the real carpet, a motor slipping. **No host-side test reaches any of
them.** The pure logic is ~600 lines of arithmetic and two state machines, and the real verification is a
robot moving on a floor.

**The one exception is the import-boundary check**, because it guards something with no other guard and
costs nothing to run.

**What I would genuinely reconsider:** if the same logic bug reaches the floor **twice**, one small check
for that specific behaviour is worth its cost — a bug that costs a class period to rediscover is expensive
in the currency that actually matters here. That is ADR-0005's own stated reversal condition, and it would
be a new ADR, not a quiet reintroduction.

---

## What I'll do differently

1. **Say which of the three I'm doing**, so "running a quick check" is never mistaken for building a suite.
2. **Reach for the debugger** on an actual bug hunt, rather than instrumenting with print statements.
3. **Never create a test file** without a new ADR.
4. **Keep throwaway verification genuinely throwaway** — it goes in the transcript as evidence, not on disk.

---

## Answered by the operator, 2026-08-26

**1. Is `check-docs.py` welcome?** — **Yes.** *"it helps to automate a very repetitive task."* It stays,
and the `src/` import boundary keeps its guard.

**2. Evidence or conclusion?** — **Conclusion.** *"just conclusion works, I will ask more questions as
needed."* So: report what a check found, not the transcript that found it. The verification still
happens — the standard against reporting an unobserved result is unchanged — it just does not get
narrated by default. Paste output when it is *surprising*, when it is the deliverable, or when asked.

**3. Is the debugger set up how you'd want it?** — **Not needed.** *"things are small enough that we
don't actually need a debugger and the aggressive minimalist modularity doctrine helps keep things
small."*

That last answer is worth more than it looks, because it explains **why** the no-test-suite decision
holds together rather than being a shortcut:

> **Minimalism is what removes the need for the heavier tools.** Small pure modules with one job each
> mean a stack trace usually names the bug outright. It is when modules grow, tangle, and hide state
> that you need a debugger to find out what is actually happening — and a test suite to notice when it
> changes. **Keeping the code small is the alternative to both**, and it is a live constraint, not a
> nice-to-have: the moment a module stops being small enough to reason about, this whole methodology
> stops being safe.

Practical consequence: **if a module ever grows past being readable in one sitting, that is the signal to
split it — not to add tooling around it.** Same instinct as the 1200-line cap on documents.

**Related:** [ADR-0005](docs/decisions/0005-no-test-suite-verify-on-hardware.md) ·
[ADR-0004](docs/decisions/0004-flat-src-supersedes-package-split.md) ·
[testing-discipline.md](docs/directives/testing-discipline.md) (superseded upstream standard, kept for the report)
