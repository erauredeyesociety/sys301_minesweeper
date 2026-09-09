# Finding — Real surfaces measured, the anomaly detector refuted, and the first detection-while-moving

**Date:** 2026-09-08 · **Hub:** connected over USB on `/dev/spike`, then run untethered on battery ·
**Sensors:** colour sensors on ports C and D, mounted at the **middle** of the three Technic holes on
the hub side (one hole step = 8 mm) · **Floor:** the real classroom multicolour carpet ·
**Surfaces:** the real yellow and pink sticky notes and the real blue painters tape.

Raw captures: [runs/surface-survey-2026-09-08.txt](./runs/surface-survey-2026-09-08.txt) ·
drive telemetry `tmp/telemetry/20260908T103023-drivetape-0000077369.csv`.
Tools written today: [`scripts/scan-surface.py`](../../scripts/scan-surface.py) (labelled capture),
[`scripts/analyse-survey.py`](../../scripts/analyse-survey.py) (runs the real `src/` detection code
over the capture), [`examples/drive_to_tape.py`](../../examples/drive_to_tape.py).

> **These are measurements on the mission's own surfaces**, unlike
> [colour-first-look-2026-09-01](./colour-first-look-2026-09-01.md), which used substitutes.
> **GATE 1 IS CLOSED** — § 6b records both mine colours detected and correctly named while the robot
> was moving, untethered on battery.

## 1. Mission facts corrected by the operator today

Recorded because both invalidate earlier design assumptions:

- **The demo-day arena is a COMPLETE CLOSED BOX outlined in blue painters tape on the floor** — a tape
  outline, *not* physical walls. The practice area's tape is deliberately incomplete only so teams do
  not overlap; that is **not** the graded arena. There is a real wall near **one** side of the demo
  area and other objects around it.
- **The floor is multicolour carpet.**
- **Mines are yellow *and* pink** matte sticky notes, the colour **may change on demo day**, and the
  standing guarantee is that **mines are never blue**. ⚠ **Blue tape and a blue sticky note are
  different things** and must not be conflated by any rule we write.

## 2. The sensor's usable range — bracketed, and both ends destroy information

Found by accident and then deliberately swept, holding a note from contact up to ~150 mm:

| Condition | reflection | raw r/g/b | what it reads as |
|---|---|---|---|
| Note touching the sensor | 99 | **1018–1024 (all channels pinned)** | neutral 33.3/33.3/33.4, `WHITE` |
| **Usable range (~16 mm)** | **21–68** | 104–623 | the surface's true chromaticity |
| Sensor ~51 mm up (old mount) | 20–33 | 85–148 | dark neutral — effectively nothing |

**Saturation is the failure at the near end**: the sensor's own LED floods straight back, every
channel pins at the 1024 ceiling, and the ratios that carry colour collapse to exactly 33/33/33. This
is the same mechanism [colour-first-look](./colour-first-look-2026-09-01.md) § 3 measured on glossy
cards — but it happens to **matte paper too**, purely from proximity. **Any channel ≥ 1000 must be
discarded**, not classified.

**Chromaticity is stable everywhere in between.** Yellow held r 35.5 / g 35.0 / b 29.4 while raw
brightness swung 6× (total 289 → 1715). That is chromaticity doing exactly what it is for — dividing
brightness out — and it is why the mount height does not need to be precise for *colour*. It is **not**
true for the brightness rule in § 4, which is height-dependent and is why § 3 is measured at a single
matched height.

## 3. The four mission surfaces, MEASURED

Chromaticity fractions are of `r+g+b`. Reflectance and total are at the **middle-hole mount height**,
matched across surfaces; chromaticity is height-independent per § 2.

| Surface | r% | g% | b% | `reflection()` | total (r+g+b) | built-in `color()` |
|---|---|---|---|---|---|---|
| **Carpet** | 30.5 | 33.6 | 35.8 | **3–9** | 49–107 | `BLACK` / `UNKNOWN` |
| **Blue tape** | 20.7 | 30.5 | **48.5** | **7–9** | 124–135 | **`BLUE`, 149/149 samples** |
| **Yellow note** | 35.5 | 35.0 | 29.4 | **51–73** | 289–1715 | `WHITE`/`BLACK` — unreliable |
| **Pink note** | **46.4** | 23.7 | 29.9 | **97+** | 263–1715 | `UNKNOWN`/`MAGENTA` — unreliable |

