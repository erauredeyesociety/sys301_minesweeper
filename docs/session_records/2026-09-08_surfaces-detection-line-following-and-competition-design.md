# Session record — 2026-09-08 · real surfaces, GATE 1 closed, line following, and the competition design

**Hub:** connected over USB for most of the day, then unplugged for the design work.
**Demo Day:** 2026-09-10 — two days out. **Intro Report:** 2026-09-18.

The longest and most productive session so far, and the most instructive because of how much of it was
**wrong first**. Failures are recorded here deliberately: several of the day's best results came from
a measurement contradicting a confident inference, and the Intro Report needs that narrative.

---

## 1. Mission facts corrected by the operator

| Fact | Status |
|---|---|
| Demo-day arena is a **closed box of blue tape on the floor** — tape only, no walls | The practice area's incomplete tape is *not* the graded arena |
| **10 foot square** (3048 mm) | The competition **expectation**, "not set in stone". KU-P1 is **PROVISIONAL**, not closed |
| Floor is **multicolour carpet** | — |
| Mines are **yellow AND pink** matte sticky notes; colour **may change**; **never blue** | ⚠ Blue *tape* and a blue *sticky note* are different things |
| Mines may be **double-wide or joined**; different mines always have **carpet between them** | The segmentation invariant |
| There may be **blue tape inside** the field | Turns out not to matter — see § 4 |

## 2. The surface survey — four surfaces, measured on the mission's own materials

Tools written today: [`scripts/scan-surface.py`](../../scripts/scan-surface.py) (labelled capture),
[`scripts/analyse-survey.py`](../../scripts/analyse-survey.py) (runs the *real* `src/` detection code
over the capture). Raw: [`runs/surface-survey-2026-09-08.txt`](../findings/runs/surface-survey-2026-09-08.txt).

| Surface | r% | g% | b% | `reflection()` | total | built-in `color()` |
|---|---|---|---|---|---|---|
| Carpet | 30.5 | 33.6 | 35.8 | **3–9** | 49–107 | BLACK / UNKNOWN |
| Blue tape | 20.7 | 30.5 | **48.5** | **7–9** | 124–135 | **BLUE, 149/149** |
| Yellow note | 35.5 | 35.0 | 29.4 | **51–73** | 289–1715 | WHITE/BLACK — unreliable |
| Pink note | **46.4** | 23.7 | 29.9 | **97+** | 263–1715 | UNKNOWN/MAGENTA — unreliable |

**Two failed capture attempts bracketed the sensor's usable range**, and were more valuable than the
successes: a note **touching** the sensor pins all channels at 1018–1024 and the ratios collapse to
33/33/33; at the old ~51 mm mount the carpet read as effectively nothing. Both ends destroy
information; the usable band is around LEGO's stated 16 mm.

Full write-up: [colour-survey-and-first-detection-2026-09-08.md](../findings/colour-survey-and-first-detection-2026-09-08.md).

## 3. ⚠ The shipped detector was refuted, and the mechanism was not what anyone predicted

Running `src/floor_anomaly.py` and `src/detector.py` **unmodified** over the real captures:

| Surface | median deviation | % clearing threshold | verdict |
|---|---|---|---|
| **Yellow note** | 5.99 | **0%** | **INVISIBLE** |
| Pink note | 20.37 | 98.8% | detected |
| **Blue tape** | 11.30 | **100%** | **FALSE POSITIVE** |

**As shipped, on this floor, the robot would arm cleanly, sweep, miss every yellow mine, and count
the boundary tape as mines.**

The mechanism is **quantisation, not hue collision**: carpet median `r+g+b` is only **79 ADC counts**,
so the fitted band sigma is **smaller than one ADC count**. The carpet's apparent "colour spread" is
quantisation noise, and that noise is exactly what the sigma-normalised rule divides by. This matters
because it means raising `K_MAX` would *not* have helped — `K_MAX` never overflowed.

## 4. ✅ What replaced it: plain reflectance

```
carpet 3-9   blue tape 7-9   yellow 51-73   pink 97+     gap: 43 points, ZERO overlap
```

- **Fixed threshold 30**, dead centre — 21 points clear each way.
- **Blue tape sits inside the carpet band**, so the mine rule cannot see tape at all. The feared
  blue-veto problem **dissolved** rather than being solved, and interior tape costs the count nothing.
- **Colour-agnostic**, so it survives the mine colour changing on the day.
- `reflection() == (100*i)//1024` exactly (0 mismatches in 3412 rows) — no new hub call needed.

