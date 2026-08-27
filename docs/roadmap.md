# SYS 301 Minesweeper — Roadmap v1

> Lean index only: milestone bullets + path refs. Detail lives in `docs/plans/`, never here.
> Boundaries: [scope.md](./scope.md) · Rules: [directives/INDEX.md](./directives/INDEX.md) · Tasks: [todo.md](./todo.md)

**Mode: HARDWARE.** The hub has been connected, characterised and programmed —
[session_records/2026-08-27_hub-first-contact-usb-and-ble.md](./session_records/2026-08-27_hub-first-contact-usb-and-ble.md).
**Next session starts at [plans/next-session.md](./plans/next-session.md).**

**Mode was: DEVELOPMENT** (host-side). The briefing is captured but PARTIAL — build to the narrowest reading
and parameterize, so an answer changes a value, not the architecture.
⚠ **Open risk:** if "10×10" means feet, exhaustive single-sensor coverage doesn't fit a demo slot —
[findings/coverage-time-budget.md](./findings/coverage-time-budget.md).

## M1 — Hub bring-up ✓ (2026-08-27)
- [x] Host prepared before first contact (ModemManager, udev, `/dev/spike`) — `./scripts/setup-host.sh --apply`
- [x] **API generation MEASURED: SPIKE 3** — no `spike` module, so SPIKE 2 material is inapplicable — [findings/hub-first-contact-2026-08-27.md](./findings/hub-first-contact-2026-08-27.md)
- [x] **Deploy route PROVEN**, no LEGO app / compiler / Windows — [ADR-0007](./decisions/0007-deploy-by-writing-modules-to-flash-lib.md) · [runbooks/deploy-to-hub.md](./runbooks/deploy-to-hub.md)
- [x] **Firmware proved untouched** by baseline capture → diff — [findings/firmware-integrity-proof.md](./findings/firmware-integrity-proof.md)
- [x] **Bluetooth connected, hub identified by UUID across USB *and* BLE** — [findings/ble-protocol-2026-08-27.md](./findings/ble-protocol-2026-08-27.md)
- [x] IMU characterised: milli-g, decidegrees, ±180° wrap, 1.35 ms tick — [findings/imu-characterisation-2026-08-27.md](./findings/imu-characterisation-2026-08-27.md)
- [ ] **Does `/flash/main.py` autorun?** — the one open item here that gates Demo Day (KU-M16)

