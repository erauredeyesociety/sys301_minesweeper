# Finding — First contact with the hub: identity, API generation, filesystem, radio

**Date:** 2026-08-27 · **Operator present:** yes, the operator connected the hub and said so first
· **Hub connected:** **YES — over USB, for the first time in this project**
· **Anything written to the hub by the probes in this document:** **NO.** Every probe here is a
listing, a `dir()`, a getter, or a file read.

> **Correction, same day — do not read the line above as "nothing was ever written".** Later on
> 2026-08-27, in a separate step that is *not* part of this document, one file was written:
> `/flash/lib/config.py`, 13262 bytes. The filesystem baseline was then re-captured and diffed, and the
> firmware was proved unchanged. That is its own document —
> [firmware-integrity-proof.md](./firmware-integrity-proof.md) — and this correction stays visible
> rather than being edited away, because the honesty claim is the point.

> **These are measurements.** Not computed, not confirmed against a datasheet — read off our own
> hardware over the cable. Everything below is the hub's own words. Where something is still inferred
> it is marked `[INFERRED]`, and where a probe was deliberately *not* run it says so.
> Vocabulary rule: [../lessons_learned/say-which-kind-of-verified.md](../lessons_learned/say-which-kind-of-verified.md).

Probes live in [`probes/`](../../probes/) and are re-runnable. Transcripts are the `_hub-*.txt` files
in this folder.

---

## 0. This file is the overview — the detail lives in three companions

Everything below is **first contact**: who the hub is, what API it speaks, what is on its filesystem,
what its radio is doing. Three things measured later the same day have their own documents, and are
**not** duplicated here:

| Document | What it holds |
|---|---|
| [firmware-integrity-proof.md](./firmware-integrity-proof.md) | The one write to `/flash/lib`, the re-capture, the complete baseline diff, and why writing a `.py` file cannot touch the firmware image |
| [imu-characterisation-2026-08-27.md](./imu-characterisation-2026-08-27.md) | IMU units derived from gravity (milli-g, decidegrees), the ±180° yaw wrap, face/gesture constants, read cost + the unresolved caching anomaly, gyro drift |
| [../runbooks/deploy-to-hub.md](../runbooks/deploy-to-hub.md) | The operator procedure for getting code onto the hub over USB with no LEGO app |

Raw transcripts of the on-hub programs are in [runs/](./runs/INDEX.md).

---

## 1. Which hub is ours — the identity to match against later

| | |
|---|---|
| **`hub.device_uuid()`** | **`03970000-3600-1B00-1450-30514B323320`** |
| **`hub.hardware_id()`** | **`E`** |
| `machine.unique_id()` | `b'6\x00\x1b\x00\x14P0QK23 '` |
| Battery | 7882 mV, charging at 364 mA |
| Temperature | `hub.temperature()` → `243` — `[INFERRED]` deci-degrees C, i.e. 24.3 °C |

**Why this matters more than it looks.** The classroom will have several SPIKE Prime hubs advertising
over Bluetooth at once, all with similar names, and any of them can be renamed. A BLE scan alone
cannot tell you which is yours.

**USB can.** USB is point-to-point: whatever answered on `/dev/spike` is the hub physically plugged
into this laptop. So we read the permanent identifiers over the cable, where there is no ambiguity,
and match a BLE advertisement against them later.

`machine.unique_id()` is the STM32 die ID, and it is **the tail of the device UUID**:

```
machine.unique_id()  =  36 00 1B 00 14 50 30 51 4B 32 33 20
hub.device_uuid()    =  03970000-3600-1B00-1450-30514B323320
                        ^^^^^^^^ └──────── the same bytes ────────┘
```

`0397` is **LEGO System A/S's Bluetooth SIG company identifier** (0x0397 = 919), which is also what a
LEGO advertisement's manufacturer-data field is keyed on. `probes/ble_scan.py` uses that to filter.

**Read it with:** `python3 probes/whoami.py`

---

## 2. API generation — SPIKE 3, decisively, and it closes the project's biggest unknown

