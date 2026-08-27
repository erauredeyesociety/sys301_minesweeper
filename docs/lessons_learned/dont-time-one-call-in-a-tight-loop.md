# Don't time one call in a tight loop and add the results up

**Date:** 2026-08-27 · **Source:** our own IMU benchmark on the hub, which disagreed with itself by 4×

**WHEN** micro-benchmarking a sensor or device API — "how much does one read cost, so I can budget a
control loop?" —

**DON'T** time each call alone in a tight loop and sum the results. Measure the **mix you will actually
run**, in one loop, and treat any per-call figure as suspect until something proves it is not a cache.

**BECAUSE** a repeated identical call may never reach the device at all. It can return a cached value,
and what you then measure is the cost of the cache — a number that is real, reproducible, internally
consistent, and answers a question nobody asked.

## What happened

Timed on our hub, 2026-08-27, 500 calls each:

| Call | Per call | Implied rate |
|---|---|---|
| `tilt_angles()` | 0.054 ms | ~18,500 Hz |
| `acceleration()` | 0.110 ms | ~9,000 Hz |
| `angular_velocity()` | 0.164 ms | ~6,000 Hz |
| **Sum of the three** | **0.328 ms** | |
| **All three in one loop** (300 iterations) | **1.350 ms** | ~740 Hz |

**The parts cost 0.328 ms; the whole costs 1.350 ms — 4.1× more.** Both numbers came off the same
hardware, minutes apart, from loops that were individually correct.

Two things gave it away, and the second is the one that generalises:

1. **The implied rates were not physically plausible.** 6,000–45,000 Hz of genuine sensor traffic over
   an I²C-class link on an STM32F413 is not a thing. A benchmark whose answer implies impossible
   hardware has measured something other than the hardware.
2. **The whole was more expensive than the sum of its parts**, which is backwards. Fixed overhead makes
   the parts cost *more* than the whole, never less. Something in the individual runs was being skipped.

`[INFERRED, UNVERIFIED]`: mixing calls forces a genuine sensor update while a repeated call is served
from a cache. Three other explanations are not ruled out — per-call loop overhead differences, the
allocator behaving differently under a mixed workload, or the firmware batching all six axes into one
transfer that only a mixed loop pays for. **It is recorded as an open unknown (KU-M14), not as a
diagnosis.**

## How to apply

- **Benchmark the call pattern you will ship.** A control loop that reads three things gets timed
  reading three things. The sum of isolated micro-benchmarks is not a loop budget.
- **Sanity-check the implied rate against physics before believing the number.** Convert to Hz and ask
  whether the bus, the sensor and the processor could do that. This catches cache artefacts for free.
- **If the whole costs more than the sum of the parts, the parts are wrong** — not the whole. Plan with
  the mixed figure (here: 1.350 ms per full IMU tick, 14 % of a 10 ms budget) and mark the per-call
  numbers unusable rather than averaging the two.
- **The decisive test is cheap: count bit-identical consecutive reads.** If a value repeated in a tight
  loop never changes and the same value read among others does, it is a cache. One experiment settles
  it; until it is run, say so.
- **This invalidates a method, not just a number.** The "(b) − (a) is the sensor's cost" subtraction in
  [../research/hub-compute-limits.md](../research/hub-compute-limits.md) § 7 row D-2 assumes adding a
  call adds its isolated cost. Here it did not. Fix the method, not only the datapoint.

**Related:** [bound-the-inputs-before-trusting-a-conclusion.md](./bound-the-inputs-before-trusting-a-conclusion.md)
(the sibling failure: right arithmetic, wrong input) ·
[say-which-kind-of-verified.md](./say-which-kind-of-verified.md) (these *were* measurements — on real
hardware — and still did not mean what they looked like) ·
[../findings/imu-characterisation-2026-08-27.md](../findings/imu-characterisation-2026-08-27.md) (the
numbers and the four experiments that would settle it) ·
[../directives/honest-instrumentation.md](../directives/honest-instrumentation.md).
