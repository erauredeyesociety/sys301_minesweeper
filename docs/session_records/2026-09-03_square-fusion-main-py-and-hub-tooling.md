# Session Record — 2026-09-03 — Square-drive fusion, `main.py` written, hub tooling

**Mode:** Hardware (attended ground run, then unplugged) + code + infrastructure · **Sprint:** 1 ·
**Hub:** connected, driven, unplugged · **Robot built:** YES — differential drive, rebuilt

Continues [2026-09-01_drive-checkpoint-colour-and-docs-rag.md](./2026-09-01_drive-checkpoint-colour-and-docs-rag.md).

> **The session the pieces converged.** The robot drove a defined 1 ft square untethered and gave us the
> first real motors-vs-IMU fusion data; the deploy toolchain grew up (auto-minify + multi-chunk +
> dependency resolution); and `src/main.py` — deliberately unwritten until now — was written as the
> irreducible-core competition program, reviewed, and hardened. Every hub call site in it is still
> `[UNVERIFIED]`; the next session runs it.

---

## What was done

- **Proved the full control loop with motors, untethered.** `examples/motor_poc.py` uploaded as
  `program.py`, started, USB unplugged, driven on battery, replugged, log retrieved — a defined **1 ft ×
  1 ft square** (4 sides + 4 gyro-closed 90° turns), with LEFT/RIGHT tap to arm and to stop. 238 rows,
  25.8 s, ~9.2 Hz. Also the pure record→unplug→run→replug→retrieve fallback (`standalone_log`).
- **Wrote `src/main.py`** — the irreducible-core switchboard (`ARMED → CALIBRATE_FLOOR → READY →
  countdown → SWEEP → REPORT`, with `CALIBRATION_FAILED`/`ABORT`), `DETECT_MODE="anomaly"` default, every
  optional feature a knob bolt-on. Added `src/hub_runtime.py` (wraps the hub-only `runloop` so main stays
  host-importable inside the ADR-0004 boundary) and config knobs `DETECT_MODE`, `COUNTDOWN_S`, `LOG_EVENTS`.
  **Code-reviewed** (no motor-safety or crash bug) and **5 fixes applied** — the load-bearing one: detector
  width gates now DERIVED from the measured tick rate, so a seam or two merged notes can't count as a mine.
- **Hardened the deploy toolchain.** `slot_upload.py` now **auto-minifies** (python-minifier strips
  comments/docstrings) and **safely multi-chunks** (512 B, CRC-chained) — any-size program uploads, not
  just sub-4 KB. New `hub_programmer/deploy_deps.py` **resolves a program's `src/` imports (AST,
  transitive) and deploys them all to `/flash/lib`**, then uploads the entry.
- **`decode_telemetry.py`** gained an automatic **per-phase** breakdown (forward distance + drift per side,
  gyro + measured track width per turn).
- **Retrieval:** ollama tunnel brought up once the ERAU VPN was connected; ResearchHub confirmed our
  boustrophedon-decomposition + per-lane re-square sweep is the standard approach.

## What was decided / measured

- **Track width = 95 mm (MEASURED)**, replacing the `[ASSUMED]` 176 — from the square's 4 turns
  (`track = 2·arc/θ`, encoder arc vs gyro heading). Effective (folds in caster drag); ~5° gyro under-read
  makes it a slight over-estimate. `config.TRACK_WIDTH_MM` updated.
- **The robot drives STRAIGHT** — per-side heading drift < 1°/ft. The "spins-left" scare was resolved; the
  mirror forward-signs (L=−1, R=+1) are correct for the rebuild. **Wheel Ø 63.5 mm confirmed** (~545° →
  ~300 mm/side).
- **`floor_anomaly` validated on REAL floor data** — 0/238 false-triggers on both sensors while moving.
  Intensity **saturates** on a bright/white floor, confirming the design's use of chromaticity over
  brightness. True-positive (a real mine) is still the outstanding bench test.
- **Anomaly-first core**: `DETECT_MODE="anomaly"` needs no target sample and survives the floor changing
  on the day; `"target"` (calibration.py) stays the optional bolt-on.

## Discovered / corrected

- The 4096-byte fallback chunk is rejected by the hub (no InfoResponse over USB); 512 B works and CRC-chains.
- `main.py` really needs **15** `src/` modules — `calibration`/`classify` arrive transitively via
  `floor_anomaly`, which the AST resolver caught and a hand-typed list missed.
- The turn under-read (~85° vs 90°) was a **logging artifact** (loop broke after the last sample); fixed by
  logging one row at each segment boundary.
- docs-rag `ask` was slow-to-unresponsive this session (cold shared GPU, >175 s/call); search + ResearchHub
  carried retrieval.

## Blocked / next

- **First hardware run of `main.py`** — [first-main-run.md](../runbooks/first-main-run.md): `deploy_deps.py
  src/main.py --apply`, small arena + short timebox, walk each state glyph, hand on the robot. This makes
  every `[UNVERIFIED]` hub call site MEASURED.
- **True-positive detection** — a real mine crossing a real floor (the one detection test hardware still owes).
- **Re-measure track width** with the boundary-log fix to drop the ~5° over-read.
- **Auto-deploy-deps `--apply`** is host-proven but `[UNVERIFIED]` on hardware; the first run confirms it.

**Findings from this session:** [square-drive-fusion](../findings/square-drive-fusion-2026-09-03.md) ·
[standalone-run-and-retrieve](../findings/standalone-run-and-retrieve-2026-09-03.md) ·
[detection-telemetry-build](../findings/detection-telemetry-build-2026-09-03.md) ·
[colour-sensor-mounting-wobble](../findings/colour-sensor-mounting-wobble-2026-09-03.md) ·
[main-py-irreducible-core](../findings/main-py-irreducible-core-2026-09-03.md)