```
MicroPython v1.20.0-1742.gf212bbe83 on 2025-03-27; SPIKE Prime with STM32F413
```

| Probe | Result |
|---|---|
| `os.uname()` | `sysname='SPIKE'`, `release='1.24.0'`, `version='v1.20.0-1742.gf212bbe83 on 2025-03-27'`, `machine='SPIKE Prime with STM32F413'` |
| `sys.implementation` | `micropython (1, 24, 0)`, `_mpy=7942` |
| `sys.version` | `3.4.0` (the Python language level MicroPython implements) |
| `sys.path` | `['', '.frozen', '/flash', '/flash/lib']` |

`help('modules')` returned, verbatim:

```
__main__ _asyncio _system/default _system/menu _system/scratch _system/test_selector
array asyncio/__init__ asyncio/core asyncio/event asyncio/funcs asyncio/lock
asyncio/stream binascii bluetooth builtins cmath collections color color_matrix
color_sensor deflate device distance_sensor errno force_sensor gc hashlib heapq
hub io json machine math micropython motor motor_pair orientation os platform
random re runloop select struct sys time uasyncio uctypes vfs zlib
```

**Conclusion: SPIKE 3 / current API.** `motor`, `motor_pair`, `runloop`, `color_sensor`,
`distance_sensor`, `force_sensor` are all present, and — the decisive part — **there is no `spike`
module and no `mindstorms` module.**

**The consequence is blunt: every SPIKE 2 tutorial is inapplicable to us.** Anything written
`from spike import PrimeHub` will `ImportError` on this hub. Most SPIKE material online is SPIKE 2.
Check the generation of a source before believing it.

Two versions are reported and they disagree — banner `v1.20.0-1742` versus `sys.implementation`
`1.24.0`. `[INFERRED]`: `1.24.0` is the upstream MicroPython core and `v1.20.0-1742.gf212bbe83` is
LEGO's own build string occupying the banner slot. **Quote both**; do not average them into one
"version".

### `dir(hub)`

```
battery_current  battery_temperature  battery_voltage  button  config  device_uuid
hardware_id  light  light_matrix  motion_sensor  port  power_off  sound
temperature  usb_charge_current
```

**Read it with:** `python3 probes/identify_hub.py` (or `scripts/identify-hub.sh`)

---

## 3. The filesystem — this is how code gets on without the LEGO app

`os.listdir('/flash')`:

```
README.txt   boot.py   config   main.py   program   pybcdc.inf
```

**`/flash/README.txt`, in the firmware's own words:**

> *"This is a MicroPython board. You can get started right away by writing your Python code in
> `main.py`. … Linux: use the command: `screen /dev/ttyACM0`"*

**`/flash/boot.py`, complete — all five lines:**

```python
# boot.py -- run on boot to configure USB and filesystem
# Put app code in main.py
import micropython, hub
micropython.alloc_emergency_exception_buf(128)
hub.config["hub_os_enable"] = True
```

**`/flash/main.py`, complete:**

```python
# main.py -- put your code here!
```

| Fact | Value | Why it matters |
|---|---|---|
| `main.py` | empty, 34 bytes | Ours to write. Nothing to preserve. |
| `/flash/program` | **empty** | No stored program slots are in use. Nothing of anyone's to destroy. |
| `/flash/lib` | **did not exist** *(as of this capture)* | But it *was* already on `sys.path` — creating it is how our pure modules get importable. **It exists now:** it was created later the same day by the first upload — [firmware-integrity-proof.md](./firmware-integrity-proof.md). |
| Free space | `os.statvfs` → 7923 × 4096 B = **32.4 MB** | Our entire `src/` is a rounding error against this. |
| `config` | a directory (`os.stat` mode `16384`) | Distinct from the `hub.config` object in `boot.py`. Not inspected. |

> ⚠ **`hub.config["hub_os_enable"] = True` is the LEGO Hub OS switch**, and it lives in an ordinary,
> writable `boot.py`. Setting it `False` would plausibly boot a plain MicroPython board with no LEGO
> layer at all. **We are not doing that, and nobody should on impulse** — it changes how the hub
> behaves at boot on shared course equipment. If it is ever wanted it is an
> [ADR](../decisions/), not an experiment. Recorded here because it is exactly the kind of one-line
> change that looks harmless and is not.

