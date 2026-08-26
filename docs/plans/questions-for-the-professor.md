# Questions for the Professor

**Type:** ACTIVE-SPEC (living list) · **Created:** 2026-08-25 · **Ask at:** the next class meeting

The design challenge was briefed verbally: *"Build a mine sweeper robot that finds all the mines
(I think yellow sticky notes) in a 10×10 area."* That is the entire requirement of record. This page is
the list of what it leaves open, **ordered by how much the answer changes the build**.

Ask them in this order. If you only get through two, get through the first two.

---

## 1. "10×10" — ten *what*? ⭐ ask this first

**Why it matters more than anything else:** a single downward color sensor traces a line, not a swath.
To not miss a 76 mm sticky note, sweep lanes must be under ~76 mm apart — under ~46 mm once realistic
heading drift is accounted for. So the arena side length sets the path length directly:

| If it's… | Sweep path | Time at a realistic speed |
|---|---|---|
| 10 inches | ~1 m | seconds |
| 10 × 76 mm cells | ~8 m | under a minute |
| **10 feet** | **125–204 m** | **8–23 minutes** |

Two orders of magnitude. Full arithmetic: [../findings/coverage-time-budget.md](../findings/coverage-time-budget.md).

**If the answer is 10 feet, the design has to change** — more sensors, a wider mechanical swath, or
abandoning exhaustive coverage — and that is a Sprint 2 decision we would need to make immediately,
not a tuning problem.

## 2. How long does the demo run get, and is finding *all* of them required? ⭐

Paired with Q1, this decides the entire strategy.

- Is there a time limit? What is it?
- Is the score "found all of them" (optimize for not missing any → slow, tight lanes) or "found the most
  in the time" (optimize for speed → wide lanes, accept misses)? **These pull in opposite directions.**
- How many attempts do we get?
- May the Builder intervene mid-run, or is it one hands-off run?

## 3. What bounds the area?

Walls? Tape on the floor? A colored border? Nothing at all?

This is the **biggest purchase decision** — we have 56 Schrute Bucks left:
- Walls → we need the **distance sensor** (45604) for boundary detection
- Tape or colored border → a second **color** channel, or the same sensor doing double duty
- Nothing → pure odometry, and drift becomes the dominant failure mode

## 4. What does "finds" mean as a deliverable?

Report a **count**? Report **locations**? **Stop** on each mine? **Pick them up**?

A count is a two-day build. A location map needs reliable dead reckoning and is a substantially bigger
project. We are currently building toward a count.

## 5. Yellow only, or are there decoy colors? ⭐ (promoted — this is a run-time question too)

- Are **all** the mines yellow, and is anything else on the floor?
- If there are other-colored notes, are they decoys to *ignore*, or targets to *classify separately*?

If yellow is the only thing on the floor, we can use plain reflected-light detection, which is much more
robust. If we must tell colors apart, that is a materially harder problem — sticky notes are matte and
pastel, the worst case for the sensor's built-in color ID.

**And it costs run time.** Classifying a note needs several samples taken wholly inside it, which caps
traverse speed at roughly **160 mm/s** where a note is clipped at a 20 mm chord, versus ~360 mm/s at
30 mm. Presence detection tolerates far more speed. So this question compounds Q1 and Q2 —
[../findings/coverage-time-budget.md](../findings/coverage-time-budget.md).

## 6. How many mines, and how are they placed?

- Is the count fixed and known, or does it vary per run?
- Can two notes be adjacent or touching? *(Adjacent notes are the classic double-count / merge-into-one
  failure — worth designing for if it can happen.)*
- Can they be on the boundary, partially outside, or overlapping it?

## 7. The arena itself

- **What is the floor surface?** Carpet or hard floor changes both odometry accuracy and the
  reflected-light values we calibrate against.
- Is it the same arena for every team?
- **Can we practise on it before Demo Day?** Calibration is floor- and lighting-specific; tuning on a
  different surface is wasted effort.

## 8. Scoring and logistics

- Is there a written scoring rubric for Demo Day we should have?
- Does the robot have a size or parts constraint beyond the budget?
- Does the Intro Report have required content beyond the CSER template, or is the template the whole spec?

---

## Answers

Record answers here as they come in, then update
[../scope.md § Mission](../scope.md#mission--partial-verbal-briefing-captured-2026-08-25) and re-derive
the requirements. Date each answer.

| # | Question | Answer | Date |
|---|---|---|---|
| 1 | Units of "10×10" | _pending_ | |
| 2 | Time limit / scoring objective | _pending_ | |
| 3 | Boundary type | _pending_ | |
| 4 | Meaning of "finds" | _pending_ | |
| 5 | Yellow only / decoys | _pending_ | |
| 6 | Mine count and placement | _pending_ | |
| 7 | Floor surface, practice access | _pending_ | |
| 8 | Scoring rubric, constraints | _pending_ | |
