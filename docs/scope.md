# SYS 301 Minesweeper — Scope

> Last updated: **2026-09-08**
> Status: **Active** — mission captured from the verbal briefing 2026-08-25; three partial answers relayed
> 2026-08-27 (mine colour, boundary type, autonomy — the last one self-contradictory); **four mission
> facts corrected by the operator 2026-09-08** (arena size, arena completeness, floor, mine colours).
> **The units of "10×10" are PROVISIONALLY answered — a 10 FOOT square, operator-stated, and explicitly
> "not set in stone".** See § Mission.
> Directives that govern work here: [docs/directives/INDEX.md](./directives/INDEX.md)

---

## Overview

ERAU **SYS 301 (Systems Engineering) Introductory Project**. A four-person team designs, builds,
programs, and demonstrates a LEGO Education SPIKE Prime robot against an instructor-briefed design
challenge, under a simulated-economy constraint (Schrute Bucks) and enforced role separation.

This repository holds **all** of the team's work product: the robot software, the systems-engineering
artifacts, the hardware/build record, and the graded course deliverables (journal, report, comms log).

## Objectives

- **O1 — Working robot.** A SPIKE Prime robot that autonomously performs the briefed mission on Demo Day (10 SEP 2026).
- **O2 — Graded deliverables.** Journal, mid-project survey, peer evaluations, and the CSER-format Intro Report, each submitted on time and to rubric.
- **O3 — Defensible engineering record.** Requirements, decisions, and verification evidence traceable enough to write the report FROM the repo rather than reconstructing it afterwards.
- **O4 — Zero firmware risk.** The hub is shared course equipment; it must be returned in its factory software state.

---

## Mission — PARTIAL (verbal briefing captured 2026-08-25)

**There is no briefing document, and there is nothing to go looking for.** The written instructions say
*"Your design challenge is per the Instructor's briefing"* — the briefing was delivered verbally in
class. What the operator was told, verbatim, is the whole of it:

> **"Build a mine sweeper robot that finds all the mines (I think yellow sticky notes) in a 10×10 area."**

That is the requirement of record. Everything below separates what it actually says from what it
doesn't.

### Answers relayed 2026-08-27 — read the provenance before quoting these

**Source: the professor, verbally, relayed by a teammate through a loose transcription.** Nobody in
this repo heard them. That is one relay hop further from the source than the briefing itself, which was
already hedged. **Full provenance record, with what is QUOTED vs RELAYED vs INFERRED:**
[findings/mission-answers-2026-08-27.md](./findings/mission-answers-2026-08-27.md).

| | Answer, as relayed | Confidence |
|---|---|---|
| **Mine colour** | *"we expect yellow"* | **Hedged in the source.** An expectation, not a specification — and the second hedge on this fact after *"I think"*. Yellow is carried as a **configured value**, not a constant. *(Retargeting quickly is the **team's** requirement, not the professor's.)* |
| **Boundary** | **No walls.** The boundary is tape on the floor — **either blue painters tape or silver/grey duct tape.** Both were mentioned; **which one was not pinned down** | Clear on "no walls". Silent on which tape, how wide, and whether crossing it is scored |
| **Autonomy** | *"you can't have a human operator... if you do have a human operator, they cannot be looking at the arena."* | ⚠ **INTERNALLY CONTRADICTORY — NOT recorded as answered.** The first clause forbids what the second permits. We build to the narrowest reading: **assume autonomy is required**, treat blind teleoperation as an unconfirmed relaxation, and ask again |

### ⚠ Corrections from the operator, 2026-09-08 — these supersede parts of the table above

Recorded on the day the robot first ran on the real surfaces. **Source: the operator, directly** — one
relay hop *closer* to us than the 2026-08-27 answers, and the arena facts are what the team is expected
to build to. Evidence and measurements:
[findings/colour-survey-and-first-detection-2026-09-08.md](./findings/colour-survey-and-first-detection-2026-09-08.md).