**`[INFERRED]`, still not tested as of 2026-08-27:** that writing `/flash/main.py` causes our code to
run at boot, and how it interacts with the Hub OS started by `boot.py`. The README asserts the
MicroPython convention; whether LEGO's layer pre-empts it is unproven. **Do not build a deploy process
on this until it is tested.** Note the distinction that the rest of the day settled: putting a *module*
in `/flash/lib` and importing it is **proven**; auto-running a *program* at boot is **not**.

**Read it with:** `python3 probes/filesystem.py`

---

## 4. Bluetooth — the radio is NOT advertising, and our earlier inference was wrong

### 4a. The hub was not advertising *when this scan ran* — and later that day it was, and we connected

> **⚠ Superseded in part, same day.** Everything below is what the first scan saw and it is left intact.
> **Later on 2026-08-27 the hub was found, connected and queried over BLE from Linux with `bleak` and no
> LEGO software**, and identified by matching its `DeviceUuidResponse` against the UUID read over USB —
> [ble-protocol-2026-08-27.md](./ble-protocol-2026-08-27.md), analysis in
> [../research/ble-bring-up.md](../research/ble-bring-up.md). **The advertising window turned out to be
> short and self-terminating**, which is the most likely reason this scan saw nothing. ⚠ **Candidate 3
> below — "USB suppresses advertising" — is RETRACTED:** the successful discovery changed two variables
> at once, and a later 120 s scan with nothing holding the serial port also saw nothing.


A passive host-side scan (`probes/ble_scan.py`, 12 s) saw **581 advertising devices** — a busy campus
RF environment — and **zero** that matched LEGO by any of three tests: company ID `0x0397`, service
UUID `0xFD02`, or name. This is not "lost in the crowd"; the hub is not transmitting.

Observed while **USB was connected**. Candidate explanations, none yet tested:

1. The radio is not in advertising mode and the CONNECT button did not put it there.
2. It is already connected to something, and a connected hub generally stops advertising.
3. **`[INFERRED]` — USB suppresses advertising on this firmware.** Settled by unplugging USB, running
   on battery, and re-scanning. That costs the REPL for the duration, so it is an operator decision.

**The operator reports pressing and holding the Bluetooth button with no light.** Relevant: the API
does not call it Bluetooth. `dir(hub.button)` → `CONNECT`, `LEFT`, `POWER`, `RIGHT`, and `dir(hub.light)`
→ `CONNECT`, `POWER`, `color`. **The Bluetooth button is `CONNECT`**, and its light is addressable
from code as `hub.light.CONNECT`.

### 4b. `bluetooth` is the real MicroPython BLE module — this overturns a previous inference

`dir(bluetooth)` → `BLE`, `UUID`, `FLAG_READ`, `FLAG_WRITE`, `FLAG_NOTIFY`, `FLAG_INDICATE`,
`FLAG_WRITE_NO_RESPONSE`

`dir(bluetooth.BLE)`:

```
active  config  gap_advertise  gap_connect  gap_disconnect  gap_pair  gap_passkey
gap_scan  gattc_discover_characteristics  gattc_discover_descriptors
gattc_discover_services  gattc_exchange_mtu  gattc_read  gattc_write
gatts_indicate  gatts_notify  gatts_read  gatts_register_services
gatts_set_buffer  gatts_write  irq
```

That is the complete standard MicroPython `ubluetooth` surface — a full GAP + GATT server and client.

**This contradicts what this project previously assumed.**
[../research/bluetooth-control-plane.md](../research/bluetooth-control-plane.md) inferred that a
program on the hub *probably cannot* open its own BLE socket, and the telemetry design was shaped
around that — `print()` out through the firmware's `ConsoleNotification` instead. **That inference was
drawn from an absence in a module list, and the module list now shows the opposite.**

