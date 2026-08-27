# Session Record — 2026-08-27 — First contact with the hub, over USB and Bluetooth

**Mode:** Hardware · **Sprint:** 1 · **Hub connected:** **YES — for the first time in this project**
· **Robot built:** no · **Ports A–F:** all EMPTY throughout

Continues [2026-08-26_code-implementation-bluetooth-and-analysis-planning.md](./2026-08-26_code-implementation-bluetooth-and-analysis-planning.md).

> **The session that turned this project from a paper design into a measured one.** Two days of
> `[ASSUMED]` values met the actual hardware. Most survived. Several did not, and the ones that did not
> are the valuable part of this record.

---

## The headline results

| Question | Answer | Where |
|---|---|---|
| Which API generation? | **SPIKE 3**, measured. No `spike` module — **every SPIKE 2 tutorial is inapplicable** | [findings/hub-first-contact](../findings/hub-first-contact-2026-08-27.md) |
| Can we get code on without the LEGO app? | **Yes, proven.** 13,262 B in 3.6 s, hub-computed SHA-256 verified, imported `OK` | [ADR-0007](../decisions/0007-deploy-by-writing-modules-to-flash-lib.md) |
| Do we need a compiler / Windows VM? | **No.** The hub runs MicroPython *source*. No GCC, no `mpy-cross`, no VM | [runbooks/deploy-to-hub](../runbooks/deploy-to-hub.md) |
| Is the firmware untouched? | **Proven** by baseline capture → upload → re-capture → diff | [findings/firmware-integrity-proof](../findings/firmware-integrity-proof.md) |
| Does Bluetooth work from Linux? | **Yes.** Connected with raw `bleak`, LEGO's COBS framing validated both directions | [findings/ble-protocol](../findings/ble-protocol-2026-08-27.md) |
| Which hub is ours? | **Proven** — device UUID matched across USB *and* BLE | same |
| IMU units? | acceleration **milli-g**; `tilt_angles()` **decidegrees**, derived from gravity | [findings/imu-characterisation](../findings/imu-characterisation-2026-08-27.md) |

**Our hub:** `device_uuid 03970000-3600-1B00-1450-30514B323320` · BLE `64:8C:BB:0A:1C:8C` ·
advertising as `Team 21` · MicroPython v1.20.0-1742.gf212bbe83, RPC 1.0.47, Hub OS 1.8.149.

---

## What was done

### Host prepared before the hub was ever plugged in

`./scripts/setup-host.sh --apply` — ModemManager stopped and disabled, a udev rule written giving
`ID_MM_DEVICE_IGNORE=1` and the stable `/dev/spike` symlink. `mmcli -L` showed ModemManager had **not**
in fact grabbed the device, so the long-standing
[host-environment.md](../findings/host-environment.md) blocker turned out to be a race we won rather
than a fault we hit. The mitigation stands anyway; it is not a race worth re-running each session.

### A baseline was captured BEFORE anything was written

[`probes/capture_baseline.py`](../../probes/capture_baseline.py) → six files in
[archives/hub-baseline/](../archives/hub-baseline/). **This is what made the firmware-integrity claim
provable rather than assertable**, and it is the single most reusable habit from this session. The
whole diff after uploading a module was: `lib` appears, 8 blocks consumed, battery and temperature
drift from charging. Every stock file byte-identical.

### Three new top-level directories, three verbs

| Directory | Verb | Contract |
|---|---|---|
| `probes/` | **reads** the hub | READ-ONLY by contract. `dir()`, getters, listings, file reads |
| `hub_programmer/` | **writes** to it | `upload.py` (dry-run default, refuses stock files), `run.py` (executes in RAM, leaves nothing) |
| `examples/` | **discovers** | Verbose per-device scripts; findings get distilled into `src/` |

`src/` stays what runs on the robot. **Never do discovery in `src/`.**

### The IMU was characterised, and a measurement threw itself out

`acceleration()` is milli-g (flat hub: `az≈989`). `tilt_angles()` is **decidegrees**, and that was
**derived, not looked up** — the accelerometer gives true tilt from gravity (0.705°), `tilt_angles()`
reported magnitude 6.7, ratio **9.53 ≈ 10**. Yaw wraps at ±180.0°. A full IMU tick costs **1.35 ms**,
so `config.py`'s assumed 100 Hz is plausible from the sensor side.

**The episode worth keeping:** a 30 s run reported 98.7° of gyro drift at 3.29 °/s. It was **discarded**
— the drift went +7.6, then −22.2, then +96.6, and steady drift does not reverse direction. The
operator was plugging in motors and handling the robot. `gyro_drift.py` was then rewritten to watch the
accelerometer *while* measuring, and it independently caught the disturbance (flagged CONTAMINATED at
t=14106 ms, gravity vector off by 2534 mg) and **refused to report a number**. The clean re-run gave
**≤0.0033 °/s**, resolution-limited at 1 ddeg over 30 s.

**A measurement that validates its own preconditions is the transferable idea here**, not the number.

### Bluetooth, end to end

