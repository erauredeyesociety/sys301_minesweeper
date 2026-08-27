# Finding — Mission answers of 2026-08-27, and exactly how far they can be trusted

**Date:** 2026-08-27 · **Source:** the professor, **verbally**, in conversation
· **Chain of custody:** professor → a teammate → loose transcription → this repo
· **Heard directly by the operator:** **NO**
· **Hardware touched to produce this document:** none

> **This is a provenance record, not a measurement.** Nothing here was observed by anyone in this
> repo. It is one relay hop further from the source than the original briefing was, and the original
> briefing was already hedged (*"I think yellow sticky notes"*).
> Vocabulary rule: [../lessons_learned/say-which-kind-of-verified.md](../lessons_learned/say-which-kind-of-verified.md).

**Companions:** [../plans/questions-for-the-professor.md](../plans/questions-for-the-professor.md) (the
message) · [../plans/known-unknowns.md](../plans/known-unknowns.md) (the state of our ignorance) ·
[../plans/blind-teleoperation.md](../plans/blind-teleoperation.md) (what the autonomy answer does and
does not buy) · [../scope.md](../scope.md) (where the answers land as requirements)

---

## 1. How to read this document

Three columns of trust, and they are not the same:

| Class | What it means | How it is written below |
|---|---|---|
| **QUOTED** | Words attributed to the professor, as relayed. Still second-hand | `> blockquote`, marked *as relayed* |
| **RELAYED** | The teammate's paraphrase of what was said | plain text, marked RELAYED |
| **INFERRED** | Our reading of the above. **Ours, not the professor's** | marked `[INFERRED]` |
| **STILL GUESSED** | Nothing was said; we are carrying a default | marked `[ASSUMED]` |

**The rule this document exists to enforce:** when the Intro Report says *"the instructor specified
X"*, X must appear in the QUOTED or RELAYED rows here. If it only appears in an INFERRED row, the
report must say *"we interpreted the briefing as X"* instead.

---

## 2. What was answered

### 2a. Mine colour — RELAYED, hedged

> **"we expect yellow"**
> — the professor, as relayed, 2026-08-27

**RELAYED:** the mines are yellow sticky notes.

**The hedge is in the source and must survive.** *"We expect yellow"* is an expectation, not a
specification. It is materially weaker than *"the mines are yellow"*, and it is now the **second**
hedge on this fact — the original briefing was *"I think yellow sticky notes"*.

**RELAYED (team, not the professor):** the team wants to be able to retarget to another colour
quickly, and asked that yellow be a configured value rather than a constant. **That is the team's
requirement, not the professor's.** Attribute it correctly in the report.

`[ASSUMED]` still: the exact shade, the pack, the paper finish. **Nobody has seen the notes.** Every
chromaticity number anywhere in this repo is computed from published sRGB values for a generic
"canary" note and is not a measurement of the real pack.

### 2b. The arena boundary — RELAYED

**RELAYED:** the arena has **no walls**. The boundary is marked **on the floor with tape** — either
**blue painters tape** or **silver/grey duct tape**. Both were mentioned. **Which one is used was not
pinned down.**

This is the answer to Q3 for the part that mattered most: there is nothing physical to bump and
nothing to echo. It is *not* an answer on tape colour, and the two candidates are not equivalent to a
colour sensor — see §4.

`[ASSUMED]` still: tape **width** (24 mm and 48 mm are both standard), whether the tape is
continuous, whether the corners are closed, and whether crossing it is scored as a failure or is
merely a marker.

### 2c. Autonomy — QUOTED, and **internally contradictory**

The relayed words, in full:

> **"you can't have a human operator... if you do have a human operator, they cannot be looking at
> the arena."**
> — the professor, as relayed, 2026-08-27

**Read the two clauses.** The first says a human operator is **not** allowed. The second describes
what is required **if** one is used. **They contradict each other**, and the ellipsis is in the
transcription — we do not know what was said in the gap.

**Two readings are both defensible:**

| Reading | What it says | Consequence |
|---|---|---|
| **A — permissive** | A human operator is allowed, on condition they cannot see the arena | Blind teleoperation is legal |
| **B — restrictive** | A human operator is not allowed; the second clause is a conditional aside, or a correction the transcription lost | Autonomy is required |

**We do NOT record this as answered.** Under
[../../CLAUDE.md](../../CLAUDE.md)'s rule to build to the narrowest defensible reading, the narrow
reading is **B: assume autonomy is required, and treat blind teleoperation as an unconfirmed
relaxation.** That is also where we land on engineering grounds — see
[../plans/blind-teleoperation.md](../plans/blind-teleoperation.md) — so nothing is lost by waiting.

**What must NOT be written anywhere on the strength of this:** "the professor permitted
teleoperation". A confirmation question is queued as Q0b in
[../plans/questions-for-the-professor.md](../plans/questions-for-the-professor.md), at the top of the
next round.

---

## 3. What was NOT answered, and is still first

| Still open | Status |
|---|---|
| **The units of "10×10"** — feet, metres, tiles, inches? | **Untouched by any of today's answers.** Still the single highest-leverage unknown in the project: ~1 m of driving at 10 in, 125–204 m at 10 ft ([coverage-time-budget.md](./coverage-time-budget.md)) |
| The demo time limit and the scoring rule | Untouched |
| Whether decoy notes of other colours are present | Untouched. §2a answers what the mines *are*, not what else is on the floor |
| What "finds" means as a deliverable | Untouched |
| Mine count and placement | Untouched |
| Floor surface, and practice access | Untouched — and §4 shows it now matters more than it did |

