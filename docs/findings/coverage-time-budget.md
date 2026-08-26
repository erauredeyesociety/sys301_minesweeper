# Finding — Exhaustive coverage may not fit in a demo run

**Date:** 2026-08-25 · **Type:** analysis (arithmetic, no hardware) · **Status:** open — needs one answer from the professor

## The claim

If "a 10×10 area" means **10 feet square**, a single downward-facing color sensor cannot sweep it
exhaustively in a plausible demo slot. Best case is **~8 minutes**; realistic case is **~14–23 minutes**.
If it means something smaller, the mission is comfortable. **The units are the whole ballgame**, and
they are currently unknown ([../scope.md § Mission](../scope.md#mission--partial-verbal-briefing-captured-2026-08-25)).

## Why coverage is the constraint

A downward point sensor doesn't sweep a swath — it traces a **line**. To guarantee no mine is missed,
adjacent sweep lanes must be spaced closer than the target's width, minus twice the robot's cross-track
error. A standard sticky note is **76 mm** (3 in) square, so:

```
lane pitch  ≤  76 mm  −  2 × cross-track error
```

Cross-track error is what heading drift costs you laterally. Per
[../research/detection-and-sweep-techniques.md](../research/detection-and-sweep-techniques.md), a **1°**
heading error over a 1.2 m lane already costs **21 mm** — so 15 mm of error per lane is optimistic, not
pessimistic, and it cuts the usable pitch from 76 mm to 46 mm.

## The arithmetic

Lanes = ⌈side ÷ pitch⌉. Path = lanes × side. Times exclude turns, which add meaningfully at 40+ lanes.

| If "10×10" means | Side | Lanes @76 mm | Path | @150 mm/s | @250 mm/s |
|---|---|---|---|---|---|
| 10 **inches** | 254 mm | 4 | 1.0 m | 0.1 min | 0.1 min |
| 10 × 76 mm cells | 760 mm | 10 | 7.6 m | 0.8 min | 0.5 min |
| 10 × 30 cm tiles | 3.0 m | 40 | 120 m | **13.3 min** | **8.0 min** |
| 10 **feet** | 3.05 m | 41 | 125 m | **13.9 min** | **8.3 min** |

With a realistic **15 mm** cross-track error (pitch 46 mm):

| If "10×10" means | Lanes | Path | @150 mm/s | @250 mm/s |
|---|---|---|---|---|
| 10 × 30 cm tiles | 66 | 198 m | **22.0 min** | **13.2 min** |
| 10 **feet** | 67 | 204 m | **22.7 min** | **13.6 min** |

Reproduce: the calculation is five lines of arithmetic; the inputs are the 76 mm note width, the pitch
formula above, and an assumed traverse speed.

## What is measured vs assumed

| Input | Status |
|---|---|
| 76 mm sticky note width | Standard 3 in note. **`[ASSUMED]`** — the actual notes have not been seen or measured |
| 1° → 21 mm over 1.2 m | Geometry, sound. The *drift rate producing* that 1° is community-measured, not LEGO-specified |
| 150–250 mm/s traverse speed | **`[ASSUMED]`** bracket. The real ceiling is set by sample rate × required samples per target and **must be measured** |
| Turn overhead | **Not included.** 40–67 turns is not negligible; the totals above are optimistic |
| Cross-track error | **`[ASSUMED]`** 15 mm. Must be measured via a UMBmark square-path run |

## What follows

1. **Ask the units question first.** It has a bigger effect on this project than any other open item —
   two orders of magnitude in path length.
2. **Ask the time limit.** If the demo slot is a few minutes and the arena really is 10 ft, exhaustive
   single-sensor coverage is off the table and the design must change, not the tuning.
3. **If it is 10 ft, the options are:** more than one color sensor across the robot's width (budget:
   56 SB remaining); accepting probabilistic rather than exhaustive coverage; or a wider effective swath
   via a mechanical arm. Each is a real trade study, and each needs the professor's scoring rule to
   evaluate — "found all of them" and "found most of them fast" are different objectives.
4. **Do not tune anything until the units are known.** Tuning a sweep for the wrong arena is wasted
   class time.

Questions to carry into class: [../plans/questions-for-the-professor.md](../plans/questions-for-the-professor.md)

---

## Update — colour classification makes this worse, and Q5 is now a time question too

[../research/color-discrimination.md](../research/color-discrimination.md) establishes something the
speed bracket above did not account for: **classification is speed-limited in a way presence detection
is not.** To classify a note you need several *pure* samples taken wholly inside it, so a note the robot
clips at a glancing chord bounds the traverse speed:

| Chord across the note | Max traverse speed for reliable classification |
|---|---|
| 30 mm | ~360 mm/s |
| 20 mm | ~160 mm/s |

Presence detection needs one clean edge pair and tolerates far more speed. So:

- **If yellow is the only colour present** (professor Q5), we detect on reflected light, run nearer the
  fast end of the bracket, and the coverage problem is merely hard.
- **If we must classify**, the slow end of the bracket is the realistic one, and the 10-foot case moves
  from "8–23 minutes" toward the upper half of that range.

**Q5 is therefore not only a robustness question — it is a run-time question.** Ask it alongside Q1
and Q2, not after them.

Consequence for the design: keep classification **optional and layered on top of** presence detection,
never a prerequisite for counting. Count on the edge pair; classify only if the sample quality allows.
That way an answer of "yellow only" costs us nothing we already built.
