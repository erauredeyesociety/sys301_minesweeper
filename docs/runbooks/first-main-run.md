# Runbook — first hardware run of `src/main.py`

**Goal:** exercise the competition program's state machine and motion primitives on the robot for the
first time, SAFELY and bounded. This is NOT a competition run — it is the run where every `[UNVERIFIED]`
hub call site in `main.py` gets its first reality check. Expect to find and fix things.

**Operator:** Programmer (plug/unplug + code) with the Builder ready to lift the robot. Hand on the robot.

## 0. Before you touch the hub

- **All of `main.py`'s dependencies must be in `/flash/lib`.** `program.py` alone is not enough — `main.py`
  pulls in 15 local modules (`config, odometry, sweep, floor_anomaly, detector, result, calibration,
  classify, hub_runtime, hub_ui, hub_motors, hub_imu, hub_color, hub_api, hub_telemetry_log`; note
  `calibration`/`classify` arrive transitively via `floor_anomaly`). **Automated path (preferred):**
  one command resolves the transitive imports and deploys each dependency, then uploads + starts the entry —

  ```bash
  ./hub_programmer/deploy_deps.py src/main.py            # DRY RUN — prints the deploy plan
  ./hub_programmer/deploy_deps.py src/main.py --apply    # deploy every dep, then upload+start main.py
  ```

  The resolver is host-proven; each module is still SHA-verified on the hub by `upload.py`. See
  [deploy-with-deps.md](./deploy-with-deps.md). ⚠ Its `--apply` orchestration is **[UNVERIFIED]** on
  hardware — this is the run that makes it MEASURED. **Manual fallback:** deploy each module by hand with
  `upload.py`, then `slot_upload.py src/main.py --apply` ([deploy-to-hub.md](./deploy-to-hub.md)).
- **Set a SMALL, bounded arena in `config.py` for this run, then restore afterwards:**
  | Knob | First-run value | Why |
  |---|---|---|
  | `ARENA_WIDTH_MM` | `400` | ~2–3 short lanes, not a full sweep |
  | `ARENA_LENGTH_MM` | `400` | ~40 cm sides, like the proven square |
  | `RUN_TIMEBOX_S` | `60` | hard stop in a minute no matter what |
  | `TRAVERSE_SPEED_MMS` | `150` | the speed the square ran at |
  | `DETECT_MODE` | `"anomaly"` | the core path; no target sample needed |

  Deploy the edited `config.py` with the rest of `src/`.

## 1. Deploy and start

1. **Power-cycle** the hub (clean Hub OS; a prior REPL/abort can leave it unresponsive to slot upload).
2. Deploy `src/` → `/flash/lib`, then `./hub_programmer/slot_upload.py src/main.py --apply` (auto-minifies +
   multi-chunks + starts). The matrix should show **"S"** (ARMED, motors held).
3. Place the robot on the floor, **~1 m clear each way**, a plain surface under the colour sensors.
4. **Unplug USB** (optional — it also runs tethered; unplug to prove untethered).

## 2. Walk the state machine (what each glyph means)

| Matrix | State | What should happen | If it doesn't |
|---|---|---|---|
| **S** | ARMED | motors held, waiting | — |
| tap LEFT/RIGHT | → | leaves ARMED | — |
| **centre dot** | CALIBRATE_FLOOR | robot **creeps forward ~3 s** sampling the floor | if it lurches/spins, STOP (tap) — a motion-primitive sign issue |
| **X** | CALIBRATION_FAILED | floor too noisy/busy, or rate too low | correct outcome — re-run on a plainer surface |
| **square outline** | READY | motors stopped, waiting | — |
| tap LEFT/RIGHT | → | ~10 s countdown (blinks/digits, beeps) | — |
| **arrow** | SWEEP | lanes: drive, gyro-closed 90° turns, beep per detection | tap LEFT/RIGHT = soft ABORT → REPORT |
| digits + glyph pages | REPORT | cycles the count pages forever | operator stops the program |

**STOP:** a LEFT/RIGHT tap is the soft abort (→ REPORT, partial count kept). The hub's **CENTRE button is
the firmware hard stop** of last resort. Keep a hand on the robot the whole time.

## 3. After the run

1. Replug USB, `python3 hub_programmer/download.py --all`, then `scripts/decode_telemetry.py` on the newest
   log. The event log (`mission-*.csv`, if `LOG_EVENTS=True`) holds pose + each detection.
2. **Restore** `config.py`'s arena/timebox to their real values (or a fresh copy) so the small-arena test
   settings don't ship.

## What this run is really testing (all `[UNVERIFIED]` until now)

- `hub_motors.drive()` / `stop_motors()` / `read_motor_degrees()` call sites (never run — only the raw
  `motor.run` equivalent was, in the square).
- `hub_ui.show_glyph/show_digit/beep/button_pressed`, `hub_imu.read_yaw_deg/reset_yaw`, `hub_color.read_rgb`.
- The floor-anomaly front-end building a model on a *real* floor and the detector counting a *real* crossing
  (the outstanding true-positive test — [detection-telemetry-build](../findings/detection-telemetry-build-2026-09-03.md)).
- That `main.py` and all its `src/` deps import and run together from `/flash/lib`.

**Related:** [deploy-to-hub.md](./deploy-to-hub.md) · [identify-hardware-after-rebuild.md](./identify-hardware-after-rebuild.md) ·
[main-py-irreducible-core](../findings/main-py-irreducible-core-2026-09-03.md) ·
[minimalism-contract](../plans/minimalism-contract-2026-09-03.md)