**What is still NOT established, and the distinction matters:** that the API *exists* is not that the
firmware will *permit* its use while LEGO's own stack owns the radio. Calling `BLE().active(True)`
alongside a running Hub OS could fail, or could disrupt the firmware's own connection.

**Deliberately not run.** `probes/bluetooth_state.py` inspects the class with `dir()` and never
instantiates `BLE()`. Instantiating the radio is a state change on shared equipment, which is the
operator's call, not a probe's.

**Read it with:** `python3 probes/bluetooth_state.py` · `python3 probes/ble_scan.py`

---

## 4c. The API surface, measured — and it settles the detection design

Captured in full in [../archives/hub-baseline/03-api-surface.txt](../archives/hub-baseline/03-api-surface.txt).
The parts that decide something:

**`color_sensor` → `color` · `reflection` · `rgbi`**

**`rgbi()` exists.** That is raw red / green / blue / intensity, so we are **not** forced through the
sensor's built-in colour ID. This was an open worry: sticky notes are matte pastel, the worst case for
a built-in classifier, and [../scope.md](../scope.md) FR-2b wants *classification*, not just presence.
We can threshold channel ratios ourselves and report UNKNOWN when they do not separate.
`[UNVERIFIED]`: the range of each channel (0–255? 0–1024?) — one bench reading settles it.

**`color` constants — the complete list the firmware knows:**

```
AZURE  BLACK  BLUE  GREEN  MAGENTA  ORANGE  PURPLE  RED  TURQUOISE  UNKNOWN  WHITE  YELLOW
```

Two consequences for the mission as the professor described it:

- **`YELLOW` exists**, and `BLUE`/`AZURE` exist — so mines (yellow notes) and a blue-painters-tape
  boundary each have a native class.
- **There is no `GREY` and no `SILVER`.** Silver duct tape has no class to land in; it will read
  `WHITE` or `UNKNOWN`, and a specular surface will do so *inconsistently* with angle. **If the arena
  boundary is silver duct tape, built-in colour ID is the wrong instrument for it** and `rgbi()` plus
  our own rule is the only defensible route. This is now the strongest argument for buying the colour
  sensor early and running the separability gate before committing to a detection design.

**`motor`** — `run` · `run_for_degrees` · `run_for_time` · `run_to_absolute_position` ·
`run_to_relative_position` · `set_duty_cycle` · `get_duty_cycle` · `velocity` · `absolute_position` ·
`relative_position` · `reset_relative_position` · `status` · `info` · `stop`, with
`BRAKE` `COAST` `HOLD` `SMART_BRAKE` `SMART_COAST`, `CLOCKWISE` `COUNTERCLOCKWISE`,
`SHORTEST_PATH` `LONGEST_PATH`, and the states `READY` `RUNNING` `STALLED` `ERROR` `DISCONNECTED`.

**`STALLED` is worth noting now** — a stall is detectable in software, which matters for a robot that
may drive into something with no wall sensor.

**`motor_pair`** — `pair` · `unpair` · `move` · `move_tank` · `move_for_degrees` ·
`move_tank_for_degrees` · `move_for_time` · `move_tank_for_time` · `stop`, pairs `PAIR_1..3`.
Differential drive is a first-class primitive; we do not have to build it.

**`runloop`** — `run` · `sleep_ms` · `until` · `wait`, states `SUCCESS` `CANCELLED` `TIMEOUT` `WAITING`.

**`hub.motion_sensor`** — `acceleration` · `angular_velocity` · `quaternion` · `tilt_angles` ·
`up_face` · `stable` · `gesture` · `tap_count` · `reset_yaw` · `set_yaw_face` · `get_yaw_face`.
**All six IMU axes are reachable**, which is what [../../src/telemetry.py](../../src/telemetry.py)
already assumes. `stable` and `up_face` give a cheap "is the robot flat / has it tipped" check.

**`device`** — `id` · `data` · `ready` · `set_mode` · `reset_mode` · `write_mode` ·
`get_duty_cycle` · `set_duty_cycle`. **`device.id(port)` is how we detect what is plugged into A–F**
at run start, which [../plans/mission-algorithm.md](../plans/mission-algorithm.md) needs for its
self-check. Not yet exercised — we own no sensors.

