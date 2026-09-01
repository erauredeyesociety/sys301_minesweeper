# Session Record — 2026-09-01 — Drive checkpoint, colour first-look, docs-rag working

**Mode:** Hardware (intermittent USB) + infrastructure · **Sprint:** 1 · **Hub:** connected and
unplugged several times as the robot had to move · **Robot built:** YES — differential drive assembled

Continues [2026-08-27_hub-first-contact-usb-and-ble.md](./2026-08-27_hub-first-contact-usb-and-ble.md).

> **The session the robot first drove on command, and the docs-rag finally worked.** Also the session
> that taught us how scarce and interrupted USB access to a *moving* robot really is.

---

## The headline results

| Result | Where |
|---|---|
| **Drive stack works** — forward/back/turn-right/turn-left, confirmed by eye + symmetric encoders | [findings/drive-checkpoint-2026-09-01.md](../findings/drive-checkpoint-2026-09-01.md) |
| **Robot is built**: differential drive, 2 motors (A=left, B=right), rear unidirectional caster, 2 colour sensors | [hardware/design-description.md](../hardware/design-description.md) |
| **Port map CONFIRMED**: A/B motors (id 48), C/D colour (id 61), E/F empty; forward = `A:-v B:+v` | [hardware/port-map.md](../hardware/port-map.md) |
| **docs-rag `/api/ask` WORKS** for the first time — `qwen3:14b` on skytracker via the VPN | [CLAUDE.md](../../CLAUDE.md), [decisions/0006](../decisions/0006-docs-rag-llm-is-operator-gated.md) |
| **Colour method characterised** on substitute surfaces; `rgbi()` is 0–1024; gloss saturates | [findings/colour-first-look-2026-09-01.md](../findings/colour-first-look-2026-09-01.md) |
| **Why the BLE button "does nothing"**: a probe's Ctrl-C kills the Hub OS, which owns the button+radio | [lessons_learned/dont-interrupt-the-hub-os-if-you-want-bluetooth.md](../lessons_learned/dont-interrupt-the-hub-os-if-you-want-bluetooth.md) |

---

## What was done

### The drive checkpoint (the win)

`examples/drive_moves.py` drove all four basic moves at 250 dps while the operator held the robot.
Encoder deltas were clean and symmetric (forward −366/+366, backward +367/−367, turns ±217), and the
operator **confirmed by eye** that each labelled move matched reality. This locks, as MEASURED:

- **A = left wheel, B = right wheel**, motors mounted mirrored, robot-forward = `A:-v, B:+v`.
- **Direct drive → 1 wheel rev = 360 encoder degrees.** Distance = π × wheel diameter (diameter still
  to be measured with a ruler — the one remaining number for real distances).
- **Speed control is the velocity argument** (`motor.run(port, dps)`), ±930 dps measured ceiling.
- A ~9° ramp loss on a short move (commanded 375°, got 366°).

The one UNVERIFIED note that guarded `src/hub_motors.py` is now CONFIRMED.

### docs-rag brought fully online

`./scripts/sky-ollama.sh up` forwarded skytracker's ollama; `docs-rag/.env` was pointed at it
(`OLLAMA_BASE_URL=http://172.17.0.1:11435`, `LLM_MODEL=qwen3:14b`). `/api/ask` now answers correctly
with citations (~80 s warm; the first call is slower loading 9.3 GB into GPU). This closes the
long-standing PARTIAL status. **The ADR named `qwen3.5:9b`, which is not installed on skytracker;
`qwen3:14b` (already present, above the 5B floor) was used with the operator's approval — nothing was
pulled.** `scripts/stack.sh` was corrected: the ask-probe timeout 90→300 s (a cold 14B load was being
misreported as broken), and the local-ollama line no longer lies when docs-rag points remote.

### Hardware harvested and characterised

New read-only probes (`probes/`): `whoami`, `identify_hub`, `filesystem`, `bluetooth_state`,
`hub_os_state`, `ports`, `devices`, `capture_baseline`, `import_check`, `encoders`, `usb_protocol`,
`harvest`, plus shared `_hubio` and `_cobs`. `harvest.py` grabs everything in one USB window
(control-protocol probe first, before any Ctrl-C). Measured: two colour sensors (not one), 930 dps
motor ceiling (not the assumed 660), `rgbi()` 0–1024, motor status constants (DISCONNECTED=5,
CANCELLED=CONTINUE=3), colour constants (YELLOW=7…), full API surface
([findings/hub-api-surface-2026-09-01.md](../findings/hub-api-surface-2026-09-01.md)).

### Colour first-look

`examples/color_live.py` on substitute surfaces (name cards, paper, khaki — no yellow, no tape).
**Red separates trivially** (55 % red fraction). **Shiny cards saturate green+blue at 1024 and become
indistinguishable** — the specular / blue-on-blue risk, measured. `reflection()` marks presence not
colour. The two sensors read a shared surface identically (matched pair confirmed). Not the mission
surfaces — the real GATE 1 (matte yellow + real tape, low mount) is still owed.

### Deploy + run, and the untethered path

`hub_programmer/upload.py` (module → `/flash/lib`, SHA-256 verified) and `run.py` (RAM via paste mode)
both proven. `slot_upload.py` built — the full slot-upload protocol (identity gate → ClearSlot →
StartFileUpload with CRC32 → chunked TransferChunk → ProgramFlow start → ConsoleNotification), USB +
BLE, dry-run by default, **untested**. `/flash/main.py` confirmed **not** to autorun.

### Scope additions

- **Our hub's identity of record** in [scope.md](../scope.md): device_uuid, MAC, name — because the
  team may contract services to other groups whose hubs differ, so identity is always verified.