| | Correction | Confidence |
|---|---|---|
| **Arena size** | **A 10 FOOT square — 3048 mm** is the competition expectation and standard | **PROVISIONAL.** Operator-stated and explicitly **"not set in stone"**; it may change on the day. Carried as `ARENA_WIDTH_MM = ARENA_LENGTH_MM = 3048.0` in [`src/mission_config.py`](../src/mission_config.py), the **planning value**, not a closed answer (KU-P1) |
| **Arena completeness** | ⚠ **The graded arena is a COMPLETE CLOSED BOX outlined in blue painters tape on the floor.** The practice area's tape is deliberately **incomplete** only so teams do not overlap — **that is not the graded arena.** There is a real wall near **one** side of the demo area, and other objects around it | Operator-stated. **Supersedes** any design that assumed the practice area's open tape was representative |
| **Floor** | **Multicolour classroom carpet** | **MEASURED** — `reflection()` 3–9, `r+g+b` 49–107 (median 79), chromaticity 30.5 / 33.6 / 35.8. Closes KU-P7 |
| **Boundary tape** | **Blue painters tape**, and **1 inch (25.4 mm) wide in the test area** | Tape identity **MEASURED** (blue fraction 0.476–0.496 vs a carpet ceiling of 0.408; built-in `color()` returned `BLUE` on 149/149 samples). Width is **operator-stated and may differ on demo day** — so it is a config value, never a literal. Closes KU-P13; KU-P14's width half only |
| **Mine colours** | **Yellow *and* pink** matte sticky notes; the colour **may change on demo day**; the standing guarantee is that **mines are NEVER BLUE** | Both colours **MEASURED** on the real pack and both correctly classified in motion. ⚠ **Blue tape and a blue sticky note are different things** and must not be conflated by any rule we write |

**What these answers do NOT do.** They do not touch the time limit, the scoring
rule, whether decoy colours exist, or what "finds" means. And a permitted-but-blind operator would
refund **no** navigation work — an operator who may not look at the arena cannot cover it by eye, cannot
see the tape, and cannot read the hub's 5×5 matrix. Analysis:
[plans/blind-teleoperation.md](./plans/blind-teleoperation.md).

### What this establishes

| | |
|---|---|
| **Task** | Find **all** the mines — coverage is the success criterion, not a sample |
| **Target** | Sticky notes — **yellow *and* pink** (operator, 2026-09-08, both MEASURED on the real pack), hedged twice before that: *"I think"* (2026-08-25) and *"we expect yellow"* (2026-08-27). **The colour may change on the day; mines are never blue.** Carried as a configured value, and the count rule underneath is **colour-agnostic** (`reflection() >= 30`) so a colour change costs nothing |
| **Arena** | A **10×10** area, **with no walls**; the boundary is floor tape (2026-08-27) — **provisionally a 10 FOOT square (3048 mm) of blue painters tape forming a COMPLETE CLOSED BOX** (operator, 2026-09-08, "not set in stone") |
| **Floor** | **Multicolour classroom carpet — MEASURED 2026-09-08.** Supersedes the earlier `[ASSUMED]` "carpet or tile" range |
| ~~**Autonomy**~~ | ~~"Robot… finds" — implies an autonomous run~~ **SUPERSEDED 2026-08-27.** The relayed answer is self-contradictory (above). Autonomy is our **choice**, not an established requirement — see FR-1 |

### What it does NOT establish — must be asked