---

## 5. Host preparation — applied today, before the first session

`./scripts/setup-host.sh --apply`, run before any port was opened:

| Change | State |
|---|---|
| ModemManager stopped and disabled | was `active`/`enabled`; **now `inactive`** |
| `/etc/udev/rules.d/99-lego-spike.rules` written | `ID_MM_DEVICE_IGNORE=1` now set on the device |
| `/dev/spike` stable symlink | live, → `ttyACM0` |
| `devel` in `dialout` | already true |
| pyserial 3.5, screen | already present |
| `bleak` | **installed today** via `pip install --user` (host change, reversible) |

`mmcli -L` returned `No modems were found` and nothing held the port, so ModemManager had not in fact
grabbed this device before we disabled it. **The mitigation is still correct** — it is a race we do
not want to re-run every session, and losing a class period to a corrupted first session is the
failure this prevents.

Host Bluetooth: BlueZ **5.64** (above the 5.55 floor `bleak` needs), adapter `C4:23:60:D3:C0:5B`
powered, not rf-killed.

---

## 6. What this closes, and what it opens

**Closed:**

- **KU-T1 / hub OS generation** — SPIKE 3. [../scope.md](../scope.md) can strike its `[UNKNOWN]`.
- **Which hub is ours** — the device UUID above.
- **Is there a usable REPL over USB** — yes, plain MicroPython at 115200.
- **Is the LEGO app required to reach the hub** — no. Nothing in this session used it.
- **Is the LEGO app required to *write* to the hub** — also no, established later the same day:
  [firmware-integrity-proof.md](./firmware-integrity-proof.md) · [../runbooks/deploy-to-hub.md](../runbooks/deploy-to-hub.md).

**Opened, in priority order:**

1. **How does a *program* get launched, as opposed to a *module* imported?** ⚠ This has been **halved,
   not closed**, later the same day. **Proven:** a module written to `/flash/lib` imports on the hub
   (`OK config`, 210528 B free afterwards), and `/flash/lib` was already on `sys.path`.
   **Still untested:** whether `/flash/main.py` autoruns at boot and whether the Hub OS pre-empts it.
   Do not treat the deploy story as finished on the strength of the first half.
2. ~~**Why is the hub not advertising, and does USB suppress it?**~~ **Largely answered later the same
   day** — BLE works, the hub is reachable and identifiable
   ([ble-protocol-2026-08-27.md](./ble-protocol-2026-08-27.md)). What remains is **how long the
   advertising window stays open** (KU-M17); a client must wait-and-pounce rather than
   scan-then-connect. The USB-suppression hypothesis is retracted.
3. **Can a hub program drive `bluetooth.BLE()` while the Hub OS runs?** Needs operator approval.
4. **What is actually plugged into ports A–F?** Answered later the same day: **all six read EMPTY** —
   `device.id()` raises `OSError` on every port and `motor.status()` returns `5` on every port. The
   motors were not connected at the time. `5` is therefore known to be what an *unoccupied* port
   returns; which named `motor` constant equals 5 is **unread**.

**Not done and not to be done casually:** `machine` exposes `bootloader`, `reset`, `soft_reset`.
All three are forbidden by [ADR-0001](../decisions/0001-stock-lego-firmware-only.md).

---

**Related:** [firmware-integrity-proof.md](./firmware-integrity-proof.md) ·
[imu-characterisation-2026-08-27.md](./imu-characterisation-2026-08-27.md) ·
[../runbooks/deploy-to-hub.md](../runbooks/deploy-to-hub.md) ·
[../runbooks/hub-identification.md](../runbooks/hub-identification.md) ·
[../research/bluetooth-control-plane.md](../research/bluetooth-control-plane.md) (§ on the hub's own
radio is now superseded by § 4b above) ·
[../lessons_learned/probe-with-scripts-not-commands.md](../lessons_learned/probe-with-scripts-not-commands.md)
