# SPIKE Prime on Native Linux — Toolchain Research (ERAU SYS 301)

**Scope:** LEGO Education SPIKE Prime Technic Large Hub (45601, ports A–F), **stock LEGO firmware only**, Ubuntu 22.04, zero budget.
**Research date:** 2026-08-25. **Hub not connected at time of writing** — every claim below is marked as *verified from a source*, *verified from source code*, or **UNVERIFIED** (needs a hub-in-hand check).

Local environment confirmed on this machine: `Ubuntu 22.04.5 LTS`, `Python 3.10.12`, `Google Chrome 151.0.7922.169`, user `devel` is in `dialout`, and **`ModemManager` is `active` and `enabled`** (this is a real problem — see Linux Gotchas).

---

## Summary

1. **The hub's USB MicroPython REPL is the load-bearing capability.** Plug in USB → the hub enumerates as a CDC-ACM serial device (usually `/dev/ttyACM0`, 115200 8N1). Sending `Ctrl+C` (`0x03`) stops the hub's foreground program and drops you at a `>>> ` MicroPython prompt. This is true on **Hub OS 2** ([HTW/WHZ technical report, Oct 2022](https://libdoc.whz.de/opus4/files/15400/lego_spike_linux.pdf)) **and still true on Hub OS 3.4.3** ([SPremote README, last commit 2026-02-04](https://github.com/jeflem/spremote)). No firmware replacement, no LEGO account, no cloud.
2. **There are two mutually incompatible host protocols**, and which one you get depends entirely on Hub OS generation:
   - **Hub OS 2** → newline-delimited **JSON-RPC** over the same serial port, plus a continuous telemetry stream.
   - **Hub OS 3** → binary **COBS-framed messages with CRC32**, documented officially by LEGO at [lego.github.io/spike-prime-docs](https://lego.github.io/spike-prime-docs/).
   The REPL underneath is common to both; the RPC layer is not.
3. **Linux is not an officially supported platform** for any LEGO SPIKE product — the [SPIKE Prime system requirements](https://education.lego.com/en-us/product-resources/spike-prime/downloads/system-requirements/) list Windows, macOS, iOS, Android and ChromeOS only, and there is **no Linux desktop build** on the [SPIKE App download page](https://education.lego.com/en-us/downloads/spike-app/software/). The **SPIKE Web App in Chrome is the only first-party route** and it works on Linux over USB (Web Serial).
4. **Opening the LEGO app with a mismatched hub does trigger a mandatory update prompt.** LEGO states outright: *"When a user connects a Hub to their device, the app verifies that it is compatible with the HubOS version. If not, the app notifies the user that a HubOS is required before they can continue"* and this specific notification *"cannot be disabled"* ([LEGO SPIKE Prime software updates](https://education.lego.com/en-us/product-resources/spike-prime/downloads/software-updates/)). **So: identify the Hub OS from the Linux serial port BEFORE ever opening the web app.**
5. **Recommended primary workflow:** VS Code on Ubuntu + [PeterStaev's `lego-spikeprime-mindstorms-vscode`](https://github.com/PeterStaev/lego-spikeprime-mindstorms-vscode) extension (Hub OS 3, USB serial, actively maintained — last commit 2025-08-29) for slot upload + run + console capture. Keep a raw `tio`/`screen` REPL session as the debugging fallback, and consider [SPremote](https://github.com/jeflem/spremote) for host-driven control where the host does the thinking.

---

## Recommended workflow

### Step 0 — Prepare the host (do this before plugging anything in)

```bash
# 1. Neutralise ModemManager for the LEGO hub (VID 0x0694, PID 0x0009)
sudo tee /etc/udev/rules.d/99-lego-spike.rules >/dev/null <<'EOF'
# LEGO Education SPIKE Prime Large Hub — CDC ACM
SUBSYSTEM=="tty", ATTRS{idVendor}=="0694", ATTRS{idProduct}=="0009", \
  MODE="0660", GROUP="dialout", SYMLINK+="spike", ENV{ID_MM_DEVICE_IGNORE}="1"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger

# 2. ID_MM_DEVICE_IGNORE is IGNORED under ModemManager's default 'strict' filter policy.
#    Simplest zero-risk option on a dev box with no cellular modem:
sudo systemctl disable --now ModemManager

# 3. Serial tooling
sudo apt install -y tio screen python3-serial   # tio is nicer than screen; picocom also fine
```

Vendor/product IDs are from the extension source (`VENDOR_ID = 0x0694`, `PRODUCT_ID = 0x0009` in `src/clients/usb-client.ts` and `src/web/clients/web-usb-client.ts`) and cross-check with the Chrome blog's *"USB Vendor ID: 1684"* (= 0x0694) ([Chrome for Developers, 2023-05-22](https://developer.chrome.com/blog/lego-education-spike-web-bluetooth-web-serial)).

### Step 1 — Identify the Hub OS, non-destructively

```bash
sudo dmesg -w &          # watch enumeration
# plug in USB, press the hub's power button
ls -l /dev/ttyACM* /dev/spike
tio /dev/ttyACM0 -b 115200        # or: screen /dev/ttyACM0 115200
```

Then apply the decision procedure in [Hub OS identification](#hub-os-identification) below. **Do not open `spike.legoeducation.com` yet.**

### Step 2 — Edit / upload / run / read back

Primary path (Hub OS 3):

```bash
code --install-extension PeterStaev.lego-spikeprime-mindstorms-vscode
```

Put this as the first line of your program so the extension skips the type/slot prompts:

```python
# LEGO slot:5 autostart
```

Then: click the status-bar item to connect over USB → use the editor's upload/run buttons. Program output (`print(...)`) comes back as `ConsoleNotification` (message id `0x21`) frames and is surfaced in the extension's output channel — the extension implements exactly that message (`src/messages/console-notification-message.ts`).

Fallback path (always available, either Hub OS): raw REPL over `tio`, plus `pyserial` scripting.

### Step 3 — Standalone run on the robot

Once the program is in a slot, disconnect USB and start it from the hub's on-brick slot selector (left/right buttons to pick slot, center button to run). Slots are `0..19` — LEGO's glossary: *"One of the 20 program slots on the hub, indexed from 0 to 19"* ([glossary.rst](https://github.com/LEGO/spike-prime-docs/blob/main/docs/source/glossary.rst)).

---

## Option comparison table

| # | Option | Transport | Hub OS | Maintained? (last commit) | Firmware safe? | Verdict for SYS 301 |
|---|---|---|---|---|---|---|
| 1 | **VS Code ext. `PeterStaev/lego-spikeprime-mindstorms-vscode` v3.1.3** | USB serial 115200 (node-`serialport`) **or** BLE | **3 only** (v2.x+); use v1.x for Hub OS 2 | ✅ **2025-08-29**, Apache-2.0, 82★ | ✅ stock | **Primary.** Real IDE loop, slots, autostart comment, MPY compile, multi-file preprocessor, console readback |
| 2 | **Raw MicroPython REPL** (`tio`/`screen`/`pyserial`) | USB serial 115200 | 2 **and** 3 | n/a — it's the firmware itself | ✅ stock | **Always keep this.** Ground truth for debugging, version probing, one-liners. No file management |
| 3 | **SPremote (`jeflem/spremote`)** | USB serial 115200 via `pyserial` | tested on **3.4.3** | ✅ **2026-02-04**, GPL-3.0 | ✅ stock (drives REPL, no flashing) | **Strong secondary.** Host-side control: your algorithm runs on the Ubuntu box, hub is a peripheral. Great for a minesweeper search/planning loop; bad for tethered-free autonomy |
| 4 | **LEGO SPIKE Web App in Chrome** | Web Serial (USB) — Web Bluetooth blocked on Linux | matches installed app version | ✅ LEGO first-party | ⚠️ **will demand a Hub OS update if mismatched** | Emergency/verification only. Not a dev loop |
| 5 | **LEGO official protocol reference + `examples/python`** | BLE (`bleak`) | 3 | main-branch commit **2024-03-04**; repo touched 2025-09-29 | ✅ stock | Reference material + a build-your-own-CLI starting point, not a finished tool |
| 6 | `sanjayseshan/spikeprime-tools` (`spikejsonrpcapispike.py`) | USB serial JSON-RPC | **2 only** | ❌ **2022-08-02** | ✅ stock | Historical. Only if the hub turns out to be Hub OS 2 |
| 7 | `sanjayseshan/spikeprime-vscode` | USB serial JSON-RPC | **2 only** | ❌ **2022-12-30** | ✅ stock | Superseded by #1 |
| 8 | `smr99/lego-hub-tk` ("LEGO Hub Toolkit") | USB serial JSON-RPC | **2 only** | ❌ **2022-02-03** | ✅ stock | Abandoned; the 2022 report already had to patch its paths |
| 9 | `nutki/spike-tools` | USB serial JSON-RPC | **2 only** (2020-era) | ❌ **2020-02-13** | ✅ stock | Dead upstream of #6 |
| 10 | `gpdaniels/spike-prime` | n/a (research notes + firmware dumps) | 2-era | ❌ **2023-10-24**, MIT, 313★ | ⚠️ contains DFU/firmware work | Read-only reference. Do **not** run the firmware-flashing parts |
| 11 | **Pybricks** | — | — | ✅ very active | ❌ **replaces LEGO firmware** | **BLACKLISTED — see Excluded options** |

Repo dates were read from the GitHub REST API (`/repos/{owner}/{repo}` → `pushed_at`) on 2026-08-25, and for cloned repos from `git log -1`.

---

## Hub OS identification

### Why this matters first

LEGO's own support text is unambiguous that the update prompt is **not dismissible**: *"a user is required to update the Hub, because the app and HubOS versions are not compatible with each other (this notification cannot be disabled)"* ([software-updates](https://education.lego.com/en-us/product-resources/spike-prime/downloads/software-updates/)). So identify from Linux first.

### Non-destructive checks, in order of safety

**A. Physical: the center button colour (do this with the hub simply powered on, no host).**

- **Green** — *"The Hub is turned on and running a Hub OS version that is compatible with the SPIKE, and the battery is charged to at least 20%."*
- **White** — *"The Hub is turned on, but is running a Hub OS version that is not compatible with the SPIKE. Update Hub OS using the SPIKE App."*
- Flashing purple = firmware update in progress; flashing orange = battery <20%; flashing red = thermal.
Source: [LEGO Education SPIKE Prime FAQs](https://education.lego.com/en-au/product-resources/spike-prime/troubleshooting/faqs/) and the [LEGO Education Partner Portal troubleshooting page](https://legoeducation.atlassian.net/wiki/spaces/LPP/pages/36814651433).

⚠️ **Caveat:** this signal is *relative to whatever app the hub last talked to*, not an absolute "OS 2 vs OS 3" readout. Treat it as a hint only.

**B. Serial idle-traffic test (strong, zero writes).** Open the port and *watch without typing*:

```bash
tio /dev/ttyACM0 -b 115200
```

- **A continuous flood of bracketed numbers scrolling by → Hub OS 2.** The 2022 report: *"You should see lots of numbers (not well formatted) and numbers should change when you move or shake the hub"* — this is the Hub OS 2 high-level program streaming telemetry ([WHZ report](https://libdoc.whz.de/opus4/files/15400/lego_spike_linux.pdf)).
- **Silence / empty terminal → Hub OS 3.** SPremote's Hub OS 3.4.3 procedure: *"Now you should see an empty terminal. Press `Ctrl+C`. Now you see the hub's Python interpreter waiting for input (`>>>`)"* ([SPremote README](https://github.com/jeflem/spremote)).

This test is purely passive and is the cleanest discriminator available without a hub-in-hand.

**C. REPL API probe (one `Ctrl+C`, then two imports — reversible).**

```
Ctrl+C                     # stops the foreground program, gives >>>
>>> import motor           # succeeds ⇒ Hub OS 3
>>> from spike import PrimeHub   # succeeds ⇒ Hub OS 2 (legacy spike package present)
>>> import os; os.listdir('/')
>>> import os; print(os.uname())
```

`import motor` / `from hub import port` / `import runloop` are the Hub OS 3 module set ([LEGO SPIKE 3 Python reference, Tufts CEEO mirror](https://tuftsceeo.github.io/SPIKEPythonDocs/SPIKE3.html)); the `spike` package with `PrimeHub`/`MotorPair` is the Hub OS 2 set ([SPIKE 2 reference](https://tuftsceeo.github.io/SPIKEPythonDocs/SPIKE2.html)). SPremote's own device classes issue exactly `import motor`, `import color_sensor`, `from hub import motion_sensor` — confirming these names on 3.4.3 firmware (`spremote/motor.py`, `spremote/color_sensor.py`, `spremote/motion_sensor.py`).

**UNVERIFIED:** the exact tuple `os.uname()` returns on Hub OS 3, and whether `hub.info()` still exists there (it did on Hub OS 2-era firmware). `help(hub)` was the documented way to get long version strings on the older firmware ([gpdaniels/spike-prime firmware notes](https://github.com/gpdaniels/spike-prime/blob/master/firmware/README.md)). Probe these on the real hub and record the output.

**D. Protocol probe (definitive, still non-destructive).** Send an `InfoRequest` and read the `InfoResponse`:

- **Hub OS 3:** message id `0x00`, payload is the single byte `\x00`, COBS-framed with CRC32. The response (id `0x01`) carries `rpc_major/minor/build`, **`firmware_major/minor/build`**, `max_packet_size`, `max_message_size`, `max_chunk_size`, `product_group_device`. Field layout confirmed in both LEGO's reference implementation (`examples/python/messages.py`) and the VS Code extension (`src/messages/info-response-message.ts`, little-endian `getUint16` at offsets 3/7/9/11/13/15).
- **Hub OS 2:** the equivalent is the JSON-RPC route — `spikejsonrpcapispike.py fwinfo` ("Show firmware version") over `/dev/ttyACM0` ([spikeprime-tools README](https://github.com/sanjayseshan/spikeprime-tools/blob/master/README.md)).

Neither request writes to flash. `InfoRequest` is explicitly the mandated *first* message of the Hub OS 3 handshake ([connect.rst](https://lego.github.io/spike-prime-docs/)).

⚠️ **UNVERIFIED but strongly implied:** LEGO's protocol docs describe **BLE only** — I grepped the entire `docs/source/` tree of `LEGO/spike-prime-docs` and there is **zero** mention of USB or serial. That the identical COBS+CRC32 message set also runs over the USB CDC-ACM endpoint is established by *working third-party code*, not by LEGO documentation: PeterStaev's `usb-client.ts` opens `serialport` at `baudRate: 115200` and speaks the same `src/messages/*` classes it uses over BLE. Treat "official protocol over USB" as community-verified.

### The nuclear-safe inspection mode

Holding the **left button while powering on** boots the hub *straight into the MicroPython interpreter*, skipping the high-level program entirely. In that mode the hub does not react to button events (except power down) and cannot talk to the SPIKE App at all ([WHZ report](https://libdoc.whz.de/opus4/files/15400/lego_spike_linux.pdf), citing gpdaniels). This is the safest possible way to inspect a hub you do not want touched.

---

## API generation differences

Hub OS 2 = SPIKE App 2 / "SPIKE Legacy" (app 2.x). Hub OS 3 = SPIKE App 3.x (current; 3.4.x as of the most recent release notes). A hub runs exactly one OS at a time, and *"a SPIKE hub can be compatible with only one version of the app"* ([RoboCamp](https://www.robocamp.eu/en/blog/lego-spike-app-update/)).

### Imports

| | Hub OS 2 (legacy) | Hub OS 3 (current) |
|---|---|---|
| Preamble | `from spike import PrimeHub, Motor, MotorPair, ColorSensor, LightMatrix`<br>`from spike.control import wait_for_seconds, wait_until, Timer` | `import motor, motor_pair, color_sensor, runloop`<br>`from hub import port, light_matrix, motion_sensor, button` |
| Model | OO — you construct objects bound to port **letters** (`Motor('A')`) | Procedural — module-level functions take a port **constant** (`motor.run(port.A, 500)`) |
| Ports | strings: `'A'`…`'F'` | `hub.port.A`…`hub.port.F`, which are ints `0`…`5` |

### Single motor

| Task | Hub OS 2 | Hub OS 3 |
|---|---|---|
| Construct | `m = Motor('A')` | — (stateless) |
| Continuous run | `m.start(speed)` — speed is **%**, −100…100 | `motor.run(port, velocity, *, acceleration=1000)` — velocity is **deg/s**: small ±660, medium ±1110, large ±1050 |
| Relative move | `m.run_for_degrees(degrees, speed)` | `await motor.run_for_degrees(port, degrees, velocity, *, stop=BRAKE, acceleration=1000, deceleration=1000)` |
| Absolute move | `m.run_to_position(position, speed, direction, stop_action)` | `await motor.run_to_absolute_position(port, position, velocity, *, direction=SHORTEST_PATH, stop=BRAKE, ...)` |
| Read angle | `m.get_position()` (deg) | `motor.absolute_position(port)` (deg) / `motor.velocity(port)` (deg/s) |
| Stop | `m.stop()`, `m.set_stop_action(action)` | `motor.stop(port, *, stop=BRAKE)`; constants `COAST, BRAKE, HOLD, CONTINUE, SMART_COAST, SMART_BRAKE` |

**The units change is the #1 porting trap: percent → degrees/second.**

### Motor pairs / drivebase

| Task | Hub OS 2 | Hub OS 3 |
|---|---|---|
| Create | `mp = MotorPair('B', 'C')` | `motor_pair.pair(motor_pair.PAIR_1, port.B, port.C)` — slots `PAIR_1..PAIR_4` |
| Steer, continuous | `mp.start(speed, rotation)` | `motor_pair.move(pair, steering, *, velocity=360, acceleration=1000)`, steering −100…100 |
| Steer, measured | `mp.move(amount, unit, speed)` — `unit` ∈ cm / in / rotations / degrees / seconds | `await motor_pair.move_for_degrees(pair, degrees, steering, *, velocity=360, stop=BRAKE, ...)` — **degrees only; no cm/inch units** |
| Tank | `mp.start_tank(l, r)`, `mp.move_tank(l_amt, r_amt, unit, speed)` | `motor_pair.move_tank(pair, left_velocity, right_velocity, *, acceleration=1000)` |
| Calibration | `mp.set_motor_rotation(amount, unit)`, `mp.set_default_speed(speed)` | **No equivalent** — you convert cm→degrees yourself from wheel circumference |

⚠️ For a minesweeper robot doing "drive N cm", Hub OS 3 removes the built-in cm/inch conversion. Budget for a `WHEEL_CIRCUMFERENCE_MM` constant and a `cm_to_deg()` helper.

### Color sensor — reflected light

| Hub OS 2 | Hub OS 3 |
|---|---|
| `cs = ColorSensor('D')`; `cs.get_reflected_light()` → 0–100 % | `color_sensor.reflection(port)` → 0–100 % |
| `cs.get_color()` → color **name string** (e.g. `'red'`) | `color_sensor.color(port)` → **int** to compare against `color.RED`, `color.GREEN`, … from the `color` module |
| `cs.get_rgb_intensity(...)` | `color_sensor.rgbi(port)` → `tuple[r, g, b, intensity]` |

**Trap:** string vs. integer color identity. `if cs.get_color() == 'black'` becomes `if color_sensor.color(port) == color.BLACK`.

### Gyro / yaw

| Hub OS 2 | Hub OS 3 |
|---|---|
| `hub.motion_sensor.get_yaw_angle()` → **degrees** | `motion_sensor.tilt_angles()` → `(yaw, pitch, roll)` in **decidegrees (1/10°)** |
| `hub.motion_sensor.reset_yaw_angle()` | `motion_sensor.reset_yaw(angle)` — takes the new offset explicitly |
| `get_pitch_angle()`, `get_roll_angle()` | unpack from `tilt_angles()` |
| — | `motion_sensor.angular_velocity(raw_unfiltered: bool)` → decidegrees/s; `motion_sensor.acceleration(raw_unfiltered)`; `motion_sensor.set_yaw_face(...)` |

**Trap:** decidegrees. A 90° turn is `900`. SPremote confirms these exact calls against 3.4.3 firmware (`spremote/motion_sensor.py` issues `motion_sensor.tilt_angles()`, `motion_sensor.reset_yaw(0)`, `motion_sensor.angular_velocity(True)`, `motion_sensor.set_yaw_face(...)`).

### 5×5 light matrix

| Hub OS 2 | Hub OS 3 |
|---|---|
| `hub.light_matrix.show_image('HAPPY')` (named images) | `light_matrix.show(pixels)` — a **list of 25 ints, 0–100 intensity** |
| `set_pixel(x, y, brightness)` | `light_matrix.set_pixel(x, y, intensity)` — x,y ∈ 0…4 |
| `write(text)` | `await light_matrix.write(text, intensity=100, time_per_character=500)` |
| `off()` | clear via `show([0]*25)` |

### Timing / async structure — the biggest structural change

**Hub OS 2** is blocking/imperative:

```python
from spike import PrimeHub, MotorPair
from spike.control import wait_for_seconds, wait_until, Timer

hub = PrimeHub()
drive = MotorPair('B', 'C')
drive.move(30, 'cm', speed=40)      # blocks
wait_for_seconds(1)
t = Timer(); wait_until(lambda: t.now() > 3)
```

**Hub OS 3** is `async`/coroutine-based on a cooperative `runloop`:

```python
import runloop, motor_pair, color_sensor
from hub import port, light_matrix

async def main():
    motor_pair.pair(motor_pair.PAIR_1, port.B, port.C)
    await motor_pair.move_for_degrees(motor_pair.PAIR_1, 720, 0, velocity=500)
    await runloop.sleep_ms(1000)
    await runloop.until(lambda: color_sensor.reflection(port.E) < 20)
    await light_matrix.write("OK")

runloop.run(main())
```

- `runloop.run(coroutine, *additional_coroutines)` — runs several coroutines **concurrently**; this is how you get parallel behaviours (drive + sensor watchdog) without threads.
- `runloop.sleep_ms(ms)` replaces `wait_for_seconds(s)` (note: **ms, not s**).
- `runloop.until(condition_fn)` replaces `wait_until(...)`.
- `Timer` is gone; use `time.ticks_ms()` / `time.ticks_diff()` (MicroPython built-ins) — **UNVERIFIED** that `time.ticks_ms` is exposed on Hub OS 3; probe in the REPL.
- Every long-running motor call returns an *Awaitable* and **must be `await`ed** or it returns immediately.

⚠️ **Slot-launcher requirement (Hub OS 2 only):** programs started from the on-brick slot selector *"need to be expressed in coroutines so they can be exited properly"* — `spikeprime-tools` ships `hub/program_template.py` for this ([README](https://github.com/sanjayseshan/spikeprime-tools/blob/master/README.md)). On Hub OS 3 the `async def main()` + `runloop.run(main())` shape covers this natively.

---

## Linux gotchas

### Device node and permissions

- Hub enumerates as CDC-ACM → `/dev/ttyACM0` (check `sudo dmesg | tail` right after plugging in; both the WHZ report and SPremote say exactly this). `python3 -m serial.tools.list_ports -v` also works.
- Owner `root:dialout`. Three fixes, in order of quality:
  1. **udev rule** (survives reboot and reconnect, no group juggling) — see Step 0 above. The minimal community version is `KERNEL=="ttyACM0",MODE="0666"` in `/etc/udev/rules.d/50-myusb.rules`; matching on VID/PID as I do above is strictly better because it won't loosen permissions on unrelated ACM devices.
  2. **`dialout` group** — `sudo adduser $USER dialout`, then log out and back in. *Already satisfied on this machine.*
  3. `sudo chmod 666 /dev/ttyACM0` — must be redone after every reconnect. Avoid.
- A `SYMLINK+="spike"` in the udev rule gives you a stable `/dev/spike` so port renumbering (`ttyACM1`, `ttyACM2`…) stops breaking scripts.

### ModemManager — the classic silent failure

**Symptom** (verbatim from the spikeprime-tools README): *"If the center led of the hub flashes red shortly after connecting and/or you see random characters appearing when manually connecting to the hub via a terminal (something like `ATE1 E0 ~x~`), this likely indicates a modem controller is trying to talk to the hub."*

ModemManager is **active and enabled on this machine right now**, so expect this.

Fixes, weakest to strongest:

```bash
# (a) Nuclear, recommended for a dev box with no cellular modem:
sudo systemctl disable --now ModemManager

# (b) Targeted: tag the device, THEN relax the filter policy — the tag alone is not enough.
#     ModemManager ≥1.14 defaults to --filter-policy=strict, which ignores ID_MM_DEVICE_IGNORE.
sudo mkdir -p /etc/systemd/system/ModemManager.service.d
sudo tee /etc/systemd/system/ModemManager.service.d/override.conf >/dev/null <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/sbin/ModemManager --filter-policy=default
EOF
sudo systemctl daemon-reload && sudo systemctl restart ModemManager
```

The strict-policy caveat is documented in the [ModemManager modem-filter reference](https://www.freedesktop.org/software/ModemManager/doc/latest/ModemManager/ref-overview-modem-filter.html). Note that a `.d/` drop-in is the correct Ubuntu approach — editing `/lib/systemd/system/ModemManager.service` directly (as many blog posts suggest) gets clobbered on package upgrade.

### Serial parameters

- **115200 baud, 8N1**, no hardware flow control needed. Confirmed three ways: LEGO's own web app uses `baudRate: 115200` ([Chrome blog](https://developer.chrome.com/blog/lego-education-spike-web-bluetooth-web-serial)); the VS Code extension opens `new SerialPort({ baudRate: 115200 })`; SPremote uses `serial.Serial(port, 115200, timeout=0.1)`.
- USB CDC ignores the baud rate at the electrical level, but the tools all set it — match it and stop worrying.
- The hub's REPL uses **`\r\n`** line endings and has **autoindent enabled**, which mangles pasted indented blocks. SPremote's `Hub.write()` explicitly replaces `\n` with `\r\n` and warns: *"Due to the interpreter's autoindentation feature this method is not suitable for sending code blocks with indentation."* If you paste multi-line code into the REPL by hand, use **paste mode: `Ctrl+E` … paste … `Ctrl+D`** (standard MicroPython) — **UNVERIFIED** that LEGO left paste mode enabled; test it.

### Entering and leaving the REPL safely

| Action | Keystroke / byte | Effect |
|---|---|---|
| Stop the running program, enter REPL | `Ctrl+C` = `0x03` | Kills the foreground program; prompt becomes `>>> `. Non-destructive |
| Soft reboot back into normal hub behaviour | `Ctrl+D` = `0x04` | MicroPython soft reset; the hub restarts its normal startup program |
| Boot straight to REPL, skip hub program | hold **left button** while powering on | Hub won't respond to buttons or the SPIKE App until rebooted |
| Exit `screen` (leaving hub alone) | `Ctrl+A` then `D` (detach) or `Ctrl+A`, `K`, `Y` (kill) | Detach leaves the session alive holding the port — prefer kill |
| Exit `tio` | `Ctrl+T` then `Q` | |
| Recover a wedged port | power-cycle the hub | SPremote: *"If you experience connection issues (device busy,...) power off the hub and power on again."* |

`Ctrl+C` semantics are confirmed on Hub OS 2 (WHZ report) and Hub OS 3.4.3 (SPremote sends literal `b'\x03'` and waits for `>>> `).

### Program storage and slots

- **20 slots, indexed 0–19** ([LEGO glossary](https://github.com/LEGO/spike-prime-docs/blob/main/docs/source/glossary.rst)). These are what the on-brick selector cycles through.
- **Hub OS 3 upload sequence** (from LEGO's own `examples/python/app.py`): `InfoRequest`(0x00) → `DeviceNotificationRequest`(0x28) → `ClearSlotRequest`(0x46) → `StartFileUploadRequest`(0x0C, carries slot uint8 + CRC32 of the file) → repeated `TransferChunkRequest`(0x10, ≤ `max_chunk_size`) → `ProgramFlowRequest`(0x1E) to start/stop. Program `print()` output returns as `ConsoleNotification`(0x21).
- Framing is **COBS with escaping + CRC32**, per `docs/source/encoding.rst`.
- The extension can **precompile Python to `.mpy`** before upload — smaller and faster to transfer.
- **Hub OS 2** equivalent is JSON-RPC: `spikejsonrpcapispike.py {list,fwinfo,mv,upload,cp,rm,start,stop,display}`.
- Files also live on a plain MicroPython filesystem you can inspect from the REPL with `import os; os.listdir('/')`.

### Download (standalone) vs streaming — two genuinely different architectures

- **Download mode:** upload to a slot, unplug, run from the hub's buttons. Fully autonomous, but every `print()` is invisible unless you're tethered. This is what a competition/field run needs.
- **Streaming/host-driven (SPremote model):** the hub stays tethered and your Ubuntu machine executes the logic, sending short REPL commands and reading results. SPremote's pitch: *"most of the code runs on your (fast) computer, only few commands for controlling motors and reading sensors have to be executed on the (slow) hub block"* — buying you *"much faster programs, programming in your favorite Python IDE, orchestration of multiple hub blocks, seamless integration of other devices like cameras."* For a **minesweeper** project (grid search, path planning, maybe a camera) this is very attractive — but there is a serial round-trip on every sensor read, and the hub is on a leash.
- **Hybrid, and what I'd actually recommend:** develop and tune with SPremote or a tethered REPL, then port the settled control loop into a slot program for the standalone demo.

### Bluetooth on Linux

- `sudo rfcomm connect /dev/rfcomm0 <MAC>` gives an RFCOMM serial device that behaves like `/dev/ttyACM0`; release with `sudo rfcomm release`. Documented for Hub OS 2 (WHZ report).
- ⚠️ On current firmware this is unreliable: *"In principle, bluetooth connections should work, too. At least, they did with older firmware. With current 3.4.3 firmware we were not able to get a reliable connection"* ([SPremote README](https://github.com/jeflem/spremote)). Hub OS 3 moved to a BLE GATT service (`0000FD02-…`), not RFCOMM SPP, which likely explains it.
- **Use USB.** Zero budget, zero pain.

### The SPIKE Web App on Linux specifically

- URL: <https://spike.legoeducation.com/prime/lobby/> (HTTP 200 as of 2026-08-25).
- Chrome/Chromium only — *"It runs in Chromium and Chrome, but not in Firefox. Seems to work on Linux without problems, but only via USB connection"* (WHZ report). Chrome 151 is installed here, so **Web Serial is available**.
- **Web Bluetooth on Linux is the gotcha:** not officially supported and requires `chrome://flags/#enable-experimental-web-platform-features`. Don't rely on it.
- **The app is not cached** — *"users always need to be connected to the Internet for the web app to work"* ([Chrome blog](https://developer.chrome.com/blog/lego-education-spike-web-bluetooth-web-serial)).
- Web Serial shows a **Chrome port-picker dialog** — the page cannot open a port silently. Chrome's own port permission is separate from filesystem permissions, but the underlying `/dev/ttyACM0` still has to be readable by your user, so the udev/dialout work above is a prerequisite even for the web app.
- BLE filter used by the app: `namePrefix: 'GDX'`, optional service `d91714ef-28b9-4f91-ba16-f0d9a604f112` (Chrome blog) — note this differs from the `0000FD02-…` service in LEGO's Hub OS 3 protocol docs, i.e. the blog documents the older app generation.

---

## Excluded options and why

### Pybricks — PERMANENTLY BLACKLISTED (project constraint)

Recorded for completeness only; **do not recommend, do not install.**

- Pybricks **replaces the LEGO firmware** on the hub. Its installation *"works just like a normal LEGO firmware update, which is why restoring the original is so easy"* — but the operative word is *replaces*. This directly violates the project's hard constraint.
- Restoration is possible (`code.pybricks.com` → tools → *Restore official LEGO firmware*, or via the DFU bootloader at <https://dfu.pybricks.com/>), **but the official SPIKE app does not use the DFU bootloader**, so a hub that has been Pybricks-flashed cannot be restored by the SPIKE app alone.
- LEGO does not publish standalone firmware images, so a bad restore has no clean vendor recovery path.
- Everything downstream is excluded too: `pybricksdev`, the "Pybricks Runner" VS Code extension, `code.pybricks.com`, and any tutorial whose first step is "install Pybricks firmware."

### Other exclusions

- **`gpdaniels/spike-prime` firmware tooling** — excellent research notes (STM32F413 target, `firmware.flash_read(...)` dumping), but the repo also covers DFU-level firmware work. Read it; don't run the flashing parts. Last commit 2023-10-24.
- **SPIKE-RT** — a real-time C/RTOS environment for the hub. Same disqualifier: it is alternative firmware.
- **`XenseEducation/spiketools-release`** — last touched 2021-01-28. Dead.
- **Wine + the Windows SPIKE App** — surfaces in forum threads; USB passthrough for a CDC device through Wine is fragile and adds nothing over the Chrome web app, which is natively supported. Not pursued.
- **The macOS/Windows/iPad/Android desktop apps** — no Linux build exists on LEGO's [download page](https://education.lego.com/en-us/downloads/spike-app/software/) (Mac OS, Windows 10, iPad, Android, Chromebook only).

---

## Open questions

These need the physical hub and should be resolved in one 20-minute bench session before any code is written:

1. **Which Hub OS is actually on the unit?** Run the passive idle-traffic test (B) first, then the REPL probe (C). Record the exact `InfoResponse` firmware triple.
2. **UNVERIFIED — `os.uname()` / `hub.info()` / `help(hub)` output on Hub OS 3.** No source I fetched shows Hub OS 3 output for any of these. Capture and paste into this doc.
3. **UNVERIFIED — MicroPython paste mode (`Ctrl+E`/`Ctrl+D`) availability on the LEGO REPL.** Determines whether hand-pasting indented code into `tio` is viable.
4. **UNVERIFIED — `time.ticks_ms()` / `time.ticks_diff()` on Hub OS 3** as the `spike.control.Timer` replacement.
5. **UNVERIFIED — whether the *web* app's update prompt is as hard as the *desktop* app's.** LEGO's "cannot be disabled" language is about "the app" generically; I found no separate statement for the browser version. Assume it is equally hard until proven otherwise.
6. **UNVERIFIED — whether Hub OS 3 exposes a USB VCP object to on-hub programs** (Hub OS 2 had `hub.USB_VCP()` / `hub.BT_VCP()` for hub→host messaging). This matters if we want bidirectional telemetry from a slot program.
7. **Does the VS Code extension's USB path work unmodified on Ubuntu 22.04?** It uses the native `serialport` node module; prebuilt binaries usually exist for linux-x64, but confirm the extension host doesn't need a rebuild.
8. **Downgrade escape hatch:** <https://spikelegacy.legoeducation.com/hubdowngrade/> and <https://spike.legoeducation.com/hubdowngrade> both return HTTP 200. Both are Chrome+USB tools. LEGO/RoboCamp caution that repeatedly switching OS *"may damage the hub"* — treat as one-way, last resort.
9. **Motor/wheel calibration constants** for cm↔degrees on Hub OS 3, since `set_motor_rotation` no longer exists.

---

## Sources

Every URL below was fetched or queried on 2026-08-25.

**Official LEGO**
- LEGO SPIKE Prime protocol reference (Hub OS 3, BLE/COBS): https://lego.github.io/spike-prime-docs/
- LEGO/spike-prime-docs repository (main-branch last commit 2024-03-04; repo `pushed_at` 2025-09-29): https://github.com/LEGO/spike-prime-docs
- Glossary — 20 program slots, 0–19: https://github.com/LEGO/spike-prime-docs/blob/main/docs/source/glossary.rst
- SPIKE Prime software & firmware updates (mandatory update notification): https://education.lego.com/en-us/product-resources/spike-prime/downloads/software-updates/
- SPIKE Prime system requirements (no Linux): https://education.lego.com/en-us/product-resources/spike-prime/downloads/system-requirements/
- SPIKE App downloads (no Linux build): https://education.lego.com/en-us/downloads/spike-app/software/
- SPIKE Prime troubleshooting FAQs (hub light colours): https://education.lego.com/en-au/product-resources/spike-prime/troubleshooting/faqs/
- LEGO Education Partner Portal — troubleshooting / hub OS & light colours: https://legoeducation.atlassian.net/wiki/spaces/LPP/pages/36814651433
- SPIKE App 3.4.2 release notes: https://legoeducation.atlassian.net/servicedesk/customer/portal/3/article/37122311027
- SPIKE Web App (Prime lobby): https://spike.legoeducation.com/prime/lobby/
- Hub downgrade tools: https://spikelegacy.legoeducation.com/hubdowngrade/ and https://spike.legoeducation.com/hubdowngrade

**Protocol / browser**
- "How LEGO Education uses the Web Bluetooth and the Web Serial APIs", Chrome for Developers, 2023-05-22 (115200 baud, USB VID 1684): https://developer.chrome.com/blog/lego-education-spike-web-bluetooth-web-serial

**Linux specifics**
- Jens Flemming, *Host-hub communication for LEGO Spike Prime on Linux*, Zwickau University of Applied Sciences, Oct 2022, DOI 10.34806/3wp9-0991 (PDF): https://libdoc.whz.de/opus4/files/15400/lego_spike_linux.pdf
- Same report, HTML: https://www2.htw-dresden.de/~fjeme691/flemming/blog/lego_spike_linux.html
- ModemManager modem filter / `--filter-policy` reference: https://www.freedesktop.org/software/ModemManager/doc/latest/ModemManager/ref-overview-modem-filter.html

**Maintained tooling (stock firmware)**
- PeterStaev/lego-spikeprime-mindstorms-vscode — v3.1.3, last commit 2025-08-29, Apache-2.0: https://github.com/PeterStaev/lego-spikeprime-mindstorms-vscode
- Marketplace listing: https://marketplace.visualstudio.com/items?itemName=PeterStaev.lego-spikeprime-mindstorms-vscode
- jeflem/spremote — last commit 2026-02-04, GPL-3.0, tested on Hub OS 3.4.3: https://github.com/jeflem/spremote
- SPremote HTML docs (API + examples): https://www2.htw-dresden.de/~fjeme691/spremote

**Legacy / abandoned tooling (Hub OS 2)**
- sanjayseshan/spikeprime-tools — last commit 2022-08-02 (ModemManager + dialout guidance, JSON-RPC CLI): https://github.com/sanjayseshan/spikeprime-tools/blob/master/README.md
- sanjayseshan/spikeprime-vscode — last commit 2022-12-30: https://github.com/sanjayseshan/spikeprime-vscode
- smr99/lego-hub-tk — last commit 2022-02-03: https://github.com/smr99/lego-hub-tk
- nutki/spike-tools — last commit 2020-02-13: https://github.com/nutki/spike-tools
- LEGO-Robotics/SPIKEPrime-Tools — last commit 2021-12-26: https://github.com/LEGO-Robotics/SPIKEPrime-Tools
- XenseEducation/spiketools-release — last commit 2021-01-28: https://github.com/XenseEducation/spiketools-release

**API references**
- SPIKE 3 Python reference (Tufts CEEO mirror of LEGO's help docs): https://tuftsceeo.github.io/SPIKEPythonDocs/SPIKE3.html
- SPIKE 2 / legacy `spike` package reference: https://tuftsceeo.github.io/SPIKEPythonDocs/SPIKE2.html
- LEGO Spike Python API v3 (autogenerated from spike.legoeducation.com help docs): https://jvolkening.github.io/lego-spike-python-v3-docs/index.html
- LEGO official Python help (SPIKE app 3): https://spike.legoeducation.com/prime/help/lls-help-python

**Background / excluded**
- gpdaniels/spike-prime — firmware research, last commit 2023-10-24, MIT: https://github.com/gpdaniels/spike-prime/blob/master/firmware/README.md
- RoboCamp, "SPIKE app: when to update and how to downgrade": https://www.robocamp.eu/en/blog/lego-spike-app-update/
- Pybricks installation (replaces LEGO firmware) — **excluded**: https://pybricks.com/learn/getting-started/install-pybricks/
- Pybricks DFU / hub troubleshooting — **excluded**: https://dfu.pybricks.com/
- primelessons.org, "MicroPython on SPIKE Prime" (Hub OS 2 era): https://primelessons.org/en/ProgrammingLessons/MicroPythonIntro.pdf
