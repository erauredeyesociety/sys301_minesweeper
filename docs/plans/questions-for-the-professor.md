# Questions for the Professor

**Type:** ACTIVE-SPEC (living list) · **Created:** 2026-08-25 · **Ask at:** the next class meeting

The design challenge was briefed verbally: *"Build a mine sweeper robot that finds all the mines
(I think yellow sticky notes) in a 10×10 area."* That is the entire requirement of record. This page is
the list of what it leaves open, **ordered by how much the answer changes the build**.

Ask them in this order. **If you only get through two, get through Q0 and Q1** — Q0 can remove half the project, Q1 spans two orders of magnitude.

---

## 0. Does the robot have to be autonomous, or may a human drive it? ⭐⭐ ASK THIS FIRST

**This may be the largest simplification available to us, and we have been assuming the hard answer.**

**"Autonomous" appears nowhere in the course instructions.** Full text extracted and scanned
2026-08-26 for *autonom · remote · control · drive · pilot · operate · steer · joystick*. The verbal
briefing says only *"build a mine sweeper robot that finds all the mines."* We inferred autonomy from
the word "robot" and then built to it — [scope.md § Mission](../scope.md#mission--partial-verbal-briefing-captured-2026-08-25)
flagged it as an inference, but FR-1 had quietly hardened it into a requirement.

**And the one relevant sentence leans the other way.** The instructions say of the Builder:

> *"The builder is also your **operator** (the only one who can **operate** the robot)."*

A purely autonomous robot needs a *starter*, not an *operator*, and "operate" is an odd word for pressing
one button. **This is suggestive, not conclusive** — "operate" may simply mean handling it — but it is
the only sentence in the course material bearing on the question, and it does not point at autonomy.
Worth quoting to the professor: it makes the question concrete rather than hypothetical.

**What changes if a human may drive it:**

| Becomes optional | Why |
|---|---|
| Sweep path planning, lane pitch, boustrophedon | A human covers the area by eye |
| Odometry accuracy, heading hold, per-lane re-squaring | Nobody is dead-reckoning |
| **The whole coverage-time problem** | The 8–23 minute figure assumes a robot driving 46 mm lanes. A person drives straight to what they can see |
| Cross-track error, UMBmark calibration | Same reason |

| Still required either way | Why |
|---|---|
| **Detection and counting** | The sensor still has to tell a note from the floor, and count each one once. **This is the actual engineering problem** |
| Calibration at run start | Floor and lighting still vary |
| Honest reporting on the hub | FR-4 is unchanged |

**So the sensing half survives and the navigation half evaporates.** Roughly half the remaining risk in
[risk-register.md](./risk-register.md) is navigation risk.

**Ask it plainly:** *"Does the minesweeper have to run autonomously, or may a team member drive it while
it detects and counts?"* And if driving is allowed, follow up: **by what — the SPIKE app, a controller,
our own Bluetooth link?** That last one decides whether we research a human-pilot control path at all.

### And there is no prohibition anywhere

Every prohibitive sentence in the instructions was extracted and read (*may not · cannot · not allowed ·
prohibit · forbidden · must not · only the*). **All nine are about roles, money, or schedule:**

- Only the Supplier may handle money or supplies · the Supplier cannot touch supplies after buying
- The Designer may not touch supplies · the Programmer may not touch supplies except to plug/unplug
- **Only the Builder may operate the robot**
- Supplies live in the yellow box between classes · no work outside class · no role changes
- Nobody may share a peer-evaluation total

**Not one constrains how the robot moves, or forbids a human guiding it.** The course's rules are about
*who does what*, not *what the machine does*. So the position is: autonomy is neither required nor
forbidden in anything we hold — it is simply unaddressed, and the only adjacent sentence calls the
Builder an **operator**.

**⚠ Raise this in class as a PRIORITY, not as an afterthought.** It is the only open question that can
*remove* work rather than merely direct it, and every class day it stays open is a day of navigation work
that may turn out to be unnecessary. Ask it in the first minutes, before the standup runs out.

*(If the answer is "autonomous", nothing is lost: everything already built assumes it, and the question
cost one sentence in a conversation we were having anyway.)*

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
- **Is the CSER Word template the required format, and do you want the `.docx`, a PDF, or both?** The
  written instructions name a due date and nothing else — no format, no file type. We are assuming the
  handed-out template is mandatory and submitting both files. A one-word answer confirms or frees it.

---

## Answers

Record answers here as they come in, then update
[../scope.md § Mission](../scope.md#mission--partial-verbal-briefing-captured-2026-08-25) and re-derive
the requirements. Date each answer.

| # | Question | Answer | Date |
|---|---|---|---|
| 0 | **Autonomous, or may a human drive?** | _pending_ | |
| 1 | Units of "10×10" | _pending_ | |
| 2 | Time limit / scoring objective | _pending_ | |
| 3 | Boundary type | _pending_ | |
| 4 | Meaning of "finds" | _pending_ | |
| 5 | Yellow only / decoys | _pending_ | |
| 6 | Mine count and placement | _pending_ | |
| 7 | Floor surface, practice access | _pending_ | |
| 8 | Scoring rubric, constraints | _pending_ | |
