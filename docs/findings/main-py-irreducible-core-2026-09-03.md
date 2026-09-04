# Finding — `src/main.py` written: the irreducible-core competition program

**Date:** 2026-09-03 · **Verified:** STRUCTURE only — imports on the host and `./scripts/check-docs.py`
passes (purity boundary + host-import). **Every hub call site is [UNVERIFIED] — the program has never
run on the robot.** Do not read "written" as "works".

`src/main.py` — deliberately unwritten until now ("where every open unknown converges") — is written as
the **switchboard** the [minimalism contract](../plans/minimalism-contract-2026-09-03.md) specifies: the
smallest state machine that still competes, with every optional feature a knob-toggled bolt-on.

## What it is

```
ARMED → (LEFT/RIGHT tap) → CALIBRATE_FLOOR → READY → (tap + 10 s countdown) → SWEEP → REPORT
```
with `CALIBRATION_FAILED` and `ABORT` as the two honest exits. It auto-starts into **ARMED with motors
HELD**, so a slot that auto-Starts never calibrates on the bench.

- **Detection front-end:** `DETECT_MODE="anomaly"` (default) — `floor_anomaly` learns the floor during
  `CALIBRATE_FLOOR` and flags anything unlike it; **no target sample, no known colour**. Its deviation
  scalar feeds `detector.EdgeCounter`, which counts on the falling edge — so mines added/removed mid-run
  are handled by construction and **completion is coverage, not a tally**.
- **Sweep:** `sweep.SweepPlan` boustrophedon lanes; `result.MissionResult` books each accepted event with
  a beep; the timebox finishes the current lane then stops (`TIMEBOX`); a LEFT/RIGHT press is the soft
  `ABORT`; every terminal state routes through `REPORT`.
- **Motion primitives** (`drive_distance_mm`, `turn_degrees`) are grounded in the **proven** 1 ft square
  (`examples/motor_poc.py`): straight = drive until the encoders advance; **turn = spin until the GYRO
  reads the angle** (gyro-closed, so it does not depend on `TRACK_WIDTH_MM`). Those two behaviours ran on
  hardware; the specific `hub_motors.drive()` / `hub_imu.read_yaw_deg()` call sites here have not.

## Supporting changes

- **`src/hub_runtime.py`** (new) — wraps the hub-only `runloop` so `main.py` reaches the async runtime
  through a `hub_*` module and stays host-importable (ADR-0004; check-docs enforces it).
- **`src/config.py`** — added `DETECT_MODE` ("anomaly" default) and `COUNTDOWN_S` (10).

## Deliberately NOT built (per contract §4 — bolt-ons, each one knob away)

Target calibration (`calibration.py` / `CALIBRATE_TARGET`), colour classification (`classify.py`),
compound-signature detection, boundary stop / line-following, live BLE / host→motor control, a persistent
mine map. `CALIBRATE_FLOOR` returns "not in core" if `DETECT_MODE != "anomaly"`.

## Verification status (say-which-kind-of-verified)

| Layer | Status |
|---|---|
| Imports on host, check-docs green | **CONFIRMED** |
| State machine / accounting logic | reviewed on the host; **not yet exercised** |
| Every `hub_*` call site (drive, read, matrix, buttons, colour) | **[UNVERIFIED] — never run on the robot** |
| Motion primitives' *shape* | grounded in the MEASURED square; the exact wrapper calls are unrun |

## Next

A hardware bring-up run: upload `main.py` as `program.py`, tap to arm, let `CALIBRATE_FLOOR` build a floor
model on the real floor, then a SHORT bounded sweep (small `ARENA_*`, short `RUN_TIMEBOX_S`) with a hand
ready. First goal is that each state transition and each motion primitive behaves; counting a real mine is
the separate detection bench test (still outstanding — [detection-telemetry-build](./detection-telemetry-build-2026-09-03.md)).

**Related:** [minimalism-contract](../plans/minimalism-contract-2026-09-03.md) ·
[square-drive-fusion](./square-drive-fusion-2026-09-03.md) · `src/main.py` · `src/hub_runtime.py`
