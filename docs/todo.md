# SYS 301 Minesweeper — Todo (SSOT)

> Last updated: 2026-09-03 · **mode: demo-readiness audit; hub is live, robot is built and drives,
> but the no-laptop stored-program path and mission program are not ready to claim yet.**

> **2026-09-01 checkpoint: the robot drives.** Forward/back/turn confirmed, drive convention locked
> ([findings/drive-checkpoint-2026-09-01.md](./findings/drive-checkpoint-2026-09-01.md)). docs-rag
> `/api/ask` now works. Still owed: wheel diameter (ruler), the units of 10×10 (professor),
> real GATE 1 on the actual notes/tape/floor, a measured stored-program run, and the `src/hub_api.py`
> port constants.

## ▶ NEXT SESSION — START HERE

**[plans/next-session.md](./plans/next-session.md)** — the ordered plan, grouped by **what each item
needs** (professor only · teammate only · hub over USB · a colour sensor without the robot · the robot
built · a keyboard), so whatever is present at the start of class can be worked immediately.

**The three real blockers, in order:** ① the **units of "10×10"** — one free question, gates the
architecture · ② the **real GATE-1 optical burst** on actual notes/tape/floor — gates the detection
rule · ③ the **stored-program/standalone path** — `/flash/main.py` does not autorun, and
`slot_upload.py --apply` is still unmeasured on our hub.

**Do not re-investigate** the API generation, the deploy route, or whether Bluetooth works. All three
are closed by measurement — [session_records/2026-08-27](./session_records/2026-08-27_hub-first-contact-usb-and-ble.md).

---

## CURRENT STATE

**Everything buildable without the professor's answers is built.** 15 `src/` modules (8 pure,
7 hub-facing, one per device), the full SE planning layer, Bluetooth answered, telemetry designed and
widened to 21 columns, the analysis layer specced. `src/main.py` is deliberately unwritten — it is where
every open unknown converges.

**The hub has been connected — 2026-08-27, over USB, on `/dev/spike`.** It is SPIKE 3 /
MicroPython 1.24.0, its filesystem is baselined, and **code has been put on it**: `/flash/lib/config.py`
uploaded and imported, with the firmware **proved unchanged** by a baseline re-capture and diff. The IMU
is characterised.

**The robot has since been built and measured — 2026-09-01.** A=left motor, B=right motor, C/D=colour
sensors, E/F empty; forward is `A:-v, B:+v`. The examples that hard-code those ports can demo safely
when their headers are followed, but `src/hub_api.py` still has the hardware port constants set to
`None`, so the reusable `src/` hardware layer will fail loudly until those constants are transcribed.
`/flash/main.py` was confirmed not to autorun; the Hub OS slot upload path is built, dry-run checked,
and still untested with `--apply`.

| What | Where |
|---|---|
| Identity, API generation, filesystem, radio | [findings/hub-first-contact-2026-08-27.md](./findings/hub-first-contact-2026-08-27.md) |
| The one write, the diff, and why the firmware cannot be touched by it | [findings/firmware-integrity-proof.md](./findings/firmware-integrity-proof.md) |
| IMU units, ±180° yaw wrap, read cost, drift | [findings/imu-characterisation-2026-08-27.md](./findings/imu-characterisation-2026-08-27.md) |
| How to put code on the hub | [runbooks/deploy-to-hub.md](./runbooks/deploy-to-hub.md) · [ADR-0007](./decisions/0007-deploy-by-writing-modules-to-flash-lib.md) |
| Built robot port/sign convention | [hardware/port-map.md](./hardware/port-map.md) · [findings/drive-checkpoint-2026-09-01.md](./findings/drive-checkpoint-2026-09-01.md) |
| Colour first-look and two-sensor agreement | [findings/colour-first-look-2026-09-01.md](./findings/colour-first-look-2026-09-01.md) |

⚠ **Carry the remaining unknowns forward accurately.** Closed since first contact: motor status values,
drive sign convention, two colour sensors, `rgbi()` range, and `/flash/main.py` **not** autorunning.
Still open for Demo Day readiness: stored slot upload on real hardware, wheel diameter, real surface
separability, time/arena units, the IMU timing anomaly, BLE advertising timing, and the
`angular_velocity()` zero-reading.
[plans/known-unknowns.md](./plans/known-unknowns.md).

Narrative: [session_records/2026-08-26_code-implementation-bluetooth-and-analysis-planning.md](./session_records/2026-08-26_code-implementation-bluetooth-and-analysis-planning.md)

## NEXT ACTION

**Ask the professor, then close the demo gates.** The hub and basic drive are no longer the blocker; the
*mission numbers*, the stored-program route, and the `src/` port constants are.

1. **Before presenting an autonomous demo:** transcribe the confirmed A/B/C/D port map into
   `src/hub_api.py` (outside this doc-only audit), then run `./scripts/check-docs.py` and the hub import
   check after upload.
2. **Prove the stored-program path on hardware:** run
   `python3 hub_programmer/slot_upload.py <demo>.py --slot N --apply --listen 20` over USB first,
   save the transcript, then test the same stored program
   with the laptop disconnected. `./hub_programmer/slot_upload.py ...` currently fails until its
   executable bit is fixed.
3. **Ask the professor — Q0 FIRST**, then Q1/Q2/Q3/Q5 → [plans/questions-for-the-professor.md](./plans/questions-for-the-professor.md)
   **Q0: must it be autonomous, or may a human drive it?** "Autonomous" appears nowhere in the
   course instructions — we inferred it. A "human may drive" answer removes sweep planning,
   odometry accuracy, heading hold, and the whole coverage-time problem.
