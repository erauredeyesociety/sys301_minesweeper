# Finding — Standalone unplugged run + telemetry retrieval: PROVEN

**Date:** 2026-09-03 · **Hub:** ran on **battery, cable unplugged** for the middle of the run ·
**Written to hub:** `program.py` to a slot, a CSV to `/flash/tmp/telemetry` (firmware untouched).
Artefact: `tmp/telemetry/20260903T114912-standalone-0000337854.csv`.

## Two competition-critical capabilities, proven in one test

`examples/standalone_log.py` (a `runloop` slot program, no motors) was uploaded as **`program.py`**
via `hub_programmer/slot_upload.py`, started with `ProgramFlow`, then **the USB cable was unplugged**,
the robot shaken by hand for ~20 s on battery, **the cable replugged**, and the log pulled with
`hub_programmer/download.py`.

Result — `standalone-0000337854.csv`, **412 rows over the full 45 s** (`t_ms` 0 → 44978), i.e. the log
**spans the unplugged window**:

| Channel | Evidence it logged real data while unplugged |
|---|---|
| IMU yaw | swung **117°** (min −829, max +344 ddeg) |
| IMU pitch | swung **85°** |
| Accel | ±1000+ mg on X and Z — the hand-shaking |
| Colour C reflection | 0 → 100 % (surfaces passing the sensor) |
| Battery | 8270–8327 mV across all 412 samples — reading the hub the whole time, on battery |

**So two things are proven at once:**

1. **A slot program runs AUTONOMOUSLY, unplugged, on battery** — the "upload, unplug, let it run"
   competition mechanism works. The program ran its full 45 s with the cable out for ~20 of them.
2. **Record-on-hub → retrieve-after-replug** — the telemetry fallback. Log to `/flash` during the run,
   pull it over USB afterward, SHA-verified. **No Bluetooth required.**

## Why this matters for competition

This is the reliable path, independent of the BLE-connection timing that has been a time-sink. The
robot can run its competition program untethered and we get every logged sample back over the cable
afterward. Live BLE streaming (`DeviceNotification`, MTU 517) remains the *preferred* upgrade for a
remote operator / laptop-side SLAM, but **it is no longer on the critical path** — this fallback
secures the data.

## What this depends on (all now proven today)

- **Slot execution fix**: a program runs only when uploaded as **`program.py`**
  ([sensor-fusion-and-slot-wall-2026-09-03.md](./sensor-fusion-and-slot-wall-2026-09-03.md) UPDATE).
- **On-hub logging + USB retrieval**: `src/hub_telemetry_log.py`, `hub_programmer/download.py`
  ([telemetry-pipeline-validated-2026-09-03.md](./telemetry-pipeline-validated-2026-09-03.md)).

## Still open

- **Stop / reset**: this program ran a fixed 45 s. Competition needs a real stop (autonomous
  mission-complete or an operator button) and reset — being designed in
  `docs/plans/competition-operations-2026-09-03.md` (in progress).
- **Button caution**: pressing the hub's menu buttons during a run can navigate away / stop the
  program (operator observed). The run procedure must say "do not touch the menu buttons mid-run".
- **Motors while unplugged**: this test had no motors (safety). A full run with motors + logging
  unplugged is the next combined test, once a stop mechanism exists so the robot does not drive
  indefinitely.

**Related:** [sensor-fusion-and-slot-wall-2026-09-03.md](./sensor-fusion-and-slot-wall-2026-09-03.md) ·
[telemetry-pipeline-validated-2026-09-03.md](./telemetry-pipeline-validated-2026-09-03.md) ·
`examples/standalone_log.py` · `hub_programmer/slot_upload.py`
