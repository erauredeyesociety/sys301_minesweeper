# Plan — the next session

**Written:** 2026-08-27, at the end of the first hardware session · **Type:** ACTIVE-SPEC
**Supersedes:** [first-hardware-session.md](./first-hardware-session.md), which was executed today.

> **Class time is the scarce resource, and different work needs different things present.** This page
> is grouped by **what each item NEEDS**, not by how interesting it is, so that whatever *is* available
> at the start of the session can be worked on immediately without re-deriving the plan.
>
> Full register: [known-unknowns.md](./known-unknowns.md). This is the *entry point*, not a duplicate.

---

## Read this first — the 60-second state (updated 2026-09-01)

**Closed, do NOT re-investigate:** SPIKE 3 API; deploy over USB proven; firmware provably untouched;
Bluetooth works and our hub is identified by UUID; IMU units measured; **the robot is BUILT and
DRIVES** — forward/back/turn confirmed, port map locked (A=left, B=right, forward `A:-v B:+v`, direct
drive 360 enc-deg/rev); two colour sensors, matched, re-mountable low; docs-rag `/api/ask` works
(needs the ERAU VPN up for skytracker).

**Telemetry architecture decided** ([telemetry-while-driving.md](../research/telemetry-while-driving.md)):
a **slot program** drives motors AND emits telemetry (print → ConsoleNotification) under the live Hub
OS — so "BLE while driving" is solved in principle. Recommendation: **log on hub, retrieve after**, not
live streaming. Deeper workaround research is in flight.

**The top of next session, in order (each unblocks the most for its cost):**

1. **LOWER THE COLOUR SENSORS to ~16 mm**, then run the **real GATE-1 optical burst** — `rgbi()` +
   `reflection()` on matte yellow notes, both real tapes, floor, and air. It unblocks **three of four**
   design areas (colour fusion, boundary detection, matched-sensor coverage) and needs **neither** the
   wheel diameter **nor** the units answer. *The single highest-value bench task.* (Group E)
2. **Measure the wheel diameter with a ruler** (mm) — the one number that turns every encoder degree
   into real distance. Then the calibration drive (below) recovers track width and turn-scale. (Group F)
3. **Ask the professor the units of "10×10"** — still THE architecture blocker; free. (Group A)
4. **The G4 telemetry test** — upload a ~5-line slot program that spins a motor and `print()`s numbered
   lines; watch for `ConsoleNotification`s while it drives (and that it finishes with no listener).
   **Run the companion in the same session:** subscribe with `DeviceNotificationRequest 0x28` (interval
   1000 ms) and watch for `DeviceNotification 0x3C` — a NEW finding says the **firmware pushes IMU,
   encoders and colour with ZERO hub code**, program-independent, which may be a *better* live path than
   `print()` ([ble-while-driving-workarounds-2026-09-01.md](../research/ble-while-driving-workarounds-2026-09-01.md)).
   Converts "BLE while driving" from inferred to proven. Needs a clean-boot window. (Group D)
5. **The calibration drive** (once diameter is known) — a gyro-vs-encoder square/straight run that sets
   track width, the caster turn-scale, and the fault-detection thresholds (slip / lifted). Design in
   [odometry-fusion-and-health-2026-09-01.md](../research/odometry-fusion-and-health-2026-09-01.md). (Group F)

---

## GROUP A — needs only the professor (free, no hardware, no money)

**Do this first every time. It costs one written message and unblocks more than anything else.**
Written communication is also a graded deliverable, so this is not overhead — it *is* the assignment.
Full wording: [questions-for-the-professor.md](./questions-for-the-professor.md).