4. **Real GATE-1 colour separability go/no-go** — needs the mounted C/D sensors, the real note pack,
   the real tape, and the floor, **not autonomous movement**.
5. **Measure wheel diameter and track width** — turns the confirmed encoder degrees into distance.
6. **Builder: confirm the part numbers printed on the two motors** — `device.id` already says both
   connected motors are the same kind; the casing read closes the paperwork loop.

**Start every session with `./scripts/stack.sh up`.** Nothing starts at boot by design.

---

## 🔴 In Progress

_(nothing — all host-side work is complete)_

## 🟡 Blocked

- [ ] Sweep **parameters** (lane pitch, arena size, run time) — **Blocked by**: professor Q1/Q2. The *code* is not blocked; the numbers are.
- [ ] Buy the distance sensor or not — **Blocked by**: professor Q3 (boundary type). 56 SB remaining.
- [ ] Color classification (FR-2b) — **Blocked by**: professor Q5. If yellow is the only color present, plain reflected-light detection is far more robust and this requirement goes away.
- [x] ~~Hub OS / API generation identification~~ — **CLOSED 2026-08-27: SPIKE 3, MicroPython 1.24.0**, measured over USB → [findings/hub-first-contact-2026-08-27.md](./findings/hub-first-contact-2026-08-27.md)
- [x] ~~`/flash/main.py` autorun?~~ — **CLOSED 2026-09-01: it does not autorun.** Demo Day needs the Hub OS slot route or another measured stored-program path.
- [ ] **Stored slot route** — `hub_programmer/slot_upload.py` is dry-run checked but `--apply` is untested on our hub; no TR-3 claim until a stored program starts with the laptop disconnected.
- [ ] **`src/hub_api.py` port constants** — blocked only by a code edit window. The confirmed port map exists; the constants are still `None`.

## 🟢 Up Next

- [x] ~~test floor~~ — **not happening by decision** ([ADR-0005](./decisions/0005-no-test-suite-verify-on-hardware.md)). Verification is the robot; the `src/` import boundary is checked by `./scripts/check-docs.py`. See [../test_methodology.md](../test_methodology.md)
- [x] ~~`src/` pure logic~~ — **written and PARKED 2026-08-25.** `config.py`, `calibration.py`, `detector.py`, `sweep.py`, `result.py`: all pure Python, host-runnable, no hub imports. Hand-checked working (a 2-note stream with a mid-note dropout counts 2, not 3). **Not being extended** until the research and planning above are done and the professor's answers land — the arena values in `config.py` are placeholders, not measurements
- [x] ~~Buy/mount colour sensors~~ — **done 2026-09-01:** two colour sensors on C/D, matched on the same surface. The real notes/tape/floor separability test is still owed.
- [ ] **Go/no-go bench experiment, before any sweep code:** pairwise separability of the real sticky-note pack on the real floor. If the colours are not separable, classification is off the table and we fall back to presence detection — [research/color-discrimination.md](./research/color-discrimination.md) §8
- [x] ~~**Find out which two motors we own**~~ — **answered by the operator 2026-08-27: both Technic Medium Angular 45603** (KU-T3). ±1110 deg/s no-load, 360 counts/rev. Confirm against the casing next time the motors are handled.
- [x] ~~`scripts/setup-host.sh`~~ — **applied 2026-08-27** with `--apply`, before the hub was ever plugged in. ModemManager `inactive`/disabled, udev rule written, `/dev/spike` symlink live. ⚠ Note the honest footnote: `mmcli -L` returned `No modems were found`, so ModemManager had **not** actually grabbed the device — the mitigation is a kept precaution, not a fixed fault. [findings/host-environment.md](./findings/host-environment.md)
- [ ] Lock sensor mounting height/angle from [research/color-discrimination.md](./research/color-discrimination.md) and [research/detection-and-sweep-techniques.md](./research/detection-and-sweep-techniques.md); the sensors are mounted low, but the real surface burst decides whether that height is good enough.
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
- [x] `inventory.py` budget ledger — balance 56 SB
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
- ⚠ **If "10×10" means feet, exhaustive single-sensor coverage takes 8–23 minutes.** That is a design
  problem, not a tuning problem. Do not tune a sweep before the units are known —
  [findings/coverage-time-budget.md](./findings/coverage-time-budget.md).
- ✅ **UPDATED 2026-08-25 — "not even three sensors clears a 5-min limit" is REFUTED.** Three sensors at
  10 ft needs **300 mm/s**, which is 58.5% of a Large motor's ceiling with ~19× torque margin — reachable.
  One and two sensors stay refuted (2003 and 516 mm/s). **Conditional on cross-track error holding at
  speed**: if `e` degrades 15→20 mm the requirement jumps to 410 mm/s and it fails again. Measure it —
  [research/speed-envelope.md](./research/speed-envelope.md) §9 bench item 4,
  [trade study §8.5a](./plans/2026-08-25-coverage-strategy-trade-study.md).
- **Detect with reflected light, not color ID.** Color mode spatially averages at target edges, which is
  fatal for edge counting. Classification is a **layer on top of** presence detection, never a
  prerequisite for counting — so an answer of "yellow only" costs us nothing we already built.
- **Professor Q5 is a run-time question, not just a robustness one.** Classification needs several pure
  samples inside a note, which caps traverse speed (~160 mm/s at a 20 mm chord vs ~360 mm/s at 30 mm).
  Ask it alongside Q1 and Q2.
- **On a fresh host, run `./scripts/setup-host.sh` before first hub contact.** On this machine the
  mitigation was applied 2026-08-27 and ModemManager was inactive/disabled; do not resurrect the older
  "ModemManager is active" warning without measuring it again.
