# Questions for the Professor

**Type:** ACTIVE-SPEC (living list) · **Created:** 2026-08-25 · **Last revised:** 2026-08-27
· **Ask at:** the next class meeting, in writing, in one batch

The design challenge was briefed verbally: *"Build a mine sweeper robot that finds all the mines
(I think yellow sticky notes) in a 10×10 area."* That is the entire requirement of record. This page is
the list of what it leaves open, **ordered by how much the answer changes the build**.

**Three partial answers came back on 2026-08-27**, relayed by a teammate. They are recorded in the
Answers table at the bottom and, with their provenance and hedging preserved, in
[../findings/mission-answers-2026-08-27.md](../findings/mission-answers-2026-08-27.md).
**One of them contradicts itself**, so it generated more questions than it closed.

**Ask them in this order. If you only get through two, get through Q1 and Q2** — Q1 spans two orders of
magnitude, Q2 decides what we are optimising for, and they interact.

**Written, not spoken.** Face-to-face beyond the daily standup is billed at 1 SB per person per minute,
and written team communication is a graded deliverable that gets submitted in full — so asking in
writing scores twice.

---

## 1. "10×10" — ten *what*? ⭐ STILL FIRST, STILL UNANSWERED

**Nothing in the 2026-08-27 answers touched this.** It remains the single highest-leverage unknown in
the project.

**Why it matters more than anything else:** a single downward colour sensor traces a line, not a swath.
To not miss a 76 mm sticky note, sweep lanes must be under ~76 mm apart — under ~46 mm once realistic
heading drift is accounted for. So the arena side length sets the path length directly:

| If it's… | Sweep path | Time at a `[ASSUMED]` 150 mm/s |
|---|---|---|
| 10 inches | ~1 m | seconds |
| 10 × 76 mm cells | ~8 m | under a minute |
| **10 feet** | **125–204 m** | **8–23 minutes** |

Two orders of magnitude. Full arithmetic: [../findings/coverage-time-budget.md](../findings/coverage-time-budget.md).

**If the answer is 10 feet, the design has to change** — more sensors, a wider mechanical swath, or
abandoning exhaustive coverage — and that is a decision we would need to make immediately, not a tuning
problem. *(And note a blind human driver does not cover the area any faster than the robot does, so the
autonomy answer gives no relief here either.)*

## 2. How long does the demo run get, and is finding *all* of them required? ⭐

Paired with Q1, this decides the entire strategy.

- Is there a time limit? What is it?
- Is the score "found all of them" (optimise for not missing any → slow, tight lanes) or "found the most
  in the time" (optimise for speed → wide lanes, accept misses)? **These pull in opposite directions.**
- How many attempts do we get?
- May the Builder intervene mid-run, or is it one hands-off run?

## 0b. To confirm: is a human operator allowed **at all**? ⭐ NEW — created by the answer

**The answer we heard says both things.** As relayed, 2026-08-27:

> *"you can't have a human operator... if you do have a human operator, they cannot be looking at the
> arena."*

The first clause says **no**. The second describes a condition for **yes**. The ellipsis is in the
transcription, so we do not know what was said in the gap. **We are not guessing at a grade** — until
this is confirmed we assume autonomy is required, which is what we were building anyway.

**Ask it plainly:** *"Just to make sure we build the right thing — is a human operator allowed at all,
or is the robot required to run on its own?"*

**Two follow-ups, only if the answer is that an operator is allowed:**

- **0c — Does using a human operator cost points** against a robot that runs autonomously? This decides
  whether a teleoperated fallback is worth building even as insurance.
- **0d — What may the operator use?** Sound from the hub, a laptop showing telemetry, a spotter who
  relays information? *"May not look at the arena"* does not say whether instrument-mediated feedback is
  allowed — and it collides with a requirement of ours: **an operator turned away from the arena cannot
  read the hub's light matrix**, which is where the robot reports its count.

*(Why this is not simply good news: an operator who may not look at the arena cannot cover it by eye,
cannot see the boundary tape, and dead-reckons off the same sensors the robot uses — later. The
navigation work does not go away. Full argument: [blind-teleoperation.md](./blind-teleoperation.md).)*

## 3b. Blue painters tape or silver/grey duct tape? ⭐ NEW — created by the answer

