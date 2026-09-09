# SYS 301 Minesweeper — Todo (SSOT)

> Last updated: 2026-09-08 (evening, after the heavy hardware day) · **mode: detection is SOLVED and
> PROVEN on the real floor; delivery is not. `src/main.py` is written and reviewed but has STILL NEVER RUN
> on hardware, and the mission code is still a one-sensor robot. Demo Day is 10 SEP — two days.**

> **2026-09-01 checkpoint: the robot drives.** Forward/back/turn confirmed, drive convention locked
> ([findings/drive-checkpoint-2026-09-01.md](./findings/drive-checkpoint-2026-09-01.md)). docs-rag
> `/api/ask` now works. Still owed: wheel diameter (ruler), the units of 10×10 (professor),
> real GATE 1 on the actual notes/tape/floor, a measured stored-program run, and the `src/hub_api.py`
> port constants.

> **2026-09-03 checkpoint: the pieces converged.** Robot drove a defined 1 ft square untethered —
> **wheel Ø 63.5 mm and track width 95 mm MEASURED**, drives straight. `slot_upload.py --apply` proven +
> hardened (auto-minify, multi-chunk); `deploy_deps.py` auto-resolves a program's `src/` imports.
> **`src/main.py` WRITTEN** (irreducible core, reviewed — no motor-safety/crash bug). `floor_anomaly`
> validated 0%-false on real floor data. Wheel-diameter and port-constant items above are now DONE.
> Still owed: the units of 10×10 (professor), a real-mine detection test, and the first `main.py` run.
> See [session_records/2026-09-03_square-fusion-main-py-and-hub-tooling.md](./session_records/2026-09-03_square-fusion-main-py-and-hub-tooling.md).

> **2026-09-08 checkpoint: GATE 1 IS CLOSED — the robot found a real mine, while moving, untethered on
> battery, twice.** `NOTE_FOUND colour=PINK refl=99` and `NOTE_FOUND colour=YELLOW refl=62`, **both
> correctly classified** ([findings/colour-survey-and-first-detection-2026-09-08.md](./findings/colour-survey-and-first-detection-2026-09-08.md)).
> ⚠ **The detection rule CHANGED to get there.** The shipped chromaticity anomaly detector **FAILS on the
> real carpet** — yellow measured **INVISIBLE** (0 % of samples cleared threshold), blue tape tripped it
> **100 %** — because the carpet totals only ~79 ADC counts and its chromatic sigma is under one count.
> Replaced by a **brightness rule, `reflection() >= 30`**: carpet 3–9, blue tape 7–9, yellow 51–73, pink 97+ —
> **zero overlap, a 43-point gap, colour-agnostic**, and the tape sits *inside* the carpet band so no blue
> veto is needed. Also MEASURED: 20 Hz tick while driving and logging, ~3 mm coast, L/R encoders within
> 0.4 %, tape rule `b/(r+g+b) >= 0.44` PROVEN in motion, colour sensor **C = RIGHT, D = LEFT**, and
> **positive yaw = physically LEFT**. Line following was analysed and **dropped for Demo Day**
> ([findings/line-following-viability-2026-09-08.md](./findings/line-following-viability-2026-09-08.md)).
> Still owed: the first `src/main.py` run, the **sensor spacing** (a ruler), and the **one-sensor swath bug**.

## ▶ NEXT SESSION — START HERE

**[plans/next-session.md](./plans/next-session.md)** — the ordered plan, grouped by **what each item
needs** (professor only · teammate only · hub over USB · a colour sensor without the robot · the robot
built · a keyboard), so whatever is present at the start of class can be worked immediately.

**The three real blockers now, in order** — all changed on 2026-09-08: ① **`src/main.py` has never run on
hardware** (KU-M29), and an upload can hash-verify and *still* die at import — `import config` on the hub
resolves to something in the LEGO firmware, not our file (KU-M38) · ② **the mission code is a ONE-SENSOR
robot** — `src/hub_color.py` reads only `COLOR_PORT`; `SECOND_COLOR_PORT` is declared and read nowhere in
`src/` (KU-D11), which at 10 ft is the difference between 75 lanes and 38 · ③ **`SENSOR_SPACING_MM` is
[UNMEASURED]** (KU-M33) — a ruler, sixty seconds, and it unblocks the corner-turn radius and the swath.
The old ① (units) is **provisionally answered** — 10 FOOT square, operator-stated 2026-09-08, *not set in
stone*. The old ② (real-mine detection) is **CLOSED** — GATE 1, twice. The stored-program path stays
solved. First-run procedure: [runbooks/first-main-run.md](./runbooks/first-main-run.md).
⚠ **Power-cycle the hub between any REPL/probe work and a slot upload** — Ctrl-C kills the Hub OS and
Ctrl-D does **not** bring it back (tested properly, 25 s of retries).

