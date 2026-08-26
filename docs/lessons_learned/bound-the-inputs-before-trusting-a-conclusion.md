# Bound your inputs before you trust a conclusion

**Date:** 2026-08-25 · **Source:** the operator, reviewing the coverage trade study

**WHEN** an analysis produces a decision-grade conclusion — a feasibility gate, a purchase
recommendation, a "this does not fit" —

**DON'T** accept it until every input it is sensitive to has a *bound* traceable to a spec sheet, a
measurement, or shown arithmetic. A bracket midpoint, a "practical" figure, or a value at maximum
efficiency is **not** a bound.

**BECAUSE** the conclusion inherits the weakest input, and an unbounded input makes the conclusion
unfalsifiable rather than merely uncertain.

## What happened

The coverage trade study ([../plans/2026-08-25-coverage-strategy-trade-study.md](../plans/2026-08-25-coverage-strategy-trade-study.md))
concluded that at 10 ft with a hard 3–5 minute limit, **nothing clears the bar — not even three colour
sensors.** That drives a real purchasing decision against a 56 SB budget.

Its run-time model turns on traverse speed `v`, for which it used **250 mm/s** — a bracket midpoint. It
even named its own overturning condition: a ground speed above 250 mm/s would change the result. But the
figure traced back to a *speed at maximum efficiency*, computed from a **56 mm wheel we have never
confirmed we own** ([KU-M3](../plans/known-unknowns.md)), on a **motor whose type is unknown**
([KU-T3](../plans/known-unknowns.md)).

So the study stated the condition that would refute it and never checked whether the hardware could meet
it. Nobody had asked the plain question: **how fast can this robot actually go?**

**The operator caught it. Neither the author nor the adversarial auditor did** — the auditor verified the
arithmetic *within* the model and confirmed every cell recomputed correctly, which is precisely the blind
spot: an audit that checks internal consistency will not question an input the whole document treats as
given.

## How to apply

- **Name the sensitive inputs explicitly**, then ask of each: measured, specified, or assumed? An
  analysis that identifies its own overturning condition must then go and *test* it, not just log it.
- **A ceiling is not a typical value.** "At maximum efficiency", "practical", "recommended" — none of
  these bound anything. If you need an upper bound, derive it from a hardware limit and show the arithmetic.
- **Audit the inputs, not only the arithmetic.** Add to any review: *which numbers here are assumptions
  wearing the costume of facts?* Recomputing every cell of a table proves the table is internally
  consistent and says nothing about whether it is about reality.
- **An assumption that reaches a purchase decision gets promoted** to a measurement task in
  [known-unknowns.md](../plans/known-unknowns.md) with a bench procedure, not left as an `[ASSUMED]` cell.

**Related:** [../directives/honest-instrumentation.md](../directives/honest-instrumentation.md)
(never report a value you did not measure) · [../directives/map-before-act.md](../directives/map-before-act.md)
(enumerate the surface before acting).
