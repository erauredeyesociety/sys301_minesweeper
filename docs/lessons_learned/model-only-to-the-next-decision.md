# Model only as far as the next decision, then go measure

**Date:** 2026-08-25 · **Source:** the operator, on the speed and coverage arithmetic

**WHEN** a number is unknown and cannot be measured yet,

**DON'T** keep refining the model of it. Carry it as a named variable, state the assumption, and stop at
the point where the number would change a **decision**.

**BECAUSE** past that point the extra precision is unfalsifiable — it cannot be checked, it cannot be
wrong in a way anyone would notice, and it competes for time with the measurement that would settle it
in ten minutes on the bench.

## What happened

The coverage and speed analysis grew a long tail: derating curves, gear-ratio encoder-quantisation
trade-offs, chord-geometry speed ceilings, sensitivity tables across cross-track error. All of it
arithmetically correct. All of it resting on **an assumed wheel diameter, on motors of unknown type, in
an arena of unknown size**.

The operator's call: *"a lot of numbers that you are accounting for we really just need to test in the
real world because we have a hodge podge of hardware."* They were right. The robot has several possible
wheel sizes on hand and nobody has yet read the part number off a motor. No amount of modelling closes
that; one class session does.

## Where the line actually is

This is **not** "don't model" — accounting for variables is what made the work useful. Two genuinely
decision-changing results came out of exactly this analysis:

- Lane pitch must be under the target width, which is why coverage is the binding constraint at all.
- Three sensors need 300 mm/s, which is reachable — overturning a "not at all" conclusion and changing
  what to buy.

Both changed a decision. Everything after them did not. **The test is: if this number moved by 30%,
would we do something different?** If no, write it down as an assumption and move on.

## Fitness for purpose is a real standard, not an excuse

This is a two-week undergraduate project graded on engineering *process* and a working demo — not a
system that must be right in the tail. It does not need to be perfect.

That is **not** licence to be sloppy, and the distinction matters:

| Cut this | Never cut this |
|---|---|
| Precision on an unmeasured input | Honesty about what was measured vs assumed |
| A fourth decimal place | The measurement's units and conditions |
| Modelling a case the professor may rule out | Traceability from a requirement to its verification |
| A gear ratio for speed we cannot use | A floor test on the counting logic |

A well-documented assumption marked `[ASSUMED]`, with the procedure that would close it, scores better
than a confident number with no provenance — and it is also just more honest. **High standards here mean
knowing which numbers are real, not having more of them.**

## How to apply

- Before extending an analysis, ask: **which decision does the next number change?** If none, stop.
- An unmeasured value becomes a **variable plus a bench procedure**, not a better estimate. Put the
  procedure in [../plans/bench-measurement-plan.md](../plans/bench-measurement-plan.md) and the variable
  in [`src/config.py`](../../src/config.py), where changing it later costs one edit.
- **Parameterise so measurement is cheap.** The reason this cost us little: arena size, wheel diameter,
  track width, and thresholds were already arguments and config values, so the real numbers will change
  values and not architecture.
- When you catch yourself producing a sensitivity table for an input nobody has ever observed, that is
  the signal.

**Related:** [bound-the-inputs-before-trusting-a-conclusion.md](./bound-the-inputs-before-trusting-a-conclusion.md)
— its sibling. That one says *check the inputs your conclusion rests on*; this one says *stop refining
them once the decision is made*. Together: **bound it, then go measure it.**