**Do not re-investigate** the API generation, the deploy route, or whether Bluetooth works. All three
are closed by measurement — [session_records/2026-08-27](./session_records/2026-08-27_hub-first-contact-usb-and-ble.md).

---

## CURRENT STATE

**Everything buildable without the professor's answers is built, and the detection problem is now SOLVED
on real hardware.** 15+ `src/` modules (pure + hub-facing, one file per device), the full SE planning
layer, Bluetooth answered, telemetry designed and widened to 21 columns, the analysis layer specced.
**`src/main.py` is WRITTEN and reviewed** (irreducible core, 2026-09-03 — no motor-safety or crash
defect found) — ⚠ **and it has STILL NEVER RUN on hardware** (KU-M29). Every behaviour this project has
actually proven belongs to a program in `examples/`, not to `main.py`. Do not report it as working.

**The hub has been connected — 2026-08-27, over USB, on `/dev/spike`.** It is SPIKE 3 /
MicroPython 1.24.0, its filesystem is baselined, and **code has been put on it**: `/flash/lib/config.py`
uploaded and imported, with the firmware **proved unchanged** by a baseline re-capture and diff. The IMU
is characterised.

**The robot has since been built, measured, and driven untethered — 2026-09-01 → 2026-09-08.**
A=left motor, B=right motor, **C = RIGHT colour sensor, D = LEFT**, E/F empty; forward is `A:-v, B:+v`
and **positive yaw = physically LEFT**. `src/hub_api.py`'s port constants **are now filled in**
(`COLOR_PORT = _port.C`, `SECOND_COLOR_PORT = _port.D`). Wheel Ø **63.5 mm**, effective track width
**95 mm**, both MEASURED. `/flash/main.py` does not autorun, but that no longer matters: the **Hub OS
slot route is PROVEN** — `slot_upload.py --apply` uploads and starts, and a slot program drives, prints,
logs to `/flash` and keeps running with the laptop unplugged.

⚠ **Two defects in the mission code, both found 2026-09-08, both still present:**

1. **`src/hub_color.py` reads only `hub_api.COLOR_PORT`.** `SECOND_COLOR_PORT` is declared and read
   **nowhere in `src/`** — so the graded sweep has a **one-sensor swath** while two sensors are mounted
   and both are read fine by the `examples/` programs. At 10 ft that is 75 lanes / 229 m / ~69 min
   versus 38 lanes / 116 m / ~6.4 min [COMPUTED]. (KU-D11)
2. **`config.DETECT_MODE` still defaults to `"anomaly"`** and `main.py` early-returns for anything else —
   but the anomaly front-end is the one **refuted** on the real carpet. The brightness rule is ~12–15
   lines away because `src/calibration.py` is already written, pure and host-runnable.

⚠ **Operational constraint (MEASURED 2026-09-08):** `hub_programmer/run.py`, `probes/` and `download.py`
send **Ctrl-C, which KILLS the Hub OS** — and `slot_upload.py` needs it alive. **Power-cycle the hub
between REPL work and a slot upload.** A Ctrl-D soft reset was properly tested (protocol verification,
25 s of retries) and does **not** work. Batch every `download.py` retrieve into one call at end of
session — ~20 separate retrieves on 2026-09-08 cost ~20 power cycles. **The CENTER button stops a
running program**, and a running program blocks a new one from starting.
⚠ **`import config` is SHADOWED on the hub** — it resolves to something in the LEGO firmware, not
`/flash/lib/config.py`, and the program dies at import **even though the upload hash-verifies**
(KU-M38). `src/hub_drive.py` works around it by mirroring the geometry locally and asserting it against
`config.py` on the **host**, where `./scripts/check-docs.py` catches any drift.