## 5. ✅ GATE 1 CLOSED — a real mine, on the real floor, while moving

[`examples/find_note.py`](../../examples/find_note.py), untethered on battery, **twice**:

```
#end reason=NOTE_FOUND colour=PINK   refl=99  rows=37 deg=198 mm=109
#end reason=NOTE_FOUND colour=YELLOW refl=62  rows=32 deg=160 mm=88
```

Both colours correctly classified by the red-fraction rule. Carpet read 3–7 *while driving*, matching
the static survey's 3–9 — so the hand-held measurements predicted the moving behaviour, which is what
makes the demo-day survey protocol worth running. **Open since August; closes KU-M22 / KU-M32.**

Earlier the same day, [`examples/drive_to_tape.py`](../../examples/drive_to_tape.py) stopped on the
tape correctly: straightness left 281° vs right 282°, yaw wander ~2.6°, **coast ~3 mm**, both sensors
triggering on the *same tick*.

## 6. Line following — four runs, three failures, each one diagnostic

| Run | Result | Cause |
|---|---|---|
| v1 | `TAPE_ENDED`, `corrections=0` | "2 s with no tape = line lost" — but **while straddling, no tape is the NORMAL state**, so it ended every run after 2 s |
| v2 | Circled for the whole 40 s run | **Inverted heading-hold sign** → positive feedback. Wheels pinned at 2.55:1; the saturated-correction prediction is (80+30)/(80−30) = 2.2 |
| v3 | `corners=0` | Corner rule required *both* sensors simultaneously; measured, a real corner holds **one** sensor for 5–10 ticks and the other joins 600 ms later |
| v4 | Corners detected, turned the wrong way, then pivoted off the tape | Two separate causes — see § 7 |

Lesson recorded: [guard-every-feedback-loop.md](../lessons_learned/guard-every-feedback-loop.md) —
*a feedback loop ships with a divergence guard, or it does not ship.*

## 7. The corner turn — diagnosed exactly, on the last day

**The pivot is the arc formula with the sensor-ahead distance silently set to zero.** It assumes the
sensors sit on the wheel axis. Master equation, derived and numerically verified:

```
miss e = X_v*sin(theta) - R*(1 - cos(theta))        ->        R* = X_v * cot(theta/2)
```

At 90° that is simply **R\* = X_v**; a pivot (R = 0) misses the new leg by one whole sensor-ahead
distance. At 180° the term vanishes (`e = -2R`), so **R = 0 is provably correct for the dead-end
U-turn** — the operator's instinct there was a theorem, not a heuristic.

⚠ **And the corner-side rule had been fitted against noise.** `on_tape()` rejected only `tot <= 0`, so
a reading of `0,1,3` returns a blue fraction of 0.75 and votes *true*. Two runs in the corpus contain
5- and 6-tick "sustained" runs that are **entirely** sub-40 noise, long enough to command a 90° turn
on sensor dropout. `MIN_CHANNEL_SUM = 40` now excludes noise and neither real class (tape 124–135,
carpet 49–107).

## 8. Decisions made

| Decision | Basis |
|---|---|
| Detection is **reflectance ≥ 30**, not chromaticity | Measured refutation, § 3–4 |
| **No blue veto** — tape is invisible to the mine rule | Measured, § 4 |
| Corner turn is an **arc at R = 65 mm**; dead-end U-turn stays a pivot | Derived, § 7 |
| `src/hub_drive.py` **owns direction** — one module, two constants, evidence beside each | Three direction bugs in one day |
| Speed is capped by **sampling, not motors** | § 9 |
| Coverage will be **partial and reported honestly** alongside the count | § 9 |

## 9. Speed, sampling, and the coverage problem

- **The motors were never the limit.** `motor.run()` takes deg/s and delivers it — commanded 150,
  measured **150.02** by differencing `relative_position`. The slow speeds are a copy-pasted
  bench-safety constant in nine files.
- **`motor.velocity()` is NOT deg/s** — it is ~percent of rated speed. The API record said "int deg/s",
  read on a *stationary* hub returning 0. **Corrected in place.**
- **Real tick rates:** median 54 ms but **mean 75 ms = 13.3 Hz**, p95 116 ms. Cause isolated — the CSV
  flush costs a deterministic **+51 ms on one tick in ten**. `src/main.py` uses `TICK_MS = 100`.
- **Worst-case chord is 36.48 mm, not 76** — a 76 mm note crossed at 45° at the worst lane offset.
- Consequence: at 300 mm/s and 9.18 Hz a crossing yields **1.12 samples** — the robot steps over the
  note. `config.max_safe_speed_mms()` now encodes this.
