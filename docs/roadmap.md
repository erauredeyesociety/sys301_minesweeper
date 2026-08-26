# SYS 301 Minesweeper — Roadmap v1

> Lean index only: milestone bullets + path refs. Detail lives in `docs/plans/`, never here.
> Boundaries: [scope.md](./scope.md) · Rules: [directives/INDEX.md](./directives/INDEX.md) · Tasks: [todo.md](./todo.md)

**Mode: DEVELOPMENT** (host-side). The briefing is captured but PARTIAL — build to the narrowest reading
and parameterize, so an answer changes a value, not the architecture.
⚠ **Open risk:** if "10×10" means feet, exhaustive single-sensor coverage doesn't fit a demo slot —
[findings/coverage-time-budget.md](./findings/coverage-time-budget.md).

## M0 — Project setup ✓
- [x] Docs tree, directives, scope, roadmap, ADRs, budget ledger — [session_records/2026-08-25_project-initialization.md](./session_records/2026-08-25_project-initialization.md)
- [x] Design briefing captured (verbal, partial) → [scope.md § Mission](./scope.md#mission--partial-verbal-briefing-captured-2026-08-25)
- [x] Out-of-class-work constraint resolved — not a blocker
- [x] Research: Linux toolchain · detection & sweep · color discrimination · motion control & odometry → [research/INDEX.md](./research/INDEX.md)
- [x] SE planning: [known-unknowns](./plans/known-unknowns.md) · [risk register](./plans/risk-register.md) · [coverage trade study](./plans/2026-08-25-coverage-strategy-trade-study.md) · [CONOPS](./plans/conops.md) · [traceability](./plans/requirements-traceability.md) · [verification plan](./plans/verification-plan.md)
- [x] Retrieval: docs-rag + ResearchHub tunnel → [runbooks/INDEX.md](./runbooks/INDEX.md)

## M1 — Ask, and prove the toolchain (Sprint 1, by 27 AUG) 🎯 next
- [ ] **Put the open questions to the professor** → [plans/questions-for-the-professor.md](./plans/questions-for-the-professor.md) — Q1 (units) gates the sweep design
- [ ] Host prep: neutralize ModemManager, serial terminal → `scripts/setup-host.sh`, [findings/host-environment.md](./findings/host-environment.md)
- [ ] Read-only hub identification: Hub OS + API generation. **Must not trigger an update.** → [runbooks/hub-identification.md](./runbooks/hub-identification.md)
- [ ] Walking skeleton: edit on Ubuntu → onto hub → runs standalone → output read back → [plans/2026-08-25-sprint-1-walking-skeleton.md](./plans/2026-08-25-sprint-1-walking-skeleton.md)
- [ ] Port map recorded as single source of truth → [hardware/port-map.md](./hardware/port-map.md)

## M1b — Planning depth (done 2026-08-26)
- [x] Code scaffold: flat `src/` — pure logic + `sensors.py` adapter ([ADR-0004](./decisions/0004-flat-src-supersedes-package-split.md)); no test suite ([ADR-0005](./decisions/0005-no-test-suite-verify-on-hardware.md))
- [x] Bench measurement plan + drivetrain runbook · telemetry plan · hub compute limits + SLAM verdict
- [x] 12 papers on disk → [research/papers/INDEX.md](./research/papers/INDEX.md)
- [ ] **In flight:** sensor-suite architecture · spin-scan localization · sensor mounting geometry
- [ ] **Owed after those land:** unified pattern → sensors → ports → cost matrix

## M2 — Mission capability (Sprint 2, 1–8 SEP)
- [ ] `src/` pure logic + `tests/persistent/` floor — **writable now, no hub needed**
- [ ] Detection: run-start calibration + hysteresis edge counter (reflected light, not color ID)
- [ ] Sweep: boustrophedon lanes + heading hold + per-lane re-square + boundary handling
- [ ] Yellow classification only if the professor confirms decoys exist (FR-2b)
- [ ] Standalone reporting on the hub — count on the light matrix, no laptop
- [ ] **Must-not-break paths** (each gets a floor test): edge-counting state machine · sweep state machine · calibration math · the `src/` import boundary

## M3 — Demo readiness (by 10 SEP)
- [ ] Sensor mounting geometry decided from research **before** the Supplier buys blocks
- [ ] UMBmark square-path odometry calibration on the real floor
- [ ] Timed dry runs; tune from measured data, not guesses
- [ ] **Demo Day 10 SEP** → [runbooks/demo-day.md](./runbooks/demo-day.md)

## M4 — Graded deliverables
- [ ] Daily journal entries, every class day → [course/journal/INDEX.md](./course/journal/INDEX.md)
- [ ] Mid-project check-in survey (1 SEP) · Peer evaluations + journal (15 SEP)
- [ ] Intro Report, CSER 2022 Word template (18 SEP) → [course/report/INDEX.md](./course/report/INDEX.md)
- [ ] Early: does the CSER `.docx` survive a LibreOffice round-trip? Cheap now, expensive on 17 SEP

## Script infrastructure
- [ ] `scripts/setup-host.sh` → `identify-hub.sh` → `deploy.sh` → `read-output.sh` → `pre-demo-check.sh`
- Rules: [directives/automation-first.md](./directives/automation-first.md) — every hub script has a timeout and exits

## FRONTIER (parked)
- [ ] Dead-reckoned mine *mapping* (locations, not just a count) — only if the professor says "finds" means locations
- [x] ~~Project docs-rag / academic-literature retrieval~~ — **done 2026-08-25**, promoted out of FRONTIER: [runbooks/docs-rag.md](./runbooks/docs-rag.md) · [runbooks/researchhub-tunnel.md](./runbooks/researchhub-tunnel.md)

---
*Delivered plans move to `docs/archives/plans/`. Archive this roadmap versioned when it fills.*