| What | Where |
|---|---|
| Identity, API generation, filesystem, radio | [findings/hub-first-contact-2026-08-27.md](./findings/hub-first-contact-2026-08-27.md) |
| The one write, the diff, and why the firmware cannot be touched by it | [findings/firmware-integrity-proof.md](./findings/firmware-integrity-proof.md) |
| IMU units, ±180° yaw wrap, read cost, drift | [findings/imu-characterisation-2026-08-27.md](./findings/imu-characterisation-2026-08-27.md) |
| How to put code on the hub | [runbooks/deploy-to-hub.md](./runbooks/deploy-to-hub.md) · [ADR-0007](./decisions/0007-deploy-by-writing-modules-to-flash-lib.md) |
| Built robot port/sign convention | [hardware/port-map.md](./hardware/port-map.md) · [findings/drive-checkpoint-2026-09-01.md](./findings/drive-checkpoint-2026-09-01.md) |
| Colour first-look and two-sensor agreement | [findings/colour-first-look-2026-09-01.md](./findings/colour-first-look-2026-09-01.md) |
| **Real surfaces, the refuted anomaly rule, and GATE 1 closed** | [findings/colour-survey-and-first-detection-2026-09-08.md](./findings/colour-survey-and-first-detection-2026-09-08.md) |
| Why line following is dropped for Demo Day | [findings/line-following-viability-2026-09-08.md](./findings/line-following-viability-2026-09-08.md) |
| Why REPL tools kill the Hub OS, and how to avoid it | [findings/hub-os-vs-repl-2026-09-08.md](./findings/hub-os-vs-repl-2026-09-08.md) · [findings/stopping-and-restarting-the-hub-2026-09-08.md](./findings/stopping-and-restarting-the-hub-2026-09-08.md) |
| The operator briefing that sets the remaining work | [plans/2026-09-08-operator-briefing-corner-turns-to-competition.md](./plans/2026-09-08-operator-briefing-corner-turns-to-competition.md) |

⚠ **Carry the remaining unknowns forward accurately.** The register was **consolidated 2026-09-08 from
~50 live rows to 27** — [plans/known-unknowns.md](./plans/known-unknowns.md). Closed on 2026-09-08:
**GATE 1 (KU-M22/M32/M6)**, the floor (carpet), the tape (blue painters), the detection scalar
(`reflection()`), the sensor's usable range, the ~3 mm coast, carpet slip, the 20 Hz loop rate, and
FR-2b demonstrated. Still open for Demo Day readiness: **the first `main.py` run**, **the one-sensor
swath**, **`SENSOR_SPACING_MM`**, whether the heading wander is bias or noise, lap-scale odometry drift,
the `motor.velocity()` unit, Hub OS relaunch without a power cycle, module-name shadowing, and the time
limit / scoring rule. The arena units are **provisionally** 10 ft — operator-stated, *not set in stone*.

Narrative: [session_records/2026-08-26_code-implementation-bluetooth-and-analysis-planning.md](./session_records/2026-08-26_code-implementation-bluetooth-and-analysis-planning.md)

## NEXT ACTION

**Make the graded program run, then make it two-sensor.** Detection is proven; delivery is not. Two days.
The hub, the drive, the deploy route and the detection rule are all closed — what is left is that
`src/main.py` has never executed and the mission code only reads one of the two mounted sensors.

1. **Builder, with a ruler, sixty seconds — no hub needed:** measure the **centre-to-centre spacing of
   the C and D colour sensors** and their **fore-aft offset**, and measure a **sticky note** and the
   **tape width** while the ruler is out. `SENSOR_SPACING_MM` does not exist in `src/config.py` today and
   it blocks the corner-turn radius and the swath (KU-M33, KU-M7, KU-P14, KU-D10).
2. **Make `src/hub_color.py` read `SECOND_COLOR_PORT` as well as `COLOR_PORT`** (KU-D11), and wire the
   brightness rule (`reflection() >= 30`) into `main.py` — `src/calibration.py` is already written, pure
   and host-runnable. ⚠ **Do not raise the lane pitch until both ports are genuinely read every tick** —
   that is the one change that silently loses mines. Then `./scripts/check-docs.py`.
3. **Run `src/main.py` on hardware for the first time** — [runbooks/first-main-run.md](./runbooks/first-main-run.md).
   **Power-cycle the hub first** if any REPL or probe tool has been used this session, or the slot upload
   will abort at the identity check (correctly — nothing is written). Expect the `config` shadowing trap
   (KU-M38): an upload can hash-verify and still die at import.