- ⚠ **Full coverage of a 10 ft arena is unreachable.** A border lap alone is ~92% of a 300 s slot;
  sweeping yields roughly 4–24% coverage. This is a planning fact, not a tuning problem.

## 10. Bugs found in shipped `src/` code, all fixed

1. **`counter.finish()` was never called from `main.py`** — a mine still under the sensor at a lane end
   stayed open, merged with the next lane's first mine, and both were rejected as `too_wide`. **Silent
   double mine loss.**
2. **`detector.events` was unbounded**, appended for every event including rejected ones, inside the
   mission loop — a plausible `MemoryError` on a heap under 252 KiB. Now a 64-entry ring; verified
   over 500 crossings that the **count is unaffected**.
3. **`SECOND_COLOR_PORT` is declared and never read** anywhere in `src/` — the mission code has a
   one-sensor swath despite two sensors mounted. **Still open** (KU-D11).
4. The divergence guard **could never fire** — `hold_ref` re-datums on every tape sighting, resetting
   the saturation count. Now trips on the runaway *signature* instead.
5. The `CORNER` log note was **clobbered** by `TURN_START` before any row was written — which is why
   **no CSV in the corpus contains a CORNER row**.

## 11. Operational discoveries

- ⚠ **REPL tools kill the Hub OS.** `run.py`, `probes/` and `download.py` send Ctrl-C, which stops the
  program serving the binary control protocol, so `slot_upload.py` then aborts at its identity check
  (correctly, writing nothing). **A power cycle is required between REPL work and a slot upload.** A
  Ctrl-D soft reset was properly tested with protocol verification and 25 s of retries and does **not**
  work. `scan-surface.py` was re-plumbed through the slot/console path and no longer kills it.
- **The CENTER button stops a running program** — and a running program *blocks a new one from
  starting*, which silently caused several failed uploads.
- ⚠ **The module name `config` is shadowed on the hub.** `import config` in an on-hub program resolves
  to something in the LEGO firmware, not `/flash/lib/config.py`, and the program dies at import —
  *even though the upload hash-verifies*. `hub_drive.py` now mirrors the constants with a host-side
  drift assertion instead.

## 12. Tooling built today

| Tool | Purpose |
|---|---|
| [`scripts/scan-surface.py`](../../scripts/scan-surface.py) | Labelled surface capture; also the demo-day site survey |
| [`scripts/analyse-survey.py`](../../scripts/analyse-survey.py) | Runs the real `src/` detection code over a capture |
| [`scripts/analyse-run.py`](../../scripts/analyse-run.py) + `runlog.py`, `compare-runs.py` | Run analysis, modelled on the operator's drone flight-analysis scripts |
| [`scripts/sensor-sides.py`](../../scripts/sensor-sides.py) | Which colour sensor is physically left/right |
| [`scripts/stop-program.py`](../../scripts/stop-program.py), `restore-hub-os.py` | Hub control ergonomics |
| [`src/hub_drive.py`](../../src/hub_drive.py) | The skid-steer module that owns direction and geometry |
| [`examples/calibrate_directions.py`](../../examples/calibrate_directions.py) | Settles forward/back/left/right **by watching**, not inference |

## 13. What is next

**Blocking, in order:**

1. **`src/main.py` has still never run on hardware** — the dominant risk with the demo two days out.
2. Fix the **one-sensor swath** (`SECOND_COLOR_PORT`) before touching lane pitch.
3. Measure **`SENSOR_SPACING_MM`** — a 30-second ruler reading. *Not* blocking the corner arc (R = 65
   survives the whole plausible range) but it centres the guess.
4. Settle **bias vs noise** in the heading wander. With n = 4 the 95% CI spans −7.8° to +6.8° over
   10 ft — a *fatal* bias is still consistent with the data. Needs ~5 full-length runs.
5. Decide: does the demo **trace the border**, or sweep the config rectangle? A lap costs ~92% of the slot.

**Design docs produced today**, all ready to implement against:
[corner-arc-turns-and-recovery](../plans/corner-arc-turns-and-recovery-2026-09-08.md) ·
[border-polygon-and-microslam](../plans/border-polygon-and-microslam-2026-09-08.md) ·
[speed-and-heading-precision](../plans/speed-and-heading-precision-2026-09-08.md) ·
[operator briefing](../plans/2026-09-08-operator-briefing-corner-turns-to-competition.md).

Known-unknowns were consolidated from ~50 live rows to **27**, with a closed ledger of 32.
