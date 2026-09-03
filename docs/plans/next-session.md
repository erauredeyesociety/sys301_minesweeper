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
4. **The G4 telemetry test** — from a clean Hub OS state, prove the slot route first, then run the
   motor+`print()` BLE test and the `DeviceNotification` companion in the order in Group D. Expected:
   REPL-run motor code kills BLE/CONNECT; slot-run motor code keeps Hub OS alive, so `print()` should
   surface as `ConsoleNotification 0x21` and the firmware should push hardware snapshots as
   `DeviceNotification 0x3C` after `DeviceNotificationRequest 0x28`. Passing G4/G4b/G5 converts
   "BLE while driving" from inferred to measured. (Group D)
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

## GROUP D — needs the hub, and a live Hub OS

**Known lesson:** REPL probes and `hub_programmer/run.py` send `Ctrl-C`; after that, the Hub OS services
that own CONNECT/FD02 are down until restart. If Bluetooth matters, power-cycle first and use only the
LEGO control protocol or BLE in the window that follows.

Before G4, measure the live radio state without changing anything else:

1. Power-cycle. **Touch no serial port.** Press CONNECT once. Scan → *expected: appears*; time how long
   the advertising window stays open (KU-M17).
2. Connect one BLE client and verify the UUID. Expected CONNECT light: **solid blue**. While solid blue,
   a second scanner may see nothing; record that as "already connected" unless the light says otherwise.
3. Read the real MTU / usable write size and log it with the transcript. The old "MTU 23" was a bleak
   reporting default, not a measured wire value.

### Clean G4/G5 window — motors + print telemetry + possible control

Run this as one controlled window. **No REPL tools in the middle:** no `hub_programmer/run.py`, no
`hub_programmer/upload.py`, no `_hubio` probe, no raw serial terminal. Those send `Ctrl-C` and invalidate
the BLE question by interrupting the Hub OS.

1. **Safety/setup.** Robot on blocks or held; wheels spin free. Close every USB/BLE client
   (`fuser -v /dev/spike` should be empty). Power-cycle with the centre button, wait for the normal Hub OS
   menu/matrix. Do not press-and-hold CONNECT.
2. **Advertising/connection state.** Press CONNECT once only if needed. Expected light states from our
   measurement: flashing blue = advertising, solid blue = connected. Once solid blue, a second scan may see
   nothing; treat that as "already connected" before treating it as "Bluetooth off."
3. **DeviceNotification baseline.** With no slot program running, connect over BLE, verify the UUID, send
   `DeviceNotificationRequest(1000)`, and log raw `0x3C` frames defensively. Then send interval `0` and
   disconnect. If no `0x3C` arrives here, do not combine it with motor motion yet.
4. **Slot route proof over USB, not BLE.** Run
   `python3 hub_programmer/slot_upload.py examples/g4_spin_and_print.py --slot N --apply --listen 25`
   with a throwaway slot `N`. This is the first hardware proof of `ProgramFlowRequest`/slot execution; it
   should show Ack responses and USB-side `ConsoleNotification 0x21`. If this fails, stop.
5. **G4 over BLE.** Power-cycle again. Connect a BLE listener/capture client, verify UUID, and watch for
   `ConsoleNotification 0x21`; ideally the same client also sends `DeviceNotificationRequest(1000)`. Start
   the stored G4 program through the Hub OS slot route, not `run.py`. Expected: motor A moves, numbered G4
   lines arrive over BLE, and `0x3C` motor position advances. If using today's `slot_upload.py`, remember it
   can listen for console but does **not** request `DeviceNotification` yet.
6. **G4b no-listener.** Power-cycle. Start the same stored slot with **no BLE client and no USB console
   listener during the run**; best is the hub slot UI, acceptable is a start command that disconnects
   immediately. Time it by stopwatch: the current G4 program should stop the motor after about 20 s. A
   stall here means `print()` is not safe as a live heartbeat.
7. **G5 both motors only after G4/G4b pass.** Use the same clean Hub OS pattern with a bounded two-motor
   slot program, still on blocks/held. Expected: both encoder fields advance in `DeviceNotification`, BLE
   console line count stays >=99%, and motor stop timing does not stretch.

**Never fix a failed step by enabling Bluetooth in hub code.** User `bluetooth.BLE()`/`gap_advertise()` can
displace the Hub-OS-owned FD02 service. Restart the Hub OS with the normal power button and re-run the
single failed step.

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