4. **Ask the professor — Q2 and Q8 in one message:** the **time limit**, whether finding *all* is
   required or the most-in-the-slot scores, attempts allowed, and any size/parts constraint. They are the
   only unanswered questions that can still change what Demo Day shows (KU-D5, KU-D9) →
   [plans/questions-for-the-professor.md](./plans/questions-for-the-professor.md). Q0 (autonomy) is
   **parked** — there is no time to build anything but an autonomous robot, whatever the answer.
5. **One long straight logged drive on the real carpet, five times** — settles whether the heading wander
   is a **systematic bias** (85 mm of cross-track drift over 3048 mm, wider than a note, mines missed) or
   **zero-mean noise** (costs almost nothing). Not needed to run the demo; needed to make any honest
   coverage claim in the Intro Report (KU-M34, KU-M35).
6. **Speed envelope test.** Every run to date has used **80–100 dps** against a MEASURED `max_speed` of
   **930 dps** — roughly 9× headroom unexploited, and at 10 ft the schedule needs it. The detector's own
   cap is ~240 mm/s at N=2 on 24 mm tape at 20 Hz, so there is real room between here and there.
7. **Builder: confirm the part numbers printed on the two motors** — `device.id` already says both are
   the same kind; the casing read closes the paperwork loop for the report.

**Start every session with `./scripts/stack.sh up`.** Nothing starts at boot by design.

---

## 🔴 In Progress

_(nothing — all host-side work is complete)_

## 🟡 Blocked

- [ ] Sweep **parameters** (lane pitch, run time, exhaustive-or-not) — **Blocked by**: professor Q2 (time limit + scoring rule) and by **KU-M33** (sensor spacing → swath). Arena size is no longer blocking: **10 ft = 3048 mm is in `config.py`**, provisionally, operator-stated 2026-09-08.
- [x] ~~Buy the distance sensor or not~~ — **moot for Demo Day.** The boundary is floor tape (2026-08-27) and no purchase is planned before 10 SEP. 56 SB unspent.
- [x] ~~Color classification (FR-2b)~~ — **KEPT, and DEMONSTRATED 2026-09-08.** The red-fraction rule (≥ 0.41 = PINK, below = YELLOW) named both real notes correctly while the robot was moving. It is **report-only and never gates the count**, so it is free to keep — and the count rule underneath it is colour-agnostic, which survives the mine colour changing on the day.
- [x] ~~Hub OS / API generation identification~~ — **CLOSED 2026-08-27: SPIKE 3, MicroPython 1.24.0**, measured over USB → [findings/hub-first-contact-2026-08-27.md](./findings/hub-first-contact-2026-08-27.md)
- [x] ~~`/flash/main.py` autorun?~~ — **CLOSED 2026-09-01: it does not autorun.** Demo Day needs the Hub OS slot route or another measured stored-program path.
- [x] ~~**Stored slot route**~~ — **CLOSED 2026-09-03/08:** `slot_upload.py --apply` uploads and starts, and slot programs (`drive_to_tape`, `find_note`) ran **untethered on battery** with the laptop unplugged.
- [x] ~~**`src/hub_api.py` port constants**~~ — **DONE.** `COLOR_PORT = _port.C`, `SECOND_COLOR_PORT = _port.D`, motors on A/B.
- [ ] ⚠ **`src/hub_color.py` reads only one sensor** — `SECOND_COLOR_PORT` is declared and read nowhere in `src/`. **Blocked by**: a code edit window. This is the single highest-value change left (KU-D11).
- [ ] ⚠ **First `src/main.py` run on hardware** — **Blocked by**: the hub, a power cycle before the slot upload, and a clear floor. Largest single risk in the project (KU-M29).
- [ ] **`DETECT_MODE` still defaults to `"anomaly"`**, the front-end refuted on the real carpet — **Blocked by**: the same code edit window. ~12–15 lines; `src/calibration.py` is already written.

## 🟢 Up Next