| Open question | Why it changes the build |
|---|---|
| ~~**10×10 in what units?**~~ | ⚠ **PROVISIONALLY ANSWERED 2026-09-08 by the operator: a 10 FOOT square (3048 mm) — "not set in stone".** It is the **expensive** end of the range and it converts two optimisations into requirements: [COMPUTED at the speeds actually MEASURED] a **one-sensor** sweep at 55 mm/s is **75 lanes / 229 m / ~69 min** and fits no plausible demo slot; a **two-sensor** sweep at 300 mm/s is **38 lanes / 116 m / ~6.4 min**. Still worth confirming, and a Builder with a tape measure closes it outright ([plans/known-unknowns.md](./plans/known-unknowns.md) KU-P1, [plans/risk-register.md](./plans/risk-register.md) R-01). |
| ~~**What bounds the area?**~~ | **ANSWERED 2026-08-27: no walls, floor tape.** ⚠ Anything in this repo that assumes **walls** is superseded — the Distance Sensor 45604 has no boundary role left, and the Force Sensor 45606 has nothing to bump. *(Neither is permanently excluded: an obstacle-stop role, and a team-supplied reference beam, would revive them. Nobody has asked.)* |
| ~~**Which tape — blue painters or silver/grey duct?**~~ | ✅ **ANSWERED AND MEASURED 2026-09-08: blue painters tape.** Rule of record `b/(r+g+b) >= 0.44` (carpet ceiling 0.408, tape 0.476–0.496), **PROVEN in motion** — `drive_to_tape.py` stopped on the tape correctly, untethered on battery. **Width 1 inch / 25.4 mm in the test area, and it may differ on demo day** — carried as a config value. ⚠ **Whether crossing the tape is a scored failure is still open** (KU-P14). |
| **Are decoy notes of other colors present?** | Still open — but **de-fanged 2026-09-08**. The count rule is now brightness (`reflection() >= 30`) and is **colour-agnostic**, and classification is **report-only and never gates the count** — so a decoy changes the reported *class*, not the *count*. Two mine colours (yellow and pink) are confirmed present; blue is guaranteed *not* to be a mine. |
| **Is a human operator allowed at all?** | The relayed answer says both yes-with-a-condition and no. Until confirmed, autonomy is assumed. If a blind operator is permitted, it changes **who reads the result** (FR-4) and **who holds the keyboard** (course role rule), and refunds no navigation work. |
| **What does "finds" mean as a deliverable?** A count? Locations? Stopping on each one? Physically retrieving them? | A count is a two-day build. A location map needs reliable odometry and is a different project. |
| **How many mines, and how are they placed?** Fixed count? Spread out, or possibly adjacent? | Adjacent notes are the classic double-count/merge failure. |
| **How is Demo Day scored?** Time limit, attempts, accuracy tolerance, may the Builder intervene? | Decides whether we optimize for speed or for not-missing-any. They pull in opposite directions. |
| **Is the arena the same for every team, and can we practice on it?** | Calibration is floor- and lighting-specific. Practicing on the wrong surface is wasted tuning. |

**Ask these at the next class meeting** — the list is maintained as a single page at
[plans/questions-for-the-professor.md](./plans/questions-for-the-professor.md).

### How we proceed meanwhile

We build to the **narrowest defensible reading**: sweep a bounded square area, detect yellow sticky
notes on the floor, count them, and report the count on the hub without a laptop. Everything is
parameterized — arena size, lane width, thresholds, and target color are inputs, not constants — so a
clarified answer changes a value, not the architecture. Anything still guessed stays marked `[ASSUMED]`.

---

## Requirements

> Provisional — derived from the working assumption above. Re-derive when the briefing lands.

### Functional (FR)

- [ ] **FR-1** The robot shall traverse the designated arena after a single operator start action.
  ⚠ **`[ASSUMED]` — autonomy remains our reading, and the 2026-08-27 answer did not settle it.** The word
  "autonomous" appears **nowhere** in the course instructions (checked 2026-08-26), and the relayed answer
  of 2026-08-27 is self-contradictory (§ Mission). **We keep autonomy as the design baseline by choice**,
  because the permitted alternative would be a *blind* operator — which removes none of the navigation
  work and adds a control link this project has never exercised.
  **⚠ SUPERSEDED:** the earlier claim that "if teleoperation is allowed the project simplifies enormously"
  is **withdrawn**. Reasoning: [plans/blind-teleoperation.md](./plans/blind-teleoperation.md).
  Confirmation question queued as Q0b in [plans/questions-for-the-professor.md](./plans/questions-for-the-professor.md).