- **[plans/competitive-interference.md](../plans/competitive-interference.md)**: interfering with other
  teams is authorized (operator relay); documented as scope, **not built** on operator direction, and
  gated on written confirmation from the professor.

---

## Decisions

| Decision | Record |
|---|---|
| docs-rag LLM is `qwen3:14b` remote (ADR named a model not installed; used what is there) | [decisions/0006](../decisions/0006-docs-rag-llm-is-operator-gated.md) |
| Drive convention A=left/B=right, forward `A:-v B:+v`, direct drive 360 deg/rev | [hardware/port-map.md](../hardware/port-map.md) |
| Competitive interference: authorized, documented, offense deferred pending written rules | [plans/competitive-interference.md](../plans/competitive-interference.md) |

---

## Corrections to my own claims

- **"USB probing kills Bluetooth" — RE-instated after being wrongly retracted.** The retraction rested
  on a false "it should self-recover if left alone" assumption; a Ctrl-C'd Hub OS needs a restart.
  Confirmed by the control protocol answering pre-Ctrl-C and going silent post-Ctrl-C.
- **"Blue-on-blue is a worry" → measured as real** (gloss saturation), but the mines are matte so it
  may not bite the actual mission surface — must re-test.
- **Colour readings were <1 cm, not 51 mm** — corrected the finding after the operator flagged it.

---

## What went wrong, and how it was recovered — a process lesson

**Five workflows were run concurrently and two stalled** (the classroom-transcript documentation and
the two-sensor coverage recompute), producing no output — most likely because every agent was routed
through the ~80 s docs-rag `/api/ask` and, under contention, some hung. **Recovered:** the classroom
transcript was written by hand ([classroom-transcript-2026-09-01.md](../findings/classroom-transcript-2026-09-01.md)),
and the coverage material was folded into the detection research. **Lesson, applied for the rest of the
session:** no more than two concurrent workflows, and docs-rag is one *optional* call with a web
fallback, never a blocking gate on every agent. The four later workflows all completed.

---

## Research completed offline (four workflows, all landed)

With the hub unplugged, four verify-gated research workflows ran to completion:

| Doc | The load-bearing result |
|---|---|
| [research/telemetry-while-driving.md](../research/telemetry-while-driving.md) | A **slot program drives motors AND streams telemetry** under the live Hub OS (`print()` → ConsoleNotification). Recommendation: **log on hub, retrieve over USB** — live streaming is infeasible at the current link. Corrected our own "MEASURED MTU 23" over-claim (it is a bleak default). |
| [research/ble-while-driving-workarounds-2026-09-01.md](../research/ble-while-driving-workarounds-2026-09-01.md) | **`DeviceNotification` (subscribe `0x28`) — the firmware pushes IMU/encoders/colour with ZERO hub code**, sidestepping the `print()` concurrency question. A better live path; a complement, not a swap. Payload-shrinking buys ~5× live rate but not full-rate. |
| [research/odometry-fusion-and-health-2026-09-01.md](../research/odometry-fusion-and-health-2026-09-01.md) | The two fault detectors (`turn_slip`, `disturbance`) as small pure functions, variable-rate turns, and auto-tuning — **all fault thresholds are wheel-diameter-independent**, set by one calibration drive. |
| [research/detection-odometry-coverage-2026-09-01.md](../research/detection-odometry-coverage-2026-09-01.md) | Colour saturation as a one-way specularity signal; odometry with the dragging caster; coverage drift swings **~170×** with the units of "10×10". |

**All three design workflows converge on one next action: lower the sensors to ~16 mm and run the real
GATE-1 optical burst** — it unblocks three of four design areas and needs neither wheel diameter nor
the units answer.

## A latent bug the research caught — forward integrated to zero

The fusion workflow, checking against the drive-checkpoint data, found that `odometry.update()` summed
the **raw** equal-and-opposite encoders (`(−366 + 366)/2 = 0`), so **a forward move integrated to zero
distance**; and `hub_motors.drive()` applied no sign, so `drive(50,50)` would have *spun* the robot.
**Fixed:** the mirror convention is now `hub_api.LEFT/RIGHT_MOTOR_FORWARD_SIGN` (measured), applied in
`hub_motors`, `odometry.py` left pure. Verified on the host — forward now integrates to +178.9 mm.
Recorded in [findings/drive-checkpoint-2026-09-01.md](../findings/drive-checkpoint-2026-09-01.md). The
import boundary passed it; only real directions off the floor exposed it —
[ADR-0005](../decisions/0005-no-test-suite-verify-on-hardware.md) exactly.

---

## Blockers — reprioritised

1. **Lower the sensors to ~16 mm + real GATE-1 optical burst** — now the single highest-value bench
   task; unblocks three of four design areas and needs neither wheel diameter nor the units answer.
2. **Wheel diameter (mm)** — one ruler read; turns every encoder degree into real distance.
3. **The units of "10×10"** — still THE architecture blocker; one free question to the professor.
4. **The G4 telemetry test** — proves BLE-while-driving (`print()` path + the `DeviceNotification`
   firmware-push companion) in one clean-boot window. *No longer a research question — a design answer
   needing one confirmation.*

---

## What's next

[plans/next-session.md](../plans/next-session.md) leads with the reprioritised top-5 and
[known-unknowns.md](../plans/known-unknowns.md) carries the new KU-M21–M28. Four research workflows
completed offline (above); their `src/` recommendations are **captured, not yet applied** — a
review-and-apply pass for a hardware session, except the one confirmed odometry bug, which was fixed.
`src/main.py` remains deliberately unwritten until the units answer lands.
