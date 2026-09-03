# Finding — three competition modules built and host-validated (2026-09-03)

**Date:** 2026-09-03 · **Verified:** COMPUTED on the host (pure modules, no hub) — the numbers below are
from `python3` runs against synthetic streams, not from the robot. Each carries a bench test before it
is trusted on the floor.

Three pieces the competition program needs were written and checked on the host today. All are pure
`src/` modules (no hub imports) except the slot program, and all follow the "reuse, don't re-derive"
rule — each leans on the existing `calibration` / `classify` / `detector` machinery.

## 1. `src/event_filter.py` — significant-event telemetry filter (requirement 4)

Report-by-exception gate: log a sample only when a monitored channel moved past its **deadband**, a
discrete **event** fired (detection / fault / phase change), or a **heartbeat** interval elapsed.
Everything else is dropped and counted.

- **COMPUTED:** a simulated 45 s run at 100 Hz (4500 ticks) with one turn, one detection and one fault
  → **30 rows kept (0.7 %), a 150× reduction.** Every discrete event, the baseline, and the 2 s
  heartbeats survived; only the do-nothing ticks were dropped.
- This is the general continuous-channel gate. It is **complementary to** the mission-integrated
  `significant_event()` predicate specified in
  [competition-operations](../plans/competition-operations-2026-09-03.md) §2, which emits one row per
  discrete *logic* event (state change, accepted/rejected `Event`). event_filter runs **now**, with no
  state machine; the logic-event predicate lands when `src/main.py` exists. Reconcile into one policy then.

## 2. `src/floor_anomaly.py` — floor-relative, colour-agnostic detection (requirement 5)

Learn the floor at run start as ≤6 colour **bands** (robust greedy clustering in chromaticity), then
score each reading by its sigma-distance to the **nearest** band. It is `classify.py`'s sigma-distance
turned inside out, and its scalar feeds `detector.py`'s four-state counter **unchanged** via the
`FloorDeviationCal` shim. Full design + threshold rule:
[floor-relative-colour-anomaly](../research/floor-relative-colour-anomaly-2026-09-03.md).

- **COMPUTED:** a 2-band floor (grey + tan) was learned as exactly 2 bands; threshold derived at
  `on>9.35` in deviation space. A sweep crossing the grey/tan **seam** and then a yellow note gave
  floor deviations ≤ 4.0 and a note deviation of **52.9** → `detector.py` counted **exactly one mine and
  ignored the seam.** This is the "mines might not be yellow / floor might change" requirement met
  without a known target exemplar.
- **Mandatory caveat:** with no target at calibrate time there is no calibrate-time contrast gate, so
  the bench recording (log a floor sweep + a note on each band, check ≥6-SD separation) is **required**,
  not optional. Irreducible blind spot: a note whose chromaticity matches a floor band → deviation ≈ 0
  (a professor question, not a knob).

## 3. `examples/competition_start.py` — the START/STOP operational shell (⚠ untested on hardware)

A `runloop` slot program proving the control loop the operator described: **ARM ("S" on the matrix) →
LEFT/RIGHT tap → 10 s countdown → autonomous phase → DONE**, with a **LEFT/RIGHT tap to STOP** the run
early (the firmware CENTER press remains the independent hard stop). No motors — the autonomous phase
reads IMU + both colour sensors and logs through `event_filter`, so it is safe on a desk.

- Grounded by [hub-menu-and-buttons](../research/hub-menu-and-buttons-2026-09-03.md): a program **cannot
  read CENTER** (`button.POWER` is the firmware's launch/stop), so the in-program tap uses LEFT/RIGHT.
- Independently matches the CONOPS the competition-operations workflow converged on (ARMED wait-state →
  tap → calibrate → READY → tap → countdown → sweep → stop).
- Added an **"s" glyph** to `src/hub_ui.py` for the armed indicator. Running this program also exercises
  `hub_ui.show_glyph / show_digit / button_pressed` on real hardware **for the first time** (their SPIKE 3
  call sites were written but never run) — a bonus verification.
- **Deploy dependency (this IS the real competition deploy):** the slot needs `hub_api`, `hub_ui`,
  `event_filter`, `hub_telemetry_log` in `/flash/lib` alongside `program.py`. Uploading `program.py`
  alone is not enough once it imports `src/` modules.

## Status

Modules 1 and 2 are host-verified and ready. Module 3 is written and syntax-checked but **has not run on
the hub** — the next hardware step. The one competition-critical unknown the operations workflow
flagged ("does a slot keep running after unplug?") is **already answered YES** by the
[standalone-run-and-retrieve](./standalone-run-and-retrieve-2026-09-03.md) milestone.

**Related:** [standalone-run-and-retrieve](./standalone-run-and-retrieve-2026-09-03.md) ·
[colour-sensor-mounting-wobble](./colour-sensor-mounting-wobble-2026-09-03.md) ·
[competition-operations](../plans/competition-operations-2026-09-03.md) ·
`src/event_filter.py` · `src/floor_anomaly.py` · `examples/competition_start.py`