- [ ] **FR-2** The robot shall detect a target on the floor beneath its sensor and distinguish it from the floor.
- [ ] **FR-2b** The robot shall classify a detected target by **color**, and shall report a reading it cannot confidently classify as UNKNOWN rather than forcing it into a class.
- [ ] **FR-3** The robot shall count each distinct target exactly once (no double-count, no miss).
- [ ] **FR-4** The robot shall report the final result to the operator without a laptop attached (hub light matrix and/or speaker) — per-color counts, a total, and the number of unclassified readings.
- [ ] **FR-5** The robot shall stop cleanly at end-of-run or on operator stop.
- [ ] **FR-6** The robot shall remain inside the arena boundary.
  **Boundary type answered 2026-08-27: tape on the floor, no walls.** This gives FR-6 its first possible
  design element — a boundary the colour sensor might see — and **as of 2026-09-08 it IS a capability**:
  two colour sensors are mounted, the tape rule `b/(r+g+b) >= 0.44` is MEASURED and was PROVEN in motion
  (`drive_to_tape.py` stopped on the tape, untethered on battery), and the arena is a complete closed box
  of blue tape. Consequence (a) still stands: **with no walls there is no physical backstop** — a
  boundary miss is unbounded, though the MEASURED **~3 mm coast** after a stop trigger means very little
  margin has to be bought.
  ⚠ **SUPERSEDED 2026-09-08 — consequence (b) as written is no longer true.** It said *"to a
  presence-only detector, tape and a mine are the same event"*. **On the real carpet they are not:**
  blue tape reads `reflection()` **7–9**, which sits **inside** the carpet band of **3–9**, while mines
  read **51–73** (yellow) and **97+** (pink). The mine rule is a brightness threshold of **30**, so the
  **mine detector cannot see the tape at all** — the tape-vs-mine ambiguity dissolves rather than being
  mitigated. No guard band, no blue veto and no tape colour class is needed for FR-6, and the
  event-width gate in [`src/detector.py`](../src/detector.py) is retained for *other* reasons (adjacent
  notes, bright carpet flecks), not for this one.
  [findings/colour-survey-and-first-detection-2026-09-08.md](./findings/colour-survey-and-first-detection-2026-09-08.md).

### Technical (TR)

- [ ] **TR-1** All robot code runs on the hub's **stock LEGO MicroPython**. No third-party firmware.
- [ ] **TR-2** Mission logic (detection, counting, sweep state, odometry) shall be **pure Python, importable and runnable on the Ubuntu host** with no hub attached — LEGO API access confined to `src/hub_*.py`. This keeps the logic developable and hand-checkable while the hub is in the yellow box. Flat `src/`, boundary guarded by a grep: [ADR-0004](./decisions/0004-flat-src-supersedes-package-split.md). Verification itself happens on the robot: [ADR-0005](./decisions/0005-no-test-suite-verify-on-hardware.md).
- [ ] **TR-3** The program shall run standalone from the hub (download mode), not tethered to a laptop, so Demo Day does not depend on a USB cable.
- [ ] **TR-4** Detection thresholds shall be **calibrated at run start**, not hard-coded, so a floor/lighting change does not require a code edit.
- [ ] **TR-5** Sensor/motor port assignments shall live in ONE place ([docs/hardware/port-map.md](./hardware/port-map.md)) and be referenced by the code, not scattered as literals.

### Resource (RR)

- [ ] **RR-1** Build only from parts purchasable within the 100 Schrute Buck budget. No real money.
- [ ] **RR-2** Development host: native Ubuntu 22.04, free/open-source tooling only.
- [ ] **RR-3** Sensors limited to what the course store offers: Color 45605, Distance 45604, Force 45606, plus the hub gyro and motor encoders.
- [ ] **RR-4** Motors limited to the Technic **Large Angular 45602**, **Medium Angular 45603**, and **Small Angular 45607**. *(Corrected 2026-08-25 — there are three, not two; the Medium is the fastest at 1110 deg/s.)* **Which two we own: both are Medium Angular 45603 — reported by the operator 2026-08-27.** RELAYED, not inspected by anyone in this repo; the definitive close is the motor device type ID read at bring-up.
- [ ] **RR-5** Store prices may change during the project. The budget ledger records the price actually paid per entry ([course/budget.md](./course/budget.md)); never hard-code a price list.