| Ask | Why it is first | Register |
|---|---|---|
| **The units of "10×10"** | **THE blocker.** Feet vs metres vs tiles is 8 minutes of sweeping vs 23. A wrong guess changes the *design*, not a tuning value | KU-P1 |
| **Autonomous, or may a human drive?** | The relayed answer **contradicts itself** — *"you can't have a human operator"* and *"if you do have a human operator, they cannot be looking at the arena"* in one sentence. We are **assuming autonomy** meanwhile | KU-P0 |
| **Time limit and scoring** | Decides exhaustive vs probabilistic coverage — a different sweep pattern, not a different constant | KU-P2 |
| **Which tape — blue painters or silver duct?** | Both were named. **Silver has no `color` constant and is specular**; blue has a native class. This changes the detection rule | KU-P13 |
| **Decoy colours?** | Decides whether FR-2b classification stays a requirement at all | KU-P5, KU-D6 |
| **Is crossing the boundary a scored failure?** | Decides whether boundary detection is safety-critical or advisory | KU-P14 |

---

## GROUP B — needs a teammate, not the hub

| Ask | Who | Why | Register |
|---|---|---|---|
| **Does the yellow box already hold a colour sensor?** | Builder / Supplier | If yes, the separability gate can run **immediately** and costs 0 SB | **KU-T4** |
| Current store prices; which bricks are available for mounting | Supplier | They are already doing this. Feeds the buy card in [purchasing-strategy.md](./purchasing-strategy.md) | KU-T5 |
| Confirm the two motors are Medium Angular **45603** | Builder | Operator-reported, not yet confirmed by `device.id()`. Confirms itself the moment they are plugged in | KU-T3 |
| Who holds which role, and where team comms happen | Team | Comms record is graded and must be exported | KU-T1, KU-T8 |

---

## GROUP C — needs the hub connected over USB *(≈15 min, all read-only or reversible)*

**Run `./scripts/setup-host.sh` first if this is a fresh boot.** Then, in order:

| # | Do | Closes | Cost |
|---|---|---|---|
| C1 | `python3 probes/capture_baseline.py --to /tmp/now && diff -ru docs/archives/hub-baseline /tmp/now` — **confirm the hub is in its known state before touching anything** | — | 1 min |
| C2 | `python3 probes/ports.py` — what is plugged into A–F | KU-T3 | 1 min |
| C3 | Read the **motor status constant values** (`motor.READY`, `RUNNING`, `STALLED`, `ERROR`, `DISCONNECTED`) — one read-only line. We know an empty port reports `5`; we do not know what `5` *is* | **KU-M15** | 2 min |
| C4 | Re-run the **IMU timing** test isolating the caching anomaly — three calls cost 4× more together than separately, so **no per-call benchmark on this hub means anything until this is closed** | **KU-M14** | 5 min |
| C5 | ⚠ **Does `/flash/main.py` autorun at boot?** Needs the operator's say-so — it changes boot behaviour on shared equipment. **The only item here that gates Demo Day**: it is the difference between a robot that runs and one tethered to a laptop | **KU-M16** | 5 min |
| C6 | Why does `angular_velocity()` read exactly `0,0,0` when stationary? Deadband, or filtering? It explains the suspiciously good drift figure | KU-M19 | 3 min |

---

## GROUP D — needs the hub, and one variable changed at a time *(the retracted claim)*

**This is a controlled experiment, and it exists because a claim was retracted for want of it.**
Do not skip a step or the result means nothing again.

1. Power-cycle. **Touch no serial port.** Press CONNECT. Scan → *expected: appears.*
2. Power-cycle. **Run one probe.** Press CONNECT. Scan.
   - **Appears** → probing is irrelevant, and `probes/` carries no Bluetooth cost.
   - **Silent** → probing suppresses the radio, and that becomes a real operational rule.

Also worth timing while connected: **how long the advertising window stays open** (KU-M17), and
**negotiating a larger MTU** — we are using **23 against an available 509**, a 20× throughput gap that
must be closed before any telemetry design is trusted (KU-M17, [ble-protocol](../findings/ble-protocol-2026-08-27.md)).

---

## GROUP E — needs a COLOUR SENSOR *(does NOT need the robot)*

> **This is GATE 1 of [verification-plan.md](./verification-plan.md), and it can invalidate the whole
> detection design in fifteen minutes.** It needs a sensor, a pack of sticky notes, and a floor.
> **Buy the sensor at the first opportunity** — it is needed under every branch of the decision matrix.