**The units question stays at the top of the next message.** Nothing answered today changes path
length, and a blind human driver does not cover less area than a robot does.

---

## 4. What the answers change, stated conservatively

**These are `[INFERRED]` — our engineering reading, not the professor's words.**

1. **The Distance Sensor 45604 has no boundary role left.** Floor tape has roughly 0.1–0.3 mm of
   vertical extent against a sensor with ±20 mm accuracy and a 50 mm blind zone. A horizontal beam
   sees nothing at the boundary; a downward beam cannot resolve it. Its lane-end trigger, run-start
   arena ranging and pre-alignment jobs all needed a reflecting boundary and all die.
   **Not "permanently excluded"** — an obstacle-stop role would survive if obstacles turn out to
   exist, and nobody has asked.

2. **The Force Sensor 45606 has nothing to bump — but do not strike it from the price log.** Its
   per-lane mechanical square (the best squaring accuracy any purchasable part offered) needed a
   physical edge to seat against. It stays **deferred**, not excluded, because one unasked question
   revives it: *may the team place its own reference beam at one edge?* Keep reading its price off
   the board; the price log is free and is a graded written deliverable.

3. **The boundary is now something the colour sensor might see.** That is the first concrete design
   element FR-6 has ever had. It is **not** yet a capability — no colour sensor is owned, and the
   tape has never been seen, let alone measured against the floor.

4. **Tape and mine are the same event to a presence-only detector.** Both are "not floor". This is a
   real consequence and it has three known mitigations, none free: classify the tape as its own
   calibrated class; suppress detection in a guard band near the boundary (which deletes coverage
   exactly where a boundary-adjacent mine would sit); or discriminate on **event width**, since a
   tape line crossed during a lane produces a long event and a note produces a bounded chord —
   `src/detector.py` already gates on event width, so this one costs nothing new.

5. **Blue tape and silver tape are not equivalent, but "silver is undetectable" is NOT established.**
   The separation that matters is **tape against the floor**, not tape against white. Our own hub
   reports no `GREY` and no `SILVER` colour constant
   ([hub-first-contact-2026-08-27.md](./hub-first-contact-2026-08-27.md) §4c), so silver will land in
   `WHITE` or `UNKNOWN` and the built-in colour ID is the wrong instrument for it — but `rgbi()`
   exists and the floor may be dark. Against carpet or dark tile, silver separates on reflectance
   alone. **The arena floor has never been observed**, so the risk cannot be sized yet. This is a
   bench measurement, not an argument.

---

## 5. Hardware facts confirmed the same day (separate source)

Recorded here only so the date is not confused with the mission relay. **Different provenance:**

| Fact | Source | Class |
|---|---|---|
| Hub is **SPIKE 3 / current API**, MicroPython 1.24.0, no `spike` module | Read off our own hub over USB — [hub-first-contact-2026-08-27.md](./hub-first-contact-2026-08-27.md) | **MEASURED** |
| Both drive motors are **Medium Angular 45603** | The **operator**, reported 2026-08-27 | RELAYED — not inspected by anyone in this repo. The definitive close is the device type ID read at bring-up |
| Wheel diameter | — | **STILL UNMEASURED.** All odometry depends on it |

---

## 6. What this finding does not license

Written out because the temptation is real and the report is graded:

- **Do not** write "autonomy is optional" into `scope.md`, an ADR, or the Intro Report. §2c is a
  contradiction, not a permission.
- **Do not** reduce any requirement on the strength of a permitted human operator. In particular, an
  operator who may not look at the arena cannot cover it by eye, cannot see the tape, and cannot read
  the hub's 5×5 matrix — so FR-4's reporting channel is in question and the navigation work is not
  refunded. Full argument: [../plans/blind-teleoperation.md](../plans/blind-teleoperation.md).
- **Do not** quote a chromaticity separation, a stopping distance, or a safe speed as a finding. No
  colour sensor is owned, no wheel is measured, no braking has been observed, and no floor has been
  seen.
- **Do not** treat the tape colour as decided. Two candidates were named and neither was chosen.

---

## 7. Follow-up questions this created

All go in one written round, behind the units question:

1. **Q0b** — *"To confirm: is a human operator allowed at all? The answer we heard both ruled one out
   and described a condition for using one."* **This is the one that matters most of the new ones.**
2. **Q3b** — Blue painters tape or silver/grey duct tape — or does it vary between arenas?
3. **Q3c** — How wide is the tape, and is crossing it a scored failure or is it only a marker?
4. **Q0c** — If a human operator is allowed, does using one **cost points** against an autonomous run?
5. **Q0d** — If a human operator is allowed, what may they use — hub sound, a laptop telemetry
   screen, a spotter? *"May not look at the arena"* does not settle instrument-mediated feedback.
6. **Q5b** — Are decoy notes of other colours present? (Unchanged and still open.)
7. **Q3d** — May the team obtain an offcut of the actual tape for calibration before Demo Day?

---

## Revision History

| Date | Change | By |
|---|---|---|
| 2026-08-27 | Created. Records the relayed mission answers with their hedges, flags the autonomy quote as internally contradictory and declines to close it, and separates QUOTED from RELAYED from INFERRED so the Intro Report can attribute correctly. | Claude |