**Both were mentioned on 2026-08-27 and neither was chosen.** They are not the same problem for a
colour sensor: our hub's built-in colour list has **no grey and no silver**, so silver tape has no class
to land in and would have to be handled from raw channel values instead.

**But we cannot size the difficulty from here.** The separation that matters is **tape against the
floor**, not tape against white — and we have never seen the floor either (Q7). So this is a question
plus a bench measurement, not an argument.

- Is it blue painters tape or silver/grey duct tape — and does it vary between arenas or between teams?

## 3c. How wide is the tape, and does crossing it count as a failure? NEW

- **How wide?** 24 mm and 48 mm are both standard. A 24 mm line is only about twice a colour sensor's
  measurement spot, which means the boundary detector cannot be tuned the same way as the mine detector.
- **Is crossing the tape a scored failure, or is the tape only a marker?** With no walls there is
  nothing physical to stop the robot, so this sets how much stopping margin the design has to buy.
- Do the wheels have to stay inside, or must no part of the robot overhang?

## 3d. May we have an offcut of the actual tape? NEW

Detection is calibrated against the real material or it is calibrated against nothing. A 150 mm piece of
the actual tape, and ideally the actual sticky notes, would let us run the separability measurement
before Demo Day rather than discovering the answer on the day.

*(Same shape as the existing request to practise on the real floor, Q7.)*

## 4. What does "finds" mean as a deliverable?

Report a **count**? Report **locations**? **Stop** on each mine? **Pick them up**?

A count is a two-day build. A location map needs reliable dead reckoning and is a substantially bigger
project. We are currently building toward a count.

## 5. Are there decoy notes of other colours? ⭐ (the mine colour half is answered)

**Answered 2026-08-27:** the mines are yellow — *"we expect yellow"*. **Still open, and this is the
half that changes the build:**

- Is anything else on the floor — notes of other colours, or anything that is not a mine?
- If there are other-coloured notes, are they decoys to *ignore*, or targets to *classify separately*?

**And it costs run time.** Classifying a note needs several samples taken wholly inside it, which caps
traverse speed materially below what presence-only detection tolerates. So this question compounds Q1
and Q2 — [../findings/coverage-time-budget.md](../findings/coverage-time-budget.md).

*(Note: the boundary tape already puts a second non-floor colour on the floor with certainty, so a
"yellow only" answer would no longer make colour discrimination go away entirely.)*

## 6. How many mines, and how are they placed?

- Is the count fixed and known, or does it vary per run?
- Can two notes be adjacent or touching? *(Adjacent notes are the classic double-count / merge-into-one
  failure — worth designing for if it can happen.)*
- Can they be on the boundary, partially outside, or overlapping it? **This one got sharper**: with a
  taped boundary, a note lying on the tape is a real case and we have to decide whether the boundary
  wins (robot stops, note not counted) or the note does.

## 7. The arena itself

- **What is the floor surface?** Carpet or hard floor changes both odometry accuracy and the
  reflected-light values we calibrate against — **and it is now what decides whether the boundary tape
  is easy or hard to see.**
- Is it the same arena for every team?
- **Can we practise on it before Demo Day?** Calibration is floor- and lighting-specific; tuning on a
  different surface is wasted effort.

## 8. Scoring and logistics

- Is there a written scoring rubric for Demo Day we should have?
- Does the robot have a size or parts constraint beyond the budget?
- Does the Intro Report have required content beyond the CSER template, or is the template the whole spec?
- **Is the CSER Word template the required format, and do you want the `.docx`, a PDF, or both?** The
  written instructions name a due date and nothing else — no format, no file type. We are assuming the
  handed-out template is mandatory and submitting both files. A one-word answer confirms or frees it.

---

## Answered — and what came off this list

### 0. Autonomy — ⚠ ANSWERED CONTRADICTORILY, re-asked as Q0b

**RETRACTED 2026-08-27.** This question used to carry a table claiming that if a human may drive,
*"sweep path planning, odometry accuracy, heading hold, per-lane re-squaring and the whole
coverage-time problem"* become optional. **That table is withdrawn.** Its stated justifications were
*"a human covers the area by eye"* and *"a person drives straight to what they can see"* — and the
answer we got, in the reading where an operator is permitted at all, says the operator **may not look at
the arena**. A blind operator has the same information the hub has, delayed, and gets none of it by
eye.