Cross-validation, all within one session: carpet measured **72** total at middle-hole against **80**
in an independent hand-held capture; blue tape measured **129** and **130** at two different heights.
Two sensors, two captures each, agreeing.

**The built-in `color()` is trustworthy for blue and useless for the notes.** It returned `BLUE` on
every one of 149 tape samples and never once on carpet, while flapping between `WHITE`, `BLACK`,
`UNKNOWN` and `MAGENTA` on the notes depending only on brightness. It carries no
"saturated / don't trust me" flag. This is the concrete justification for scope FR-2b — our own
classifier over raw `rgbi()` — rather than relying on `color()`.

## 4. ⚠ The chromaticity anomaly detector FAILS on this carpet — measured, and it fails silently

Running the shipped [`src/floor_anomaly.py`](../../src/floor_anomaly.py) and
[`src/detector.py`](../../src/detector.py) **unmodified** over the real captures:

| Surface | median deviation | % clearing the derived threshold | verdict |
|---|---|---|---|
| Carpet (baseline) | 1.35 | 0% | — |
| **Yellow note** | **5.99** | **0%** (port D: 53–66%, a coin flip) | **INVISIBLE** |
| Pink note | 20.37 | 98.8% | detected |
| **Blue tape** | **11.30** | **100%** | **FALSE POSITIVE** |

Derived on-threshold was 7.47; yellow reaches 5.99 and never clears it. **As shipped, on this floor,
the robot would arm cleanly, sweep, miss every yellow mine, and count the boundary tape as mines.**

**The mechanism is quantisation, not hue collision.** Carpet median `r+g+b` = **79 ADC counts**, so one
count is 0.0127 chromaticity units, and the fitted band sigma is **0.00953 — less than a single ADC
count**. The carpet's apparent "colour spread" is pure quantisation noise, and that noise is exactly
what the sigma-normalised rule divides by. Yellow sits 0.0546 from the carpet centroid = **5.73 sigma**
where the rule demands 8.90. This matters for the fix: it is *not* the "note hue matches a floor band"
blind spot `floor_anomaly.py`'s docstring warns about, so raising `K_MAX` or capping band sigma would
**not** have helped — `K_MAX` never overflowed (2–5 bands on real carpet).

## 5. ✅ What survives: plain reflectance

At the matched mount height, on both sensors:

```
carpet     3 - 9      blue tape  7 - 9      yellow  51 - 73      pink  97+
                      gap: 43 reflectance points, ZERO overlap
```

- **A fixed threshold of 30 is dead centre** — 21 points clear above carpet+tape, 21 below yellow.
- **The blue tape sits *inside* the carpet band, so it is ignored for free.** No veto, no blue
  threshold, no extra module. The blue-veto problem dissolves rather than being solved.
- **It is colour-agnostic**, so it survives the mine colour changing on demo day — which is the one
  thing we were told to expect.
- Contrast-to-noise is 51–57 MAD against the project's own 8.90-MAD arming rule — passes by ~6×.
- **`reflection()` == `(100 * i) // 1024` exactly**, 0 mismatches in 3412 rows. So `read_rgb()` already
  carries reflectance and **no new hub call site is needed**.
- Run end-to-end through the real `detector.EdgeCounter` with real samples: **2 of 2 planted notes
  counted, the tape crossing rejected, zero phantom events on 30 s of raw carpet.**

Shadows are asymmetric in our favour: the rule fires on *high* reflectance, so a shadow can only cause
a **miss**, never a phantom. Chromaticity has no such asymmetry.

**The residual risk is a carpet patch as bright as paper**, unmeasured away from the spots sampled.
Two independent defences exist: the event width gate (a bright fleck is `too_narrow`, a bright patch
`too_wide`), and `calibration.calibrate()`, which **refuses to arm** below the contrast rule — a gate
the anomaly path structurally does not have.

## 6. First detection while moving — `drive_to_tape.py`, untethered on battery

Uploaded to a Hub OS slot, USB unplugged, button-armed, run on battery, telemetry logged to `/flash`.

```
#end reason=TAPE_DETECTED rows=53 deg=281 mm=155
```