**Parts owned as of 2026-08-27:** 2 motors and 2 wheels. **The motors are both Medium Angular 45603**
(operator, 2026-08-27). **Wheel type and diameter are still UNKNOWN and unmeasured** — several sizes are
on hand, and every odometry figure in the repo depends on the effective rolling diameter. Balance 56 SB
([course/budget.md](./course/budget.md)).
**Not yet owned:** sensors, mounting blocks, axles. Sensor mounting height and angle are therefore still
free variables — which is why the mounting geometry is researched *now*, before the purchase.

**Hodge-podge hardware: measure, don't model.** Wheel diameter, track width, top speed, loop rate and
cross-track error are unmeasured and stay as config variables until the bench session closes them —
[plans/bench-measurement-plan.md](./plans/bench-measurement-plan.md),
[lessons_learned/model-only-to-the-next-decision.md](./lessons_learned/model-only-to-the-next-decision.md).

---

## Constraints

| Constraint | Source | Flexible? |
|---|---|---|
| Team *collaboration* happens in class; individual programming/design work may happen anytime | Course instructions p.1, as ruled by the operator 2026-08-25 | Resolved — see § Critical Notes |
| Role separation is enforced; violations cost 2 Schrute Bucks each | Course instructions, p.1 | No |
| Programmer may not touch supplies (except plugging the robot into their laptop) | Course instructions, p.1 | No |
| 100 Schrute Buck budget; buy-back at 90% rounded down | Course instructions, p.1 | No |
| In-person meetings beyond the daily 5-min standup are billed 1 SB/person/minute | Course instructions, p.2 | No |
| Written digital communication is unlimited **but must be submitted in full at project end** | Course instructions, p.1 | No |
| Supplies stored in the team's yellow box between classes | Course instructions, p.1 | No |
| Hub firmware must not be replaced or flashed | Operator decision + shared equipment | **No — blacklisted** |
| Hub OS version treated as frozen — identified read-only 2026-08-27, and stays frozen. **One file was written to the hub's filesystem the same day** (`/flash/lib/config.py`), and the firmware was **proved unchanged** by re-capturing the baseline and diffing it: every stock file byte-identical, module list, API surface and device identity unchanged. `/flash` is the FAT filesystem the firmware *exposes*; the firmware itself is the MicroPython binary in the STM32F413's internal program flash, and a `.py` file cannot reach it — [findings/firmware-integrity-proof.md](./findings/firmware-integrity-proof.md) | Operator decision 2026-08-25; [ADR-0001](./decisions/0001-stock-lego-firmware-only.md) | **No — blacklisted** |
| Development host is native Ubuntu; LEGO does not officially support Linux desktop | Operator's machine | No |
| Report must use the **CSER 2022 / Elsevier Procedia MS Word template** | `course/source-material/cser_template_cser2022 (7).docx` | No |

## Assumptions