Scan → connect → enumerate GATT → frame a request → parse the response → confirm identity.
Transport is service `FD02` with one write-without-response characteristic and one notify.
LEGO's COBS framing (delimiter `0x02`, XOR 3) was implemented from the published algorithm and
**validated in both directions**: the encoder against a known value (`InfoRequest` → `00 00 02`), the
decoder against a real 17-byte `InfoResponse` whose every field parsed sensibly.

> ⚠ **Negotiated MTU is 23; the hub advertises `max_packet_size` 509.** We are using 4 % of the
> available packet size. Irrelevant for a two-byte query, **a 20× difference for telemetry**.

---

## Decisions

| Decision | Record |
|---|---|
| **Deploy by writing modules to `/flash/lib` over the USB REPL**, SHA-256 verified on the hub | [ADR-0007](../decisions/0007-deploy-by-writing-modules-to-flash-lib.md) |
| `probes/` is read-only by contract; writing lives in `hub_programmer/` | [lessons/probe-with-scripts-not-commands](../lessons_learned/probe-with-scripts-not-commands.md) |
| Probe with scripts that have deadlines, never typed commands | same |
| Identify our hub by **device UUID over a connection** — never by name or MAC | [findings/ble-protocol](../findings/ble-protocol-2026-08-27.md) |
| **Blacklist item 2 added:** never press-and-hold CONNECT while plugging in USB | [CLAUDE.md](../../CLAUDE.md) |

---

## Defects found and fixed

1. **`src/hub_motors.py` referenced a bare `_motor` on six lines that was never defined.** **Every
   motor command would have raised `NameError` the first time the robot tried to move.** It passed
   `check-docs.py`'s import check because the name only resolves at *call* time. Now `hub_api._motor`.
2. **`src/telemetry.py` justified itself with a disproved fact** — its docstring said `bluetooth` is
   absent from the hub's module list. It is present, and is the full ubluetooth stack. The conclusion
   survives on a narrower reason; the old reason is struck in place.
3. **`src/telemetry.py` broke its own rule** ("the unit is part of the column name") with bare
   `accx/accy/accz`. Renamed to `*_mg` now the unit is measured — a **wire-format change**, so
   `VERSION` went to `spike-telemetry v2` in the same edit.
4. **`docs/runbooks/hub-identification.md` made two wrong predictions**, now marked ❌ **PREDICTION
   WRONG** in place rather than quietly corrected: `hub.info()` does not exist, and **both** offered
   forms for reading the battery were wrong (the real calls are `hub.battery_voltage()` and friends).
5. **`docs/research/spike3-api-reference.md` exceeded the 1200-line limit** — split, with the
   deployment and radio sections moved out because both are now settled by measurement elsewhere.

---

## Corrections to my own claims — the part worth re-reading

**Three things I asserted this session were wrong, and all three were caught before they hardened.**

1. **"USB probing and Bluetooth are mutually exclusive."** RETRACTED. The successful discovery changed
   two variables at once (power cycle *and* a CONNECT press), and a later **120 s scan with nothing
   holding the serial port** still saw nothing. The simpler explanation fits every observation: **the
   advertising window is short and self-terminating.** The controlled experiment is written down and
   has not been run. Until it is, this is **UNKNOWN**, not a rule.
2. **"The BLE address is public, therefore stable."** RETRACTED. Those bits classify *random*
   addresses only, where `01` means **resolvable private — which rotates**. Address type is unverified.
   **Never identify by MAC alone.**
3. **"Blind teleoperation is permitted."** RETRACTED. The relayed quote contains *"you can't have a
   human operator"* **and** *"if you do have a human operator, they cannot be looking at the arena"* —
   the first clause forbids what the second permits. I resolved a contradiction I had no business
   resolving. **KU-P0 is PARTIAL, autonomy remains the working assumption**, and it leads the
   professor list. [findings/mission-answers](../findings/mission-answers-2026-08-27.md)

---

## Safety finding

**Holding the CONNECT (Bluetooth) button while USB is being plugged in is the documented DFU /
bootloader gesture** — the one physical action that can reflash the hub. Its pink-green-blue-off cycle
shares all three colours with LEGO's harmless *"Hub OS updated, restart me"* pattern.
**Any three-colour cycle: stop and unplug. Single presses only.**

The operator had reported press-and-holding this button, but always on an already-running hub with USB
already attached — **not** the DFU gesture. No harm occurred. The rule is now blacklist item 2.

---

## Blockers — one is now the whole project

1. **The units of "10×10".** Untouched by every answer received today. It decides whether one downward
   sensor needs 8 minutes of sweeping or 23, and therefore whether the *design* changes or just a
   tuning value. **Free to close: one question.**
2. **No sensors owned.** The colour separability go/no-go — the gate on the entire detection design —
   needs one colour sensor and a pack of sticky notes. It does **not** need the robot.
3. **Ports A–F empty.** No motor or wheel measurement is possible until the Builder mounts parts.

---

## What's next

**[../plans/next-session.md](../plans/next-session.md)** — the ordered plan for the next class, grouped
by what each item actually needs, because class time is the scarce resource and the hub is not always
present.

Superseded: [../plans/first-hardware-session.md](../plans/first-hardware-session.md) was the plan for
today. It was executed. Kept for its reasoning.