**So the simplification this question was chasing does not exist under either reading**, and the
question that remains is only whether an operator is permitted at all (Q0b). Reasoning:
[blind-teleoperation.md](./blind-teleoperation.md). Provenance:
[../findings/mission-answers-2026-08-27.md](../findings/mission-answers-2026-08-27.md).

*(What was correct and is kept: the word "autonomous" appears nowhere in the course instructions — full
text extracted and scanned 2026-08-26 — and no prohibitive sentence anywhere in the course material
constrains how the robot moves. All nine are about roles, money or schedule. The one adjacent sentence
calls the Builder "your operator (the only one who can operate the robot)", which is worth quoting when
asking Q0b, and which means that if we ever do drive the robot from a keyboard, **the keyboard is the
Builder's** — driving is operating, at −2 SB per violation.)*

### 3. What bounds the area — ANSWERED 2026-08-27

**No walls. The boundary is tape on the floor**, blue painters or silver/grey duct.

What that changed: the **Distance Sensor 45604 has no boundary role left** — floor tape has ~0.1–0.3 mm
of vertical extent against a sensor with ±20 mm accuracy and a 50 mm blind zone — and the **Force
Sensor 45606 has nothing to bump**, which removes the best squaring accuracy any purchasable part
offered. **Neither is permanently excluded**: an obstacle-stop role would revive the first, and a
team-supplied reference beam would revive the second, and neither has been asked about. Keep reading
both prices off the store board; the price log is free and graded.

What it did **not** answer became Q3b, Q3c and Q3d above.

---

## Answers

Record answers here as they come in, then update
[../scope.md § Mission](../scope.md#mission--partial-verbal-briefing-captured-2026-08-25) and re-derive
the requirements. **Date each answer and name its source** — a relayed answer is not the same evidence
as one heard first-hand.

| # | Question | Answer | Source | Date |
|---|---|---|---|---|
| 0 | **Autonomous, or may a human drive?** | ⚠ **CONTRADICTORY.** *"you can't have a human operator... if you do have a human operator, they cannot be looking at the arena."* First clause forbids, second permits. **Not treated as answered** — re-asked as Q0b. Meanwhile we assume autonomy | Professor, verbal, **relayed by a teammate** | 2026-08-27 |
| 0b | Is an operator allowed **at all**? | _pending_ | | |
| 0c | Does teleoperation cost points? | _pending_ | | |
| 0d | What may a blind operator use? | _pending_ | | |
| 1 | **Units of "10×10"** | _pending_ — **still first** | | |
| 2 | Time limit / scoring objective | _pending_ | | |
| 3 | Boundary type | **No walls. Boundary is tape on the floor** — blue painters **or** silver/grey duct; which one was not pinned down | Professor, verbal, **relayed by a teammate** | 2026-08-27 |
| 3b | Which tape — blue or silver? | _pending_ | | |
| 3c | Tape width; is crossing scored? | _pending_ | | |
| 3d | May we have a tape offcut? | _pending_ | | |
| 4 | Meaning of "finds" | _pending_ | | |
| 5 | Yellow only / decoys | **PARTIAL** — mines are yellow: *"we expect yellow"* (**hedged in the source**). Whether decoys of other colours exist is **still unanswered** | Professor, verbal, **relayed by a teammate** | 2026-08-27 |
| 6 | Mine count and placement | _pending_ | | |
| 7 | Floor surface, practice access | _pending_ | | |
| 8 | Scoring rubric, constraints | _pending_ | | |

---

## Revision History

| Date | Change | By |
|---|---|---|
| 2026-08-25 | Created from the verbal briefing. | Claude |
| 2026-08-27 | Recorded the three relayed answers. **Q3 closed** (no walls, floor tape) and replaced by Q3b/Q3c/Q3d. **Q5 halved** — mine colour answered (hedged), decoys still open. **Q0 retracted, not closed**: the answer contradicts itself, and its "becomes optional" table is withdrawn because a blind operator refunds no navigation work. Added Q0b/Q0c/Q0d. Q1 (units) promoted to first with Q2. Answers table gained a Source column. | Claude |