- `[ASSUMED]` The mission is arena sweep + target detection/count (see § Mission). **Highest-risk assumption in this document.**
- `[ASSUMED]` The operator's role on the team is **Programmer** — inferred from "don't worry about the physical design specifications" and from [archives/operator-notes/2026-08-25_spike-platform-notes.md](archives/operator-notes/2026-08-25_spike-platform-notes.md). Confirm.
- `[ASSUMED]` The hub is a SPIKE Prime Technic Large Hub 45601 — supported by the operator's report of 6 ports (A–F) across two sides; SPIKE Essential has only 2.
- `[MEASURED 2026-08-27]` Hub OS generation is **SPIKE 3 / current API** — MicroPython 1.24.0, `motor` / `motor_pair` / `runloop` / `color_sensor` present, **no `spike` module**. Read off our own hub over USB, read-only: [findings/hub-first-contact-2026-08-27.md](./findings/hub-first-contact-2026-08-27.md). Legacy SPIKE 2 material will not run on this hub at all.
- `[MEASURED 2026-09-08]` Arena floor is **multicolour classroom carpet** — `reflection()` 3–9, `r+g+b` 49–107 (median 79). ⚠ **Supersedes the earlier `[ASSUMED]` "carpet or tile" range.** Carpet slip proved *not* to be the problem feared: left/right encoders tracked within **0.4 %** over a 155 mm drive. [findings/colour-survey-and-first-detection-2026-09-08.md](./findings/colour-survey-and-first-detection-2026-09-08.md)
- `[PROVISIONAL 2026-09-08, operator]` Arena is a **10 FOOT square (3048 mm)**, a complete closed box outlined in **blue painters tape** — explicitly **"not set in stone"**. Carried as the planning value in [`src/mission_config.py`](../src/mission_config.py); a change on the day edits two numbers and nothing else.
- `[DECIDED 2026-08-25 by the team]` Initial drive design is **2 motors + 2 wheels** (differential drive). Recorded, not designed, here.
- `[MEASURED 2026-09-03]` Wheel diameter **63.5 mm** (2.5 in) and effective track width **95 mm** — confirmed by a driven 1 ft square. ⚠ **Supersedes the earlier `[UNKNOWN]`.** Propagated to [`src/mission_config.py`](../src/mission_config.py).
- `[UNMEASURED]` **Colour-sensor spacing (`SENSOR_SPACING_MM`) and fore-aft offset** — known only to be **wider than a 76 mm sticky note** (MEASURED lower bound: one note cannot cover both sensors). It blocks the corner-turn radius and the effective swath, and it is the **highest-priority measurement in the project** — a ruler, sixty seconds ([plans/known-unknowns.md](./plans/known-unknowns.md) KU-M33).

---

## Boundaries

### In Scope

- SPIKE Prime robot software (sweep, detection, counting, reporting, calibration).
- Host-side tooling to get code onto the hub and read results back from Ubuntu.
- Systems-engineering artifacts: requirements, ADRs, verification evidence, findings.
- Course deliverables: daily journal entries, the CSER-format Intro Report, the communications record.
- Hardware record kept as a **written description supplied by the operator** — port map, BOM/budget ledger, build notes. Enough to write the report and to make the port map authoritative for the code.

### Out of Scope (deliberate exclusions — may revisit)

- **Detailed physical/mechanical design.** The Designer owns this. The operator explicitly deprioritized it: we record what the build *is*, we do not design it here.
- Purchasing decisions and the Schrute Buck economy strategy — the Supplier's role; we only keep the ledger.
- Computer vision, cameras, or any sensor the course does not supply.
- A simulator or digital twin of the arena. Calibrate on the real floor instead.
- Multi-robot coordination.
- Anything requiring real money.

### PERMANENTLY Out of Scope (BLACKLIST — enforced, not deferred)

1. **Pybricks or any third-party firmware.** It replaces the hub's LEGO firmware. Never install, never recommend, never "just to test". Excluded even though it supports Linux well.
2. **Any DFU, bootloader, filesystem-format, or factory-reset operation on the hub.**
3. **Accepting an unattended "Hub update required" prompt.** The hub's software state is only changed by an explicit operator decision recorded as an ADR.
4. **Convening the team to build outside of class**, which is what the course rule actually forbids — see § Critical Notes.
5. **Committing, pushing, or otherwise mutating git.** Agent-side git mutations are human-only; agents propose commands, the operator runs them.
6. **Fabricated results.** No invented sensor readings, no "it should work" reported as "it works", no green test over untested hardware. See [directives/honest-instrumentation.md](./directives/honest-instrumentation.md).
7. **claude.ai connectors** (Gmail, Google Calendar, Google Drive, Spotify). They surface as unauthorised in this session; they are **not used by this project and should not be**. Operator's ruling 2026-08-25 — ignore the prompts, do not authorise them, do not build anything that depends on them. The project's only external services are the local docs-rag and ResearchHub over the pwnstar tunnel.
8. **A host-side test suite.** Removed 2026-08-25 — verification happens on the robot ([ADR-0005](./decisions/0005-no-test-suite-verify-on-hardware.md)). Do not re-introduce one without a new ADR.
9. **A LibreOffice MCP server, and a `libre_mcp/` child project.** Considered and **deferred entirely** by the operator 2026-08-26, before any work started. **The problem it would solve is already solved:** **confirmed on this host** that LibreOffice round-trips the CSER `.docx` with all 20 styles and the trim size intact ([findings/cser-template-libreoffice-roundtrip.md](./findings/cser-template-libreoffice-roundtrip.md)), so no Word installation and no automation layer is needed to produce the report. Building an MCP server to drive a document editor we can already drive by hand would be a second project competing with a robot due 10 SEP. **Revisit only if report assembly turns out to be genuinely painful**, and not before.
10. **Session-time budgeting and drop-order bookkeeping.** Operator ruling 2026-08-26: do not track or maintain per-task minute estimates. Dependency *order* between measurements is worth documenting; a minute total is not, and keeping it current is a waste of effort and tokens.

