# SYS 301 Minesweeper — Todo (SSOT)

> Last updated: 2026-08-25
> **mode: DEVELOPMENT (host-side)** — briefing captured but partial. Build the narrowest defensible
> reading, parameterized, so a clarified answer changes a value and not the architecture.

## CURRENT STATE

Planning and research are deep; **nothing physical has happened yet.** The robot is not built, the hub has
never been connected, and the motor and wheel types are unknown. What exists: a full SE planning layer, a
working retrieval stack (docs-rag + ResearchHub), a small pure-Python code scaffold, and 12 papers on disk.
Progress narrative: [session_records/2026-08-26_retrieval-stack-code-scaffold-and-se-planning.md](./session_records/2026-08-26_retrieval-stack-code-scaffold-and-se-planning.md).

**Run `./scripts/stack.sh up` at the start of every session** — nothing starts at boot by design.

---

## 🔴 In Progress

- [ ] Sensor-suite architecture — which sensors, which movement patterns each unlocks *(workflow running)*
- [ ] Spin-scan localization — the operator's challenge to the SLAM verdict *(workflow running)*
- [ ] Sensor mounting geometry — orientation, standoff, parts cost *(workflow running)*
- [ ] **Owed after those land:** the unified matrix — pattern → sensors (count/type/orientation) → ports → SB cost → thoroughness, SLAM and non-SLAM in one table

## 🟡 Blocked

- [ ] Sweep **parameters** (lane pitch, arena size, run time) — **Blocked by**: professor Q1/Q2. The *code* is not blocked; the numbers are.
- [ ] Buy the distance sensor or not — **Blocked by**: professor Q3 (boundary type). 56 SB remaining.
- [ ] Color classification (FR-2b) — **Blocked by**: professor Q5. If yellow is the only color present, plain reflected-light detection is far more robust and this requirement goes away.
- [ ] Hub OS / API generation identification — **Blocked by**: hub not physically connected
- [ ] `src/` — **Blocked by**: the above. `src/` is not blocked.

## 🟢 Up Next

- [ ] **`tests/persistent/` floor** for the mission logic below (edge counter, calibration, sweep state, import boundary) — the code exists, the floor does not yet
- [x] ~~`src/` pure logic~~ — **written and PARKED 2026-08-25.** `config.py`, `calibration.py`, `detector.py`, `sweep.py`, `result.py`: all pure Python, host-runnable, no hub imports. Hand-checked working (a 2-note stream with a mid-note dropout counts 2, not 3). **Not being extended** until the research and planning above are done and the professor's answers land — the arena values in `config.py` are placeholders, not measurements
- [ ] **Go/no-go bench experiment, before any sweep code:** pairwise separability of the real sticky-note pack on the real floor. If the colours are not separable, classification is off the table and we fall back to presence detection — [research/color-discrimination.md](./research/color-discrimination.md) §8
- [ ] **Find out which two motors we own** — Large Angular 45602 or Small Angular 45607. The research recommends the large one for drive; the small one sits at 46–77% of no-load in the classification speed band. Ask the Supplier/Builder
- [ ] `scripts/setup-host.sh` — neutralize ModemManager, install a serial terminal, verify `dialout`. Idempotent. See [findings/host-environment.md](./findings/host-environment.md)
- [ ] Decide sensor mounting height/angle from [research/color-discrimination.md](./research/color-discrimination.md) and [research/detection-and-sweep-techniques.md](./research/detection-and-sweep-techniques.md) **before** the Supplier buys mounting blocks
- [ ] Confirm the operator's team role (assumed: Programmer) and the other three names/roles → [course/team/roles.md](./course/team/roles.md)
- [ ] Journal entry for 25 AUG (Sprint 1 start) → [course/journal/INDEX.md](./course/journal/INDEX.md)
- [ ] Test whether the CSER `.docx` survives a LibreOffice round-trip. Cheap now, expensive on 17 SEP
- [ ] Start the communications record → [course/team/communications.md](./course/team/communications.md)

## 📋 Backlog

- [ ] Fill [hardware/port-map.md](./hardware/port-map.md) once motors/sensors are mounted (operator describes; we record)
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
- **ModemManager is active on this host** and will corrupt the first hub serial session. Clear it before
  the hub is ever plugged in, or the team will misdiagnose it as "Linux doesn't work with LEGO".