Run [`examples/color_sensor_verbose.py`](../../examples/color_sensor_verbose.py) over each surface in
turn — floor · yellow note · blue tape · silver tape — and record `color()`, `reflection()` and
`rgbi()` together.

**What the answer decides:**

- **The `rgbi()` channel range** is unknown (0–255? 0–1024?) — nothing can be thresholded until it is
  measured (KU-M20).
- **Silver duct tape has no `color` constant** and is *specular*, so its reading may swing wildly with
  angle and height. If it cannot be separated from a bright yellow note, **built-in colour ID is the
  wrong instrument** and raw `rgbi()` ratios are the only route (KU-D2).
- **If the colours do not separate at all, FR-2b classification comes off the table** and the plan
  changes that day (KU-D6).

---

## GROUP F — needs the ROBOT BUILT (motors mounted, wheels on)

Nothing here is possible before the Builder mounts parts. Ordered by what unblocks what —
[bench-measurement-plan.md](./bench-measurement-plan.md) has the timings and the drop order.

| Do | Closes | Note |
|---|---|---|
| `examples/motor_encoder_verbose.py` — **turn the wheels BY HAND**, read encoders | KU-M8, KU-M3 | **Never commands motion**, so it cannot run the robot off a desk. Gives degrees-per-revolution and the sign convention |
| Effective rolling diameter and track width | **KU-M3** | The keystone — every odometry number rests on it |
| **Gyro drift while DRIVING** | **KU-M9** | ⚠ Stationary drift measured ≤0.0033 °/s, but **a filter that suppresses drift at rest can behave completely differently under acceleration.** Heading is *not* solved |
| Cross-track error over one lane | KU-M4 | Sets lane pitch, hence run time |
| Achieved loop rate with everything running | KU-M5 | The IMU costs 1.35 ms; driving and detecting are unmeasured |
| Stopping distance at sweep speed | KU-M13 | With no walls, the robot must stop *before* crossing tape |

---

## GROUP G — needs nothing but a keyboard

| Do | Why | Register |
|---|---|---|
| **CSER `.docx` LibreOffice round-trip** | 15 minutes now, or discover it the night before the report is due | **KU-M12** |
| Confirm the report format with the professor | The instructions name a **due date and nothing else** — no format, no file type. The Word template is an **inference** | — |
| Write `src/main.py`? | **NO — still deliberately unwritten.** It is where every open unknown converges. Writing it before Group A is answered means writing it twice | — |

---

## The residual list — carried forward, still open

These were opened in earlier sessions, are **not** blocked on anything above, and keep being deferred
because something louder is always in front of them. Recorded here so they are not silently dropped:

- **KU-P4** — what "finds" actually means as a deliverable: a count, locations, stopping on each?
- **KU-P6** — how many mines, and whether two can be adjacent or touching the boundary.
- **KU-P7** — the arena floor surface, and whether we may practise on it. **Every reflectance number
  we ever measure is surface-specific**, so measuring on the wrong floor is measuring nothing.
- **KU-P8 / KU-P9** — the scoring rubric and report logistics, in writing.
- **KU-P11** — is there a spare hub if ours fails? Relevant to how much risk any hub-touching step is
  worth.
- **KU-D5 / KU-D9** — exhaustive vs probabilistic coverage, and what the robot does when it cannot
  finish. Both wait on KU-P1 × KU-P2.
- **KU-D7** — gear down or fit smaller wheels for encoder resolution. Waits on KU-M3.
- **KU-M10** — does the robot displace the notes it drives over? Cheap to test once it drives.

---

## What NOT to do next session

- **Do not re-investigate the API generation, the deploy route, or whether Bluetooth works.** All three
  are closed by measurement. Re-deriving them is the most likely way to waste the session.
- **Do not write `src/main.py`** until Group A is answered.
- **Do not build the BLE upload path.** [ADR-0007](../decisions/0007-deploy-by-writing-modules-to-flash-lib.md)
  already deploys over USB and it is proven. BLE upload is not on the critical path.
- **Do not press-and-hold CONNECT while plugging in USB** — that is the DFU gesture.
  [CLAUDE.md](../../CLAUDE.md) blacklist item 2.
