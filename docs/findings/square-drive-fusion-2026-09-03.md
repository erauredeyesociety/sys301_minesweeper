# Finding — 1 ft square drive: motors-vs-IMU fusion, MEASURED

**Date:** 2026-09-03 · **Verified:** MEASURED on real hardware — `examples/motor_poc.py` uploaded as
`program.py`, run on **battery, USB unplugged**, retrieved after replug.
Artefact: `tmp/telemetry/20260903T123528-motorpoc-0000609431.csv` (238 rows, 25.8 s, SHA-verified).

The robot drove a ~1 ft × 1 ft square — four straight sides with a gyro-closed 90° turn at each
corner — logging motors (encoders/velocity/status), IMU (yaw + 3-axis accel), and both colour sensors
(reflection + RGBI) at ~9 Hz, tagged by phase (`side0-3`, `turn0-3`, `stop0-3`).
`scripts/decode_telemetry.py` now produces the per-segment breakdown automatically.

## Four results

| # | Result | Evidence |
|---|---|---|
| 1 | **The robot drives STRAIGHT** — the earlier "spins-left" is resolved | Heading drift per side: **−0.3, −0.1, −0.4, +0.6°** per foot. The mirror forward-signs (L=−1, R=+1, `src/hub_api.py`) are correct for this rebuild. |
| 2 | **Wheel diameter 63.5 mm confirmed** | ~545° of wheel per side → **294–305 mm** (target 304.8 = 1 ft), consistent across all four sides. |
| 3 | **Track width MEASURED = 95 mm** (was `[ASSUMED]` 176) | All four turns gave 94–95 mm via `track = 2·arc/θ` (encoder arc vs gyro heading). `config.TRACK_WIDTH_MM` updated to 95. |
| 4 | **Turns read ~85°, not 90°** — a LOGGING artifact | The turn loop broke *after* the last logged sample, so the true 90° was never written. Fixed (see below). This makes the 95 mm a slight over-estimate (true ≤ 95). |

Sample rate **9.2 Hz** (100 ms tick + ~9 ms sensor-read overhead). Gravity on Z = 997 mg → the hub
sat flat/upright the whole run. The whole-run encoder-span asymmetry (A 2836°, B 1819°) is **not a
fault**: with the mirror signs, A decreases monotonically (span = total travel) while B oscillates
(forward on sides, back on turns), so its span under-reads total travel. The per-segment view is the
honest one.

## Improvements made from this run (answering "improve the format / frequency?")

- **Format — log at segment boundaries.** `examples/motor_poc.py` now takes one extra `sample()` right
  after each straight/turn loop exits, so the segment's TRUE end state (the real 90°, the real side
  length) is recorded. This directly removes the ~5° turn under-read and will tighten the next track-width
  measurement. Cheap, and worth carrying into any move-by-target code.
- **Decoder — automatic phase breakdown.** `scripts/decode_telemetry.py` gained `phase_report()`: when a
  log has `side*/turn*` phases it prints forward-distance + heading-drift per side and gyro + measured
  track width per turn, then the mean track width. No change to non-phase logs.
- **Frequency — 9.2 Hz is adequate here, watch it for detection.** At a 150 mm/s sweep that is ~16 mm
  between samples; a ~76 mm note is ~5 samples wide — enough to detect, tight for locating. The limiter
  is the ~9 ms/tick of sensor reads, not the sleep. For a detection sweep, either raise the rate by
  logging fewer channels per tick or accept 16 mm spacing and lean on the width gate. **Not changed
  yet** — settle it against a real detection run, not in the abstract.

## Still open

- **Re-measure track width** with the boundary-log fix (KU) to drop the ~5° over-read.
- The `finally`/`#end` trailer line is filtered by the decoder's `#` skip — fine, but means the very
  last `reason=complete` isn't parsed; the phase rows already prove completion.

**Related:** [standalone-run-and-retrieve](./standalone-run-and-retrieve-2026-09-03.md) ·
[colour-sensor-mounting-wobble](./colour-sensor-mounting-wobble-2026-09-03.md) ·
`examples/motor_poc.py` · `scripts/decode_telemetry.py` · `src/config.py`