---

## Technical Decisions

| Decision | Choice | Rationale | Date |
|---|---|---|---|
| Firmware | Stock LEGO, never replaced | Shared equipment; operator constraint | 2026-08-25 |
| Hub programming language | LEGO MicroPython on the hub | Only Python route that keeps stock firmware | 2026-08-25 |
| Code architecture | Pure mission logic + thin hub I/O adapter | Makes a real host-side test floor possible without hardware — see [ADR-0002](./decisions/0002-split-mission-logic-from-hub-io.md) | 2026-08-25 |
| Host toolchain | Ubuntu native; route pending research | See [docs/research/spike-prime-linux-toolchain.md](./research/spike-prime-linux-toolchain.md) | 2026-08-25 |

Full records: [docs/decisions/INDEX.md](./decisions/INDEX.md)

---

## Our hub — identity of record

**This is Team 21's hub. Every ID below is measured off the physical unit; none is a guess.**

| Property | Value | How read |
|---|---|---|
| `hub.device_uuid()` | **`03970000-3600-1B00-1450-30514B323320`** | USB **and** confirmed over BLE |
| `hub.hardware_id()` | **`E`** | USB |
| `machine.unique_id()` | `36 00 1B 00 14 50 30 51 4B 32 33 20` (the tail of the UUID) | USB |
| BLE address | **`64:8C:BB:0A:1C:8C`** | BLE scan |
| BLE advertised name | **`Team 21`** | BLE scan (user-settable — not proof) |
| Firmware | MicroPython v1.20.0-1742.gf212bbe83 (2025-03-27), STM32F413, RPC 1.0.47, Hub OS 1.8.149 | USB + BLE |

**Identify by connecting and comparing the `device_uuid`** (`DeviceUuidRequest 0x1A`). **Never by name**
(anyone can set it, including to ours) and **never by BLE address alone** (its type is unverified and
may rotate). Full record: [findings/hub-first-contact-2026-08-27.md](./findings/hub-first-contact-2026-08-27.md),
[findings/ble-protocol-2026-08-27.md](./findings/ble-protocol-2026-08-27.md).

**Why this is in scope, not just a finding.** The team may **contract its programming/design services
to other groups for Schrute Bucks** (authorized; see [plans/competitive-interference.md](./plans/competitive-interference.md)
and the class economy). That means working against **other hubs with different `device_uuid`s, MACs and
names.** So the rule is permanent: **our tooling matches the specific hub it is told to target and
verifies the UUID before it acts** — it never assumes "the LEGO hub in range is ours." We already
connected to another team's hub once by taking the first match
([lessons_learned/prove-identity-before-you-act.md](./lessons_learned/prove-identity-before-you-act.md)).
When we take a contract, record that hub's IDs in the job's own note, never overwrite this block.

---

## Critical Notes