- [x] ~~test floor~~ — **not happening by decision** ([ADR-0005](./decisions/0005-no-test-suite-verify-on-hardware.md)). Verification is the robot; the `src/` import boundary is checked by `./scripts/check-docs.py`. See [../test_methodology.md](../test_methodology.md)
- [x] ~~`src/` pure logic~~ — **written and PARKED 2026-08-25.** `config.py`, `calibration.py`, `detector.py`, `sweep.py`, `result.py`: all pure Python, host-runnable, no hub imports. Hand-checked working (a 2-note stream with a mid-note dropout counts 2, not 3). **Not being extended** until the research and planning above are done and the professor's answers land — the arena values in `config.py` are placeholders, not measurements
- [x] ~~Buy/mount colour sensors~~ — **done 2026-09-01:** two colour sensors on C/D, matched on the same surface. The real notes/tape/floor separability test is still owed.
- [x] ~~**Go/no-go bench experiment:** pairwise separability of the real sticky-note pack on the real floor~~ — **DONE 2026-09-08, and it passed by ~6×.** `reflection()`: carpet 3–9, blue tape 7–9, yellow 51–73, pink 97+ — **zero overlap, a 43-point gap**, contrast-to-noise 51–57 MAD against the project's own 8.90-MAD arming rule. ⚠ The *chromaticity* route was **refuted** on the same data — yellow invisible, tape a 100 % false positive. [findings/colour-survey-and-first-detection-2026-09-08.md](./findings/colour-survey-and-first-detection-2026-09-08.md)
- [ ] **Measure `SENSOR_SPACING_MM`, the fore-aft sensor offset, a sticky note, and the tape width** — one ruler, sixty seconds, no hub. Deletes four `[UNMEASURED]`s and unblocks the corner-turn radius.
- [ ] **Speed envelope test** — 80–100 dps used against a MEASURED 930 dps ceiling; the 10 ft schedule needs the headroom.
- [x] ~~**Find out which two motors we own**~~ — **answered by the operator 2026-08-27: both Technic Medium Angular 45603** (KU-T3). ±1110 deg/s no-load, 360 counts/rev. Confirm against the casing next time the motors are handled.
- [x] ~~`scripts/setup-host.sh`~~ — **applied 2026-08-27** with `--apply`, before the hub was ever plugged in. ModemManager `inactive`/disabled, udev rule written, `/dev/spike` symlink live. ⚠ Note the honest footnote: `mmcli -L` returned `No modems were found`, so ModemManager had **not** actually grabbed the device — the mitigation is a kept precaution, not a fixed fault. [findings/host-environment.md](./findings/host-environment.md)
- [x] ~~Lock sensor mounting height/angle~~ — **settled 2026-09-08 by the real surface burst.** The middle of the three Technic holes (8 mm per step, ~16 mm working height) is right, and the usable range is now bracketed at **both** ends: at contact every channel pins at 1018–1024 and colour collapses to 33/33/33 (**any channel ≥ 1000 must be discarded, not classified**); at the old ~51 mm mount the signal is dark neutral and useless. ⚠ The **±12.5 mm mount wobble** (single peg, OPERATOR-REPORTED, bench test BM-9 never run) is still the load-bearing uncertainty in the geometry.
- [ ] Confirm the operator's team role (assumed: Programmer) and the other three names/roles → [course/team/roles.md](./course/team/roles.md)
- [ ] Journal entry for 25 AUG (Sprint 1 start) → [course/journal/INDEX.md](./course/journal/INDEX.md)
- [x] ~~Test the CSER `.docx` LibreOffice round-trip~~ — **done, it survives.** All 20 styles and the trim size intact; one sample image + one OLE object lost (replaced anyway). [findings/cser-template-libreoffice-roundtrip.md](./findings/cser-template-libreoffice-roundtrip.md)
- [ ] Start the communications record → [course/team/communications.md](./course/team/communications.md)

## 📋 Backlog

- [x] ~~Fill [hardware/port-map.md](./hardware/port-map.md) once motors/sensors are mounted~~ — done 2026-09-01.
- [ ] Transcribe [hardware/port-map.md](./hardware/port-map.md) into `src/hub_api.py` once code edits are clear.
- [ ] Draft the Intro Report skeleton → [course/report/outline.md](./course/report/outline.md)
- [ ] UMBmark square-path odometry calibration once the robot drives

## ✅ Recently Completed — 2026-08-25