| What | Measured |
|---|---|
| Outcome | **Stopped on the tape**, not on a cap |
| Straightness | left Δ281° vs right Δ282° — **<0.4% divergence** |
| Heading hold | yaw 84.3°–86.9°, **~2.6° total wander** over the run |
| **Coast after trigger** | 439° → 444° = **~3 mm** |
| Sensor agreement | C 47.2% blue, D 47.8% on the **same tick** |
| Tick rate | **20 Hz sustained** while driving and logging |
| Approach visible | b% 39.6 → 42.9 → 47.2 over three ticks as the tape enters |

**Carpet slip is not the problem we feared** — the robot tracked straight and the ~3 mm coast means
the boundary needs almost no stopping margin. The 20 Hz tick while driving *and* logging *and* reading
both colour sensors is a real measurement, and it is double the 10 Hz the sweep assumed.

## 6b. ✅ GATE 1 CLOSED — both mine colours detected while moving, and correctly named

[`examples/find_note.py`](../../examples/find_note.py), same untethered slot-program route, brightness
threshold 30. **Two runs, two colours, both correct:**

| Run | Result | `reflection()` at stop | Distance driven |
|---|---|---|---|
| 1 | `NOTE_FOUND` **PINK** | 99 | 109 mm |
| 2 | `NOTE_FOUND` **YELLOW** | 62 | 88 mm |

Logs: `tmp/telemetry/20260908T105447-findnote-0000987673.csv` (pink) and `...-0001092589.csv` (yellow).

The yellow approach, tick by tick, showing the threshold crossed cleanly with no ambiguity:

| tick | `reflC` | `reflD` |
|---|---|---|
| carpet | 3–5 | 3–7 |
| seq 24 | 12 | 7 |
| seq 25 | 27 | 18 |
| seq 26 | **46** | 33 |
| seq 27 | **59** | **51** |

**What this closes.** GATE 1 / KU-M22 / KU-M32 — *a real mine, on the real floor, detected while
moving* — open since August. Three things are established at once:

1. **The brightness rule works in motion, not just in a hand-held capture.** Carpet read 3–7 while
   driving, matching the static survey's 3–9 (§ 3). The static measurements predicted the moving
   behaviour, which is the property that makes the demo-day survey protocol worth running.
2. **Colour classification works on real notes.** The red-fraction rule (≥ 0.41 = PINK, below =
   YELLOW, § 3) named both correctly. It is reporting only and never gates the count.
3. **The margin is not marginal.** Both notes cleared the threshold of 30 by 32 and 69 points, from a
   carpet baseline of 3–7.

Motion behaviour matched § 6: ~3 mm coast, ~2.6° of yaw drift, and left/right encoders within ~3%.

⚠ What is **still** owed: detection during an actual **sweep** (turns, multiple lanes, and the two
sensors both crossing one note — the double-counting problem), and `src/main.py` has **still never
run on hardware**.

## 7. ⚠ Operational constraint discovered: REPL tools and slot upload are mutually exclusive

`hub_programmer/run.py` and `probes/` send **Ctrl-C** to obtain a MicroPython REPL. **Ctrl-C kills the
Hub OS**, and the Hub OS is what serves the binary control protocol `slot_upload.py` needs. A slot
upload attempted after any REPL tool aborts at the identity check:

```
[2] identity: DeviceUuidRequest 0x1A
    no DeviceUuidResponse -- cannot prove this is our hub. ABORT (write nothing).
```

That abort is the identity guard working correctly — **nothing was written**. The fix is a **hub
power-cycle** (single press off, single press on) between REPL work and a slot upload.

**On demo day: do all colour surveying first, then power-cycle, then upload the competition program.**

## 8. What this closes and what it opens

**Closes:** the real-surface half of GATE 1 · the sensor's usable range · that the anomaly front-end
is wrong for this arena · that no blue veto is needed · that carpet slip does not break straight-line
driving · that 20 Hz is achievable while driving and logging.

**Opens / still owed:** whether a
carpet patch anywhere in the arena reaches reflectance 30 · the arena **units** (KU-P1, still the
dominant unknown) · `src/main.py` has **still never run on hardware** · wiring the reflectance rule
into `main.py`, which is ~12–15 lines because `src/calibration.py` is already written, pure and
host-runnable, but `main.py` currently early-returns for any `DETECT_MODE` other than `"anomaly"`.
