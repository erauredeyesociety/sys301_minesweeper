# Design description — proposed, then resulting

**Deliberately simple.** Plain sentences, not a parts list. *"The colour sensor is mounted flat, facing
down, near the front."* That is enough to write code against and enough to describe in the report.

Two columns because they diverge, and the difference is worth keeping: **PROPOSED** is what we intend,
**RESULTING** is what the Builder actually made. When they differ, the *why* is usually the most
interesting sentence in the whole build.

> **We are not doing a brick inventory** (operator, 2026-08-26). Reasoning from LEGO part numbers we may
> not own got complicated fast and bought little. Describing the design in sentences is the right
> altitude for this project.

---

## Drive

| | |
|---|---|
| **PROPOSED** | Two motors, two wheels, differential drive — one motor per wheel, steering by driving them at different speeds. Decided by the team 2026-08-25. |
| **RESULTING (2026-09-01)** | **Differential drive, confirmed built.** One wheel driven on the **left**, one on the **right**, each by its own motor. A **single unidirectional roller-ball caster at the back** carries the third point of contact — so the robot is a two-wheel differential drive with a passive rear caster, steered entirely by the speed difference between left and right. Motors read on ports **A and B** (`device.id` 48). |

**Motors confirmed:** both `device_id` **48** with `motor.info` `max_speed` **930 deg/s** (measured
2026-09-01), so [KU-T3](../plans/known-unknowns.md) is closed at the hub. **Wheel diameter and track
width are still UNMEASURED** — they are read off the built robot, not derived, and every distance/turn
number in [`src/config.py`](../../src/config.py) depends on them. The rear caster is *unidirectional*,
which matters: it rolls freely forward/back but resists sideways scrub, so a pivot turn drags it and
that shows up as a heading-vs-encoder discrepancy to calibrate out, not a bug.

## Colour sensor — the target detector

| | |
|---|---|
| **PROPOSED** | Mounted **flat, facing straight down**, near the front of the robot and **close to the drive axle**. About **16 mm above the floor** (LEGO's optimal reading distance). Not tilted. |
| **RESULTING (2026-09-01)** | **TWO colour sensors, not one** — ports **C and D** (`device.id` 61), facing down. **UPDATE, later 2026-09-01:** the wheel geometry lets them mount **UNDERNEATH the robot, near the ground** — no longer the ~51 mm front-corner position. This puts them close to the 16 mm optimum and **lets colour and motors run in the same session.** Exact standoff still to be read off the built robot. |

⚠ **Height RESOLVED 2026-09-01** by mounting the sensors underneath the robot (see RESULTING above). The earlier front-corner position was ~51 mm — ~3× too high. LEGO's optimal reading distance is **16 mm** (2 studs), with a
~12 mm illuminated spot there. At ~51 mm the spot spreads and dims and ambient light contaminates it, so
`color()` will be unreliable; `reflection()`/`rgbi()` may still give a weak signal. **Recommend lowering
both sensors to ~16 mm.** The exact usable range is one bench height-sweep (rides with GATE 1).

**Two sensors, one on each front corner, is a real capability, not just redundancy:** they straddle the
robot's width, so together they cover a wider swath per pass (fewer lanes, less run time — see the
coverage recomputation) *and* their left/right difference gives an edge/heading signal a single centred
sensor cannot. The spacing between them is a Designer choice that is not yet fixed.

**Why keep them near the axle:** distance from the drive axle couples the robot's pitch into the
sensor's standoff *and* costs heading error on turns ([sensor-mounting-geometry.md](../research/sensor-mounting-geometry.md)).
Front-corner mounting trades some of that for width and forward lookahead — a deliberate tension to
resolve with the Designer.

## Distance sensor — boundary detection, IF we buy one

| | |
|---|---|
| **PROPOSED** | Facing **forward and level — not tilted.** Mounted **high enough** that the floor does not echo back inside the trigger range. |
| **RESULTING** | `<<< only if bought — gated on professor Q3 >>>` |

**Do not tilt it.** A few degrees is not buildable from LEGO beams: rigid double-pinned angles only land
on Pythagorean triples (36.87°, 28.07°, 22.62°, 16.26°). **Raise it instead.** The floor echoes at slant
range `1.74 × height`, so height must satisfy `h > 0.57 × trigger threshold` or the floor spoofs the wall.

## Anything that needs to spin

| | |
|---|---|
| **PROPOSED** | **Mount it on a motor.** The motor's encoder gives the angle for free, and height comes from wherever the mount ends up. |
| **RESULTING** | `<<< only if built >>>` |

A spinning sensor costs **one of the 4 free ports** (2 of 6 are already motors), so it competes directly
with a third colour sensor. Assessment: [spin-scan-localization.md](../research/spin-scan-localization.md)
— the mechanism works, but the ultrasonic beam gives only ~5 useful directions per turn.

## Hub

| | |
|---|---|
| **PROPOSED** | Wherever it balances, with the **5×5 light matrix visible to the operator** — it is the only readout during an untethered run, and the Builder reads it from across the room. |
| **RESULTING** | `<<< describe: where it sits, which way the matrix faces >>>` |

---

## The numbers that must be measured, not described

Prose is enough for the design. These are not — they scale every calculation and must come off the real
robot ([bench-measurement-plan.md](../plans/bench-measurement-plan.md)):

| What | Why it matters | Where it lands |
|---|---|---|
| **Effective rolling wheel diameter** | Converts motor degrees to millimetres. The *loaded* value, not the moulded number | `config.WHEEL_DIAMETER_MM` |
| **Track width** | Every turn. Derived from a spin that actually closes, not a ruler | `config.TRACK_WIDTH_MM` |
| **Sensor height above floor** | Sets detection quality and the sampling geometry | build record + calibration |
| **Which motors, which wheels** | Speed ceiling and torque headroom | [KU-T3](../plans/known-unknowns.md) |

## Changes

Append a line when the design changes. **A change nobody wrote down becomes a bug someone else debugs.**

| Date | What changed | Why |
|---|---|---|
| 2026-08-25 | Differential drive, 2 motors + 2 wheels | Team decision |
| | | |

---

Detailed as-built facts go in [build-record.md](./build-record.md); port assignments live **only** in
[port-map.md](./port-map.md).

---

## Open risk — a curled or bent sticky note

Raised by the operator 2026-09-01: **what if a sticky note is bent upward** so its face is not flat on
the floor? A downward colour sensor expects a flat surface at ~16 mm. A note curled up presents a
near-vertical or tilted face, so the sensor may see the floor *under* the raised edge, a weak/wrong
reflection off the angled face, or the note only as a brief narrow event instead of a full-width one.

**Not being solved now — captured so it is not forgotten.** It is a detection-robustness problem, filed
as a known-unknown, and it interacts with the event-width discriminator (a curled note is narrower in
the sensor's view than a flat one). Revisit after GATE 1 establishes what a *flat* note even reads as —
there is no point hardening against a curled note before we can reliably see a flat one.