- [x] Read course instructions, journal rubric, CSER report template
- [x] Bootstrap docs tree, 15 project-local directives, scope, roadmap, 3 ADRs
- [x] Schrute Buck budget ledger — balance 56 SB (now [course/budget.md](./course/budget.md))
- [x] `CLAUDE.md`, `MEMORY.md`, README, `.gitignore`
- [x] Host readiness audit → [findings/host-environment.md](./findings/host-environment.md)
- [x] Research: [Linux toolchain](./research/spike-prime-linux-toolchain.md) · [detection & sweep](./research/detection-and-sweep-techniques.md) · [color discrimination](./research/color-discrimination.md)
- [x] Course deliverables, runbooks, hardware record, Sprint 1 plan (delegated, then independently audited — 12 defects found and fixed)
- [x] Design briefing captured; out-of-class-work constraint resolved (not a blocker)
- [x] Coverage time-budget analysis → [findings/coverage-time-budget.md](./findings/coverage-time-budget.md)
- [x] **docs-rag deployed and verified** over this repo's `docs/` → [runbooks/docs-rag.md](./runbooks/docs-rag.md)
- [x] **ResearchHub tunnel working** — pwnstar port 5347 discovered; stale detection and repair tested → [runbooks/researchhub-tunnel.md](./runbooks/researchhub-tunnel.md)
- [x] `scripts/fetch_paper.py` — fetch a paper by URL / DOI / arXiv id, with a grep-able text sidecar
- [x] Docker cleanup — ~6.7 GB reclaimed; volumes untouched; `sam-scraper-*` images held (no source tree found)

---

## Notes

- **Deadlines:** Demo Day 10 SEP · journal + peer review 15 SEP · Intro Report 18 SEP.
- **The journal is 80 points, −5 per missing day** — the cheapest guaranteed score in the project.
- ⚠ **SUPERSEDED 2026-09-08 — "8–23 minutes" was the optimistic reading and the arena is provisionally
  10 FEET.** [COMPUTED at the speeds actually MEASURED] a **one-sensor** sweep at 55 mm/s is
  **75 lanes / 229 m / ~69 min** and fits no plausible demo slot; a **two-sensor** sweep at 300 mm/s is
  **38 lanes / 116 m / ~6.4 min**. Both sensors *and* a higher traverse speed are therefore
  **requirements, not optimisations** — and `src/hub_color.py` reads only one sensor today.
  [findings/coverage-time-budget.md](./findings/coverage-time-budget.md), KU-P1 / KU-D11.
- ✅ **UPDATED 2026-08-25 — "not even three sensors clears a 5-min limit" is REFUTED.** Three sensors at
  10 ft needs **300 mm/s**, which is 58.5% of a Large motor's ceiling with ~19× torque margin — reachable.
  One and two sensors stay refuted (2003 and 516 mm/s). **Conditional on cross-track error holding at
  speed**: if `e` degrades 15→20 mm the requirement jumps to 410 mm/s and it fails again. Measure it —
  [research/speed-envelope.md](./research/speed-envelope.md) §9 bench item 4,
  [trade study §8.5a](./plans/2026-08-25-coverage-strategy-trade-study.md).
- ✅ **CONFIRMED BY MEASUREMENT 2026-09-08: detect with reflected light, not colour ID.** The built-in
  `color()` was trustworthy for blue (149/149 tape samples) and **useless on the notes** — it flapped
  between `WHITE`, `BLACK`, `UNKNOWN` and `MAGENTA` purely with brightness, and carries no
  "saturated / don't trust me" flag. `reflection() >= 30` separates cleanly and is colour-agnostic.
  Classification stays a **layer on top of** presence detection, never a prerequisite for counting.
- **Professor Q5 (decoys) is now a reporting question, not a counting one** — updated 2026-09-08. The
  count rule is brightness and colour-agnostic, so a decoy changes the reported *class*, not the *count*.
  What still caps traverse speed is the **detector**, not the classifier: `v ≤ W·f/N` gives **240 mm/s**
  at N=2 on 24 mm tape at 20 Hz, and **~70 mm/s** if `flush_every` drops to 10.
  ⚠ **The mines are yellow AND pink** (operator, 2026-09-08), the colour **may change on the day**, and
  the standing guarantee is that **mines are never blue** — blue tape and a blue sticky note are
  different things and must not be conflated by any rule we write.
- **On a fresh host, run `./scripts/setup-host.sh` before first hub contact.** On this machine the
  mitigation was applied 2026-08-27 and ModemManager was inactive/disabled; do not resurrect the older
  "ModemManager is active" warning without measuring it again.