- **"You MAY NOT work on the project outside of class" — RESOLVED 2026-08-25 by the operator.** The rule governs *team collaboration* (the whole team convening to build together), not the individual programming component. The Programmer and Designer may work on software and design outside class. **This is not a blocker.** Physical assembly and store purchases still happen in class with the roles enforced, and the operator keeps the human-side coordination record.
- **Communications are graded and submitted in full.** Everything written in Discord/email is part of the deliverable. Keep the record collectible from day one — see [docs/course/team/communications.md](./course/team/communications.md).
- **The Builder is the only person who may operate the robot.** The Programmer plugs in and unplugs; that is the only supply contact allowed.
- **Demo Day is 10 SEP 2026.** Everything technical is subordinate to being demonstrably working on that date.

---

## Revision History

| Date | Changes | By |
|---|---|---|
| 2026-09-08 | **Four mission facts corrected by the operator, and the first real-surface measurements.** § Mission gains a dated corrections block: the arena is **provisionally a 10 FOOT square (3048 mm)**, "not set in stone"; the graded arena is a **COMPLETE CLOSED BOX** of blue painters tape and **the practice area's incomplete tape is not it**; the floor is **multicolour classroom carpet [MEASURED]**; the mines are **yellow *and* pink**, may change on the day, and are **never blue**. Closed the "which tape" question (**blue painters, MEASURED**) and struck two `[ASSUMED]`/`[UNKNOWN]` assumptions (floor; wheel diameter + track width). ⚠ **SUPERSEDED FR-6 consequence (b)** — *"to a presence-only detector, tape and a mine are the same event"* is **false on this carpet**: tape reads `reflection()` 7–9, *inside* the carpet band 3–9, against mines at 51–73 and 97+, so the brightness rule (threshold 30) cannot see the tape at all and no blue veto is needed. Added the `[UNMEASURED]` colour-sensor spacing as an explicit assumption. | Claude |
| 2026-08-25 | Initial draft from course instructions + operator answers. Mission left PENDING. | Claude |
| 2026-08-25 | Added FR-2b (color classification), RR-4/RR-5 (motors, changing prices), the 2-motor/2-wheel design decision, and the parts-owned status. | Claude |
| 2026-08-25 | Captured the verbal design briefing (§ Mission): find all mines, yellow sticky notes, 10×10 area. Resolved the out-of-class-work constraint — not a blocker. Status Draft → Active. | Claude |
| 2026-09-01 | Added **§ Our hub — identity of record** (device_uuid `03970000-3600-1B00-1450-30514B323320`, BLE `64:8C:BB:0A:1C:8C`, name `Team 21`), because contracting services to other groups means targeting other hubs and identity must be verified, never assumed. | Claude |
| 2026-08-27 | **Deploy path established and the firmware proved untouched.** Code reaches the hub over USB with no LEGO app: base64 chunks over the MicroPython REPL into `/flash/lib`, verified by a SHA-256 the hub computes on itself ([ADR-0007](./decisions/0007-deploy-by-writing-modules-to-flash-lib.md), [runbooks/deploy-to-hub.md](./runbooks/deploy-to-hub.md)). Baseline re-capture + diff showed the one expected delta and nothing else ([findings/firmware-integrity-proof.md](./findings/firmware-integrity-proof.md)). IMU units derived from gravity — milli-g and decidegrees, yaw wraps at ±180° ([findings/imu-characterisation-2026-08-27.md](./findings/imu-characterisation-2026-08-27.md)). **What is NOT established: how a *program* is launched** — whether `/flash/main.py` autoruns at boot is untested. | Claude |
| 2026-08-27 | Recorded three relayed answers (§ Mission): mine colour yellow *(hedged)*, **no walls — floor-tape boundary**, and an autonomy reply that **contradicts itself** and is therefore NOT treated as answered. Superseded everything assuming walls; gave FR-6 its first possible design element; **withdrew FR-1's claim that teleoperation would simplify the project**. Closed the Hub OS generation (SPIKE 3, measured) and the motor type (both Medium 45603, operator-reported). The **units of "10×10" remain unanswered and still gate the architecture**. | Claude |