## M0 — Project setup ✓
- [x] Docs tree, directives, scope, roadmap, ADRs, budget ledger — [session_records/2026-08-25_project-initialization.md](./session_records/2026-08-25_project-initialization.md)
- [x] Design briefing captured (verbal, partial) → [scope.md § Mission](./scope.md#mission--partial-verbal-briefing-captured-2026-08-25)
- [x] Out-of-class-work constraint resolved — not a blocker
- [x] Research: Linux toolchain · detection & sweep · color discrimination · motion control & odometry → [research/INDEX.md](./research/INDEX.md)
- [x] SE planning: [known-unknowns](./plans/known-unknowns.md) · [risk register](./plans/risk-register.md) · [coverage trade study](./plans/2026-08-25-coverage-strategy-trade-study.md) · [CONOPS](./plans/conops.md) · [traceability](./plans/requirements-traceability.md) · [verification plan](./plans/verification-plan.md)
- [x] Retrieval: docs-rag + ResearchHub tunnel → [runbooks/INDEX.md](./runbooks/INDEX.md)

## M1 — Ask, and prove the toolchain (Sprint 1, by 27 AUG) 🎯 next
- [ ] **Put the open questions to the professor** → [plans/questions-for-the-professor.md](./plans/questions-for-the-professor.md) — Q1 (units) gates the sweep design
- [x] Host prep: neutralize ModemManager, serial terminal → `scripts/setup-host.sh --apply` run 2026-08-27; ModemManager `inactive`/disabled, `/dev/spike` symlink live → [findings/host-environment.md](./findings/host-environment.md)
- [x] Read-only hub identification: Hub OS + API generation — **done 2026-08-27, SPIKE 3 / MicroPython 1.24.0, no update prompt seen** → [findings/hub-first-contact-2026-08-27.md](./findings/hub-first-contact-2026-08-27.md)
- [ ] **Walking skeleton — HALF DONE, do not tick it whole.** ✅ edit on Ubuntu → onto the hub (`/flash/lib/config.py`, on-hub SHA-256 verified) → **imports on the hub** (`OK config`) → output read back over USB. ❌ **"runs standalone" is unproven**: whether `/flash/main.py` autoruns at boot is untested (**KU-M16**), and that is the half Demo Day needs → [runbooks/deploy-to-hub.md](./runbooks/deploy-to-hub.md) · [ADR-0007](./decisions/0007-deploy-by-writing-modules-to-flash-lib.md) · [plans/2026-08-25-sprint-1-walking-skeleton.md](./plans/2026-08-25-sprint-1-walking-skeleton.md)
- [ ] Port map recorded as single source of truth — all six ports **confirmed EMPTY** 2026-08-27 (`device.id()` → `OSError`, `motor.status()` → `5`); nothing to assign until parts are mounted → [hardware/port-map.md](./hardware/port-map.md)

## M1b — Planning depth (done 2026-08-26)
- [x] Code scaffold: flat `src/` — pure logic + the `hub_*.py` modules adapter ([ADR-0004](./decisions/0004-flat-src-supersedes-package-split.md)); no test suite ([ADR-0005](./decisions/0005-no-test-suite-verify-on-hardware.md))
- [x] Bench measurement plan + drivetrain runbook · telemetry plan · hub compute limits + SLAM verdict
- [x] 12 papers on disk → [research/papers/INDEX.md](./research/papers/INDEX.md)
- [x] Sensor suite architecture · spin-scan localization · sensor mounting geometry · Bluetooth (control + telemetry) · analysis theory (detection + motion) · mission algorithm spec
- [x] Unified matrix → [plans/sensor-decision-matrix.md](./plans/sensor-decision-matrix.md)
- [x] `scripts/setup-host.sh` · `find_spike_prime.py` · `scripts/check-docs.py`

## M2 — Mission capability (Sprint 2, 1–8 SEP)
- [x] `src/` pure logic written — config · calibration · detector · sweep · result · odometry · sensors. **No test floor** ([ADR-0005](./decisions/0005-no-test-suite-verify-on-hardware.md)); the import boundary is guarded by `./scripts/check-docs.py`
- [ ] Detection: run-start calibration + hysteresis edge counter (reflected light, not color ID)
- [ ] Sweep: boustrophedon lanes + heading hold + per-lane re-square + boundary handling
- [ ] Yellow classification only if the professor confirms decoys exist (FR-2b)
- [ ] Standalone reporting on the hub — count on the light matrix, no laptop
- [ ] **Must-not-break paths** — verified on the robot, not by tests ([ADR-0005](./decisions/0005-no-test-suite-verify-on-hardware.md)): edge-counting state machine · sweep state machine · calibration math. The `src/` import boundary is the one exception, checked by `./scripts/check-docs.py`

## M3 — Demo readiness (by 10 SEP)
- [ ] Sensor mounting geometry decided from research **before** the Supplier buys blocks
- [ ] UMBmark square-path odometry calibration on the real floor
- [ ] Timed dry runs; tune from measured data, not guesses
- [ ] **Demo Day 10 SEP** → [runbooks/demo-day.md](./runbooks/demo-day.md)

## M4 — Graded deliverables
- [ ] Daily journal entries, every class day → [course/journal/INDEX.md](./course/journal/INDEX.md)
- [ ] Mid-project check-in survey (1 SEP) · Peer evaluations + journal (15 SEP)
- [ ] Intro Report, CSER 2022 Word template (18 SEP) → [course/report/INDEX.md](./course/report/INDEX.md)
- [x] ~~CSER `.docx` LibreOffice round-trip~~ — **it survives**: 20 styles + trim size intact, one sample image/OLE lost. [findings/cser-template-libreoffice-roundtrip.md](./findings/cser-template-libreoffice-roundtrip.md)

## Script infrastructure
- [ ] `scripts/setup-host.sh` → `identify-hub.sh` → `deploy.sh` → `read-output.sh` → `pre-demo-check.sh`
- Rules: [directives/automation-first.md](./directives/automation-first.md) — every hub script has a timeout and exits

## FRONTIER (parked)
- [ ] Dead-reckoned mine *mapping* (locations, not just a count) — only if the professor says "finds" means locations
- [x] ~~Project docs-rag / academic-literature retrieval~~ — **done 2026-08-25**, promoted out of FRONTIER: [runbooks/docs-rag.md](./runbooks/docs-rag.md) · [runbooks/researchhub-tunnel.md](./runbooks/researchhub-tunnel.md)

---
*Delivered plans move to `docs/archives/plans/`. Archive this roadmap versioned when it fills.*
