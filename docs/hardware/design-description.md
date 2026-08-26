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
| **RESULTING** | `<<< describe what was built >>>` |

**Still open:** which motors we own (Large 45602 / Medium 45603 / Small 45607 — [KU-T3](../plans/known-unknowns.md)),
and which wheels. Both are read off the parts, not derived. Numbers that depend on them live in
[`src/config.py`](../../src/config.py) and change with one edit.

## Colour sensor — the target detector

| | |
|---|---|
| **PROPOSED** | Mounted **flat, facing straight down**, near the front of the robot and **close to the drive axle**. About **16 mm above the floor** (LEGO's optimal reading distance). Not tilted. |
| **RESULTING** | `<<< describe: how far above the floor, how far forward, rigid or sprung >>>` |

**Why close to the axle:** distance from the drive axle couples the robot's pitch into the sensor's
standoff *and* costs heading error on turns — two independent reasons for the same placement
([sensor-mounting-geometry.md](../research/sensor-mounting-geometry.md)).

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
