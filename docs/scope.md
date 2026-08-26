# SYS 301 Minesweeper — Scope

> Last updated: 2026-08-25
> Status: **Active** — mission captured from the verbal briefing 2026-08-25; several parameters still open (see § Mission)
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

### What this establishes

| | |
|---|---|
| **Task** | Find **all** the mines — coverage is the success criterion, not a sample |
| **Target** | Sticky notes, **yellow** (the operator's recollection is hedged: *"I think"*) |
| **Arena** | A **10×10** area |
| **Autonomy** | "Robot… finds" — implies an autonomous run |

### What it does NOT establish — must be asked

| Open question | Why it changes the build |
|---|---|
| **10×10 in what units?** Feet, tiles, grid cells, inches? | Directly sets sweep-leg length, run time, and how much odometry drift accumulates. 10 ft and 10 floor tiles are very different problems. |
| **What bounds the area?** Walls, tape line, colored border, or nothing? | Decides whether we need the **distance sensor** (walls), a second **color** channel (tape line), or pure odometry (nothing). This is the single biggest hardware-purchase consequence. |
| **Only yellow, or several colors with yellow being the mine?** | If yellow is the only color present, reflected-light presence detection suffices and is far more robust. If other colors are decoys, we need real classification (FR-2b) — a materially harder problem on matte pastel paper. |
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
  ⚠ **`[ASSUMED]` — autonomy is our INFERENCE, not a stated requirement.** Checked 2026-08-26: the word
  "autonomous" appears **nowhere** in the course instructions, and the verbal briefing says only *"a robot
  that finds all the mines"*. § Mission already flags this as an inference; FR-1 had hardened it into a
  requirement without the marker. **If teleoperation is allowed the project simplifies enormously** — see
  [plans/questions-for-the-professor.md](./plans/questions-for-the-professor.md) Q0.
- [ ] **FR-2** The robot shall detect a target on the floor beneath its sensor and distinguish it from the floor.
- [ ] **FR-2b** The robot shall classify a detected target by **color**, and shall report a reading it cannot confidently classify as UNKNOWN rather than forcing it into a class.
- [ ] **FR-3** The robot shall count each distinct target exactly once (no double-count, no miss).
- [ ] **FR-4** The robot shall report the final result to the operator without a laptop attached (hub light matrix and/or speaker) — per-color counts, a total, and the number of unclassified readings.
- [ ] **FR-5** The robot shall stop cleanly at end-of-run or on operator stop.
- [ ] **FR-6** The robot shall remain inside the arena boundary.

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
- [ ] **RR-4** Motors limited to the Technic **Large Angular 45602**, **Medium Angular 45603**, and **Small Angular 45607**. *(Corrected 2026-08-25 — there are three, not two; the Medium is the fastest at 1110 deg/s. Which two we own is open: [KU-T3](./plans/known-unknowns.md).)*
- [ ] **RR-5** Store prices may change during the project. The budget ledger records the price actually paid per entry ([../inventory.py](../inventory.py)); never hard-code a price list.

**Parts owned as of 2026-08-25:** 2 motors and 2 wheels — **types of both unknown**, and several wheel
sizes are on hand. Balance 56 SB (`./inventory.py --verbose`).
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
| Hub OS version treated as frozen until identified | Operator decision, 2026-08-25 | Revisit after read-only identification |
| Development host is native Ubuntu; LEGO does not officially support Linux desktop | Operator's machine | No |
| Report must use the **CSER 2022 / Elsevier Procedia MS Word template** | `course/source-material/cser_template_cser2022 (7).docx` | No |

## Assumptions

- `[ASSUMED]` The mission is arena sweep + target detection/count (see § Mission). **Highest-risk assumption in this document.**
- `[ASSUMED]` The operator's role on the team is **Programmer** — inferred from "don't worry about the physical design specifications" and from [archives/operator-notes/2026-08-25_spike-platform-notes.md](archives/operator-notes/2026-08-25_spike-platform-notes.md). Confirm.
- `[ASSUMED]` The hub is a SPIKE Prime Technic Large Hub 45601 — supported by the operator's report of 6 ports (A–F) across two sides; SPIKE Essential has only 2.
- `[UNKNOWN]` Which Hub OS generation is installed. Determines whether the code targets the SPIKE 3 API (`import motor`) or the legacy SPIKE 2 API (`from spike import PrimeHub`). Resolve by read-only identification before writing mission code.
- `[ASSUMED]` Arena floor is classroom carpet or tile — materially affects odometry accuracy and reflected-light thresholds.
- `[DECIDED 2026-08-25 by the team]` Initial drive design is **2 motors + 2 wheels** (differential drive). Recorded, not designed, here.
- `[UNKNOWN]` Wheel diameter and track width — both are required for any odometry arithmetic. Measure and record in [hardware/build-record.md](./hardware/build-record.md).

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

## Critical Notes

- **"You MAY NOT work on the project outside of class" — RESOLVED 2026-08-25 by the operator.** The rule governs *team collaboration* (the whole team convening to build together), not the individual programming component. The Programmer and Designer may work on software and design outside class. **This is not a blocker.** Physical assembly and store purchases still happen in class with the roles enforced, and the operator keeps the human-side coordination record.
- **Communications are graded and submitted in full.** Everything written in Discord/email is part of the deliverable. Keep the record collectible from day one — see [docs/course/team/communications.md](./course/team/communications.md).
- **The Builder is the only person who may operate the robot.** The Programmer plugs in and unplugs; that is the only supply contact allowed.
- **Demo Day is 10 SEP 2026.** Everything technical is subordinate to being demonstrably working on that date.

---

## Revision History

| Date | Changes | By |
|---|---|---|
| 2026-08-25 | Initial draft from course instructions + operator answers. Mission left PENDING. | Claude |
| 2026-08-25 | Added FR-2b (color classification), RR-4/RR-5 (motors, changing prices), the 2-motor/2-wheel design decision, and the parts-owned status. | Claude |
| 2026-08-25 | Captured the verbal design briefing (§ Mission): find all mines, yellow sticky notes, 10×10 area. Resolved the out-of-class-work constraint — not a blocker. Status Draft → Active. | Claude |
