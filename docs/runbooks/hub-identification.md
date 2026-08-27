# Runbook — Hub Identification (READ-ONLY FIRST CONTACT)

> **Purpose.** Determine which **LEGO Hub OS / Python API generation** is on the SPIKE Prime hub
> **without changing anything on the hub** and **without triggering a "Hub update required" prompt**.
> **Status: EXECUTED 2026-08-27.** Written 2026-08-25 with no hub attached; run for real on our own hub
> over USB on 2026-08-27, and revised the same day against what it actually printed. The result is filed
> as [../findings/hub-first-contact-2026-08-27.md](../findings/hub-first-contact-2026-08-27.md).
> Host-side facts measured 2026-08-25 are marked *(verified 2026-08-25)*; hub-side claims now say either
> **CONFIRMED 2026-08-27** or **`UNVERIFIED`**, and **three predictions this runbook made turned out to
> be WRONG** — they are marked ❌ **PREDICTION WRONG** in place rather than quietly corrected, because a
> wrong prediction on the record is worth more than a tidy table (§ 5.5, § 5.7, § 6).
>
> **Everything below refers to the port as `/dev/spike`**, the stable symlink created by
> `scripts/setup-host.sh`. On this host it points at `ttyACM0`; use the symlink, because the number
> moves.
>
> Governing rules: [../directives/hardware-safety.md](../directives/hardware-safety.md) ·
> [../directives/honest-instrumentation.md](../directives/honest-instrumentation.md) ·
> [../decisions/0001-stock-lego-firmware-only.md](../decisions/0001-stock-lego-firmware-only.md)
> Toolchain background (written in parallel, will refine this file — do not duplicate it here):
> [../research/spike-prime-linux-toolchain.md](../research/spike-prime-linux-toolchain.md)

**Why this matters.** The whole codebase forks on the answer. SPIKE 3 (current) is
`import motor` / `from hub import port` / `import runloop`; SPIKE 2 (legacy) is
`from spike import PrimeHub`. [../scope.md](../scope.md) used to list the generation as `[UNKNOWN]` and
forbids writing mission code against a guess. **This runbook closed that unknown on 2026-08-27: our hub
is SPIKE 3** (KU-M1 in [../plans/known-unknowns.md](../plans/known-unknowns.md)). It closes that, and
nothing else — the API being *known* is not the same as its call sites being *run*.

---

## 0. FORBIDDEN in this procedure — read before you plug anything in

Nothing in this session writes to the hub. If a step seems to require any of the following, **STOP and
ask the operator**; do not improvise.

| Forbidden | Why |
|---|---|
| Accepting **any** "Hub update required" / "Update Hub OS" prompt | Changes the hub's software state. That is an operator decision recorded as an ADR, never a side effect. **STOP.** |
| Opening the LEGO SPIKE App or SPIKE Web App at all during this procedure | It negotiates Hub OS compatibility on connect and is the most likely source of an update prompt. It also seizes the serial port. |
| Pybricks, `pybricksdev`, or any third-party firmware tool | Blacklisted permanently — it flashes the hub. [ADR-0001](../decisions/0001-stock-lego-firmware-only.md) |
| DFU mode, bootloader entry, filesystem format, factory reset | One-way door on shared course equipment |
| Any filesystem write on the hub: `open(..., 'w')`, `os.remove`, `os.rename`, `os.mkdir`, `os.rmdir` | We do not know what is on the hub yet |
| Any firmware/reset call: `hub.reset()`, `machine.reset()`, `machine.bootloader()`, anything named `update`, `flash`, `erase`, `format` | Same |
| Uploading, deleting, or overwriting a program slot | Not identification. That is the deploy runbook's job, later. |
| Running a motor | Not identification. The Builder is the only authorized operator of a moving robot. |
| An **agent** opening a blocking serial read from a tool call (`screen`, `cat /dev/ttyACM0`, a `read()` with no deadline) | Hangs the session. Hard rule — [../directives/automation-first.md](../directives/automation-first.md). See § 6. |

**One addition, 2026-08-27.** Writing to the hub is no longer a hypothetical escalation of this
procedure — it is a **different, existing procedure** with its own runbook,
[deploy-to-hub.md](./deploy-to-hub.md), and its own proof that the firmware is untouched
([../findings/firmware-integrity-proof.md](../findings/firmware-integrity-proof.md)). Nothing in the
table above is relaxed: *this* procedure still writes nothing. If you want to write, leave this runbook
and open that one.

**Allowed:** reading USB/kernel/port state on the host; sending short expressions to the hub's
MicroPython REPL that only *read* (`sys`, `os.uname()`, `help('modules')`, `dir()`, version and
battery attributes). Executing a read-only expression at the REPL leaves no file behind.

---

## 1. Before connecting — clear the field

| # | Do | Expected |
|---|---|---|
| 1.1 | Close the **LEGO SPIKE App** and every **SPIKE Web App** browser tab. Close Chrome entirely if unsure. | Neither is running |
| 1.2 | Verify nothing is holding a Chrome WebSerial session: `pgrep -a chrome \| head` | Empty, or clearly unrelated windows |
| 1.3 | Confirm no old serial terminal is alive: `screen -ls; pgrep -a screen; pgrep -a minicom; pgrep -a picocom` | `No Sockets found` / no matches |

**Why 1.1 is first and not optional:** a connected SPIKE app is the single most likely way to get an
unattended update prompt, and Chrome's WebSerial holds `/dev/ttyACM0` **exclusively** — if a tab has
the port, every command below fails with "device busy" and the failure looks like a hardware fault.

---

## 2. Connect over USB and confirm Linux enumerates the hub

Plug the hub into the host with the USB cable and switch the hub on. Per the course role rules, the
**Programmer** is the only person besides the Builder permitted to plug/unplug the robot
([../scope.md](../scope.md) § Critical Notes).

| # | Command | Expected observation |
|---|---|---|
| 2.1 | `lsusb` | A new line for the hub. Vendor **LEGO Group / `0694`**, product `0009` — **confirmed indirectly 2026-08-27**, see the note below. Record the line verbatim anyway; a transcribed `lsusb` line is stronger evidence than an inference. |
| 2.2 | `ls -l /dev/spike /dev/ttyACM*` | `crw-rw---- 1 root dialout 166, 0 … /dev/ttyACM0`. Major **166** is the `cdc_acm` char major *(verified from `modinfo cdc_acm`: `alias char-major-166-*`, 2026-08-25)*. Group **must** be `dialout`. |
| 2.3 | `sudo dmesg \| tail -n 40` | Lines of the shape `usb 1-…: new full-speed USB device number N using xhci_hcd`, `cdc_acm 1-…:1.0: ttyACM0: USB ACM device`. The `cdc_acm … ttyACM0: USB ACM device` line is the signature. |
| 2.4 | `udevadm info -q property -n /dev/spike` | `ID_VENDOR_ID`, `ID_MODEL_ID`, `ID_SERIAL`, `ID_USB_DRIVER=cdc_acm`. **Record all of these** — they are what a future udev rule keys on. |

**On the VID:PID, 2026-08-27 — confirmed by inference, not by a transcribed `lsusb` line.** The udev
rule `scripts/setup-host.sh` installs at `/etc/udev/rules.d/99-lego-spike.rules` matches
**`ATTRS{idVendor}=="0694", ATTRS{idProduct}=="0009"`** and nothing else, and its `SYMLINK+="spike"`
fired: `/dev/spike -> ttyACM0` exists on this host. A rule that matches only `0694:0009` cannot create
that symlink for a device that is not `0694:0009`. So the ID is **confirmed against our unit** — but
via the rule, not by reading it off `lsusb`. Anyone with the hub plugged in should still paste the real
`lsusb` line into the finding and upgrade this from *confirmed against `99-lego-spike.rules`* to
*measured*. Vocabulary: [../lessons_learned/say-which-kind-of-verified.md](../lessons_learned/say-which-kind-of-verified.md).

Notes, measured on this host **2026-08-25**:

- `sudo` on 2.3 is **required here**: `kernel.dmesg_restrict = 1`, and unprivileged `dmesg` fails with
  `read kernel buffer failed: Operation not permitted` *(verified)*.
- The user is **already in `dialout`** — `id` returns `…,20(dialout),…` *(verified)*. So **no `sudo`
  is needed to open the port**, and none should be used. `sudo screen /dev/ttyACM0` (as suggested in
  the operator's raw notes, [../archives/operator-notes/2026-08-25_spike-platform-notes.md](../archives/operator-notes/2026-08-25_spike-platform-notes.md)) leaves root-owned lock files and root screen
  sessions behind; do not use it.
- Baseline with **no hub attached** *(verified 2026-08-25)*: `/dev/ttyACM*` does not exist. So the
  appearance of `ttyACM0` is by itself evidence the hub enumerated.
- If `ttyACM0` does **not** appear: try the other USB port and a different cable (many LEGO USB cables
  are charge-only) before concluding anything about the hub. A charge-only cable produces **no**
  `lsusb` line at all.

---

## 3. ModemManager — check and mitigate before opening the port

ModemManager probes newly-appeared `ttyACM` devices to see whether they are cellular modems. Its probe
writes AT-command bytes to the port. On a MicroPython REPL that garbage arrives as keystrokes and can
corrupt the first seconds of a session or leave the port busy.

Measured on this host *(verified 2026-08-25)*:

```
systemctl is-active ModemManager   → active
systemctl is-enabled ModemManager  → enabled
mmcli --version                    → mmcli 1.20.0
/usr/lib/udev/rules.d/80-mm-candidate.rules  present
```

**⚠ Those rows are STALE for this host as of 2026-08-27.** `./scripts/setup-host.sh --apply` was run
before the first hub session: ModemManager is now **`inactive` and disabled**, and the udev rule sets
`ID_MM_DEVICE_IGNORE=1` on the device. Re-measure rather than trust either set of rows if the host
changes. The blocker itself is filed as
[../findings/host-environment.md](../findings/host-environment.md).

**And the probe question is answered, 2026-08-27:** with the hub plugged in, `mmcli -L` returned
**`No modems were found`** and nothing held the port. **ModemManager had not in fact grabbed this
device.** The mitigation is still correct and stays applied — it is a race we do not want to re-run
every session, and losing a class period to a corrupted first session is the failure it prevents. What
changes is the honest claim: this is a *precaution whose necessity is unproven on this host*, not a
fault we observed.

| # | Check | Expected / meaning |
|---|---|---|
| 3.1 | `systemctl is-active ModemManager` | **`inactive` on this host since 2026-08-27** (was `active`/`enabled`). `active` on a fresh host |
| 3.2 | Right after plugging in: `mmcli -L` | `No modems were found` = ModemManager ignored the hub, **nothing further needed**. Any listed modem on `ttyACM0` = it grabbed the port. |
| 3.3 | `sudo journalctl -u ModemManager -n 30 --no-pager` | Any line naming `ttyACM0` or `0694:0009` = it probed the device |
| 3.4 | `sudo fuser -v /dev/spike` (or `sudo lsof /dev/spike`) | **No output** = nobody holds the port. A `ModemManager` line = it holds it. |

**Non-destructive mitigation, in order of preference — only if 3.2/3.4 show interference:**

1. **Preferred, permanent, targeted — a udev ignore rule** for the hub's VID only, using the
   `ID_VENDOR_ID` recorded in step 2.4:

   ```bash
   # /etc/udev/rules.d/99-lego-spike-no-modemmanager.rules
   SUBSYSTEM=="tty", ATTRS{idVendor}=="0694", ENV{ID_MM_DEVICE_IGNORE}="1"
   ```
   ```bash
   sudo udevadm control --reload-rules && sudo udevadm trigger
   # unplug and replug the hub, then re-check:
   mmcli -L
   ```
   This touches **only the host**, never the hub, and affects only LEGO devices.
   **Confirmed 2026-08-27:** the vendor ID `0694` (product `0009`) matches our unit — see the note in
   § 2. `scripts/setup-host.sh` now installs a superset of this rule at
   `/etc/udev/rules.d/99-lego-spike.rules`, which also sets `GROUP="dialout"` and `SYMLINK+="spike"`;
   prefer running the script over hand-writing this file. **Still `UNVERIFIED`:** that the rule
   *suppresses probing* for this device — untestable here, because `mmcli -L` found no modem either
   way.

2. **Session-scoped fallback:** `sudo systemctl stop ModemManager`, run the identification, then
   `sudo systemctl start ModemManager`. Reversible, but it disables any real modem on the machine for
   the duration. Do not `disable` it.

3. **Do not** delete files from `/usr/lib/udev/rules.d/` or uninstall ModemManager.

**Also worth knowing:** `brltty` is installed on this host but **inactive** *(verified 2026-08-25:
`systemctl is-active brltty` → `inactive`, package `brltty 6.4-4ubuntu3`)*. It is a well-known
grabber of `ttyACM` devices when running. If step 3.4 ever names `brltty`, the same
session-scoped stop applies.

---

## 4. Reach the hub's MicroPython REPL — read-only

**CONFIRMED 2026-08-27 — this was the central assumption of the runbook and it held.** The stock
firmware on *our* hub exposes an ordinary interactive MicroPython REPL on `/dev/spike`. A `>>>` prompt
was reached, plain-text, and every probe in § 5 ran through it. A SPIKE 3-generation Hub OS does
**not** hide the REPL behind a framed binary protocol — that worry is retired. The
`UNVERIFIED` markers that used to stand here are struck.

**What you may see on the port and what it means:**

| Observation after connecting + `Ctrl-C` | Reading |
|---|---|
| A `>>>` prompt | REPL available. Continue to § 5. |
| Continuous binary/garbage bytes, no prompt | The hub is streaming its status protocol. **Not a fault.** Send `Ctrl-C` again; if still no prompt, stop and record the observation as the finding. |
| Nothing at all | Port opened but hub silent. Try `Ctrl-C` then `Enter`. If still nothing, record UNKNOWN — **do not** escalate to anything that writes. |
| `Device or resource busy` | Something holds the port — go back to § 1 and § 3.4. |

Serial settings: **115200 8N1 — CONFIRMED working 2026-08-27** on this hub (the baseline captures carry
the header `# port /dev/spike @ 115200 8N1`). CDC ACM devices generally ignore the baud rate anyway, so
it is a safe default either way.

### 4a. The human route (physical terminal only)

A person sitting at the machine may use `screen /dev/spike 115200` (no `sudo`). **An agent may not**
— see § 6. Exit procedure is in § 7.

### 4b. The required route for anything scripted — § 6

---

## 5. What to type, and what each answer means

Send these one at a time and **record the output verbatim**, including error text. An exception is a
result, not a failure — `ImportError: no module named 'spike'` is *evidence*.

| # | Type at `>>>` | What it tells us |
|---|---|---|
| 5.1 | `import sys; print(sys.implementation)` | Confirms MicroPython and gives its version, e.g. `(name='micropython', version=(1,x,y))`. Indicative of generation only — **do not decide on this alone**. |
| 5.2 | `import os; print(os.uname())` | `sysname` / `release` / `version` / `machine`. `machine` should name the board; `version` usually carries a build string/date. **This is the firmware fingerprint to file.** |
| 5.3 | **`help('modules')`** | **The discriminator.** See the decision table below. |
| 5.4 | `import hub; print(hub.__name__); print(dir(hub))` | `dir()` is read-only. The *shape* of the `hub` module differs between generations. |
| 5.5 | `print(hub.info())` — only if `info` appeared in 5.4 | ❌ **PREDICTION WRONG (2026-08-27): `info` is NOT in `dir(hub)` on this hub.** There is no `hub.info()`. The version fingerprint comes from `os.uname()` and `sys.implementation` (5.1/5.2) instead. Left in the table on purpose: skipping this row is the *correct* behaviour the row itself prescribed, and a recorded wrong prediction is worth more than a deleted one. |
| 5.6 | `import sys; print(sys.path)` | Where the hub looks for modules. Read-only, and useful later for deploy. |
| 5.7 | Battery — **use the measured form:** `print(hub.battery_voltage(), hub.battery_current(), hub.battery_temperature(), hub.usb_charge_current)` | ❌ **PREDICTION WRONG (2026-08-27): BOTH forms this row originally offered are wrong.** There is no `hub.battery` object and no importable `battery` module. The real calls are **top-level attributes of `hub`**: `battery_voltage()`, `battery_current()`, `battery_temperature()`, and the *attribute* (not call) `usb_charge_current`. Measured: **7882 mV charging at 364 mA**; a later session read **7942 → 8001 mV** while charging over USB. [demo-day.md](./demo-day.md) still needs the *threshold*, which is a different question and remains open. |

### Decision table — SPIKE 2 vs SPIKE 3

| Evidence from `help('modules')` (5.3) / `dir(hub)` (5.4) | Conclusion | Consequence for the code |
|---|---|---|
| `spike`, `mindstorms`, `hub` present; **no** `runloop` | **SPIKE 2 / legacy API** | Mission code targets `from spike import PrimeHub`. Most of LEGO's *current* teaching material does not apply. |
| `motor`, `motor_pair`, `runloop`, `color_sensor`, `distance_sensor`, `force_sensor` present | **SPIKE 3 / current API** ← ✅ **THIS IS OUR HUB, matched exactly 2026-08-27** | Mission code targets `import motor` / `from hub import port` / `import runloop`. |
| **Both** families present | Ambiguous — a compatibility shim. **Do not guess.** Record verbatim, ask the operator, and prefer the current API. | ADR needed |
| No REPL reached at all | **UNKNOWN — the honest answer.** File it as UNKNOWN. | Blocked; the toolchain research file becomes the next move |

**CONFIRMED 2026-08-27 for the SPIKE 3 row — struck, not softened.** Our hub's `help('modules')` listed
`motor`, `motor_pair`, `runloop`, `color_sensor`, `distance_sensor`, `force_sensor`, and **no `spike`
module and no `mindstorms` module**. The row matched exactly. The complete verbatim list is in
[../archives/hub-baseline/02-modules.txt](../archives/hub-baseline/02-modules.txt) and the reading is in
[../findings/hub-first-contact-2026-08-27.md](../findings/hub-first-contact-2026-08-27.md).

The **SPIKE 2 row remains `UNVERIFIED`** — we have never seen a SPIKE 2 hub, and its module names are
still only what [../research/spike-prime-linux-toolchain.md](../research/spike-prime-linux-toolchain.md)
predicts. On a *different* hub, record what it actually prints rather than what this table says.

---

## 6. This must run from a script with a timeout — not an interactive read

**Hard rule.** An agent tool call that opens `/dev/spike` and waits for bytes hangs the session with
no way out. Every hub-touching command goes in a script that has an explicit deadline and exits.

❌ **PREDICTION WRONG (2026-08-27) — the text that used to stand here said `scripts/identify_hub.py`
and `scripts/identify-hub.sh` did not exist and that creating them was "outside this runbook's write
zone". They exist, and they ran.** This section is now a **pointer**, not a specification.

| What runs | Wrapped by | What it does |
|---|---|---|
| `scripts/identify_hub.py` | `scripts/identify-hub.sh` | The read-only identification sequence in § 5. Produced the `_hub-identify-*.transcript.txt` filed in [../findings/](../findings/INDEX.md) |
| `probes/whoami.py` | — | Identity: `device_uuid`, `hardware_id`, `machine.unique_id()`, battery |
| `probes/identify_hub.py` | — | `os.uname()`, `sys.implementation`, `help('modules')`, `dir(hub)` |
| `probes/filesystem.py` | — | `/flash` listing, sizes, `os.statvfs`, stock file contents |
| `probes/capture_baseline.py` | — | All of the above into [../archives/hub-baseline/](../archives/hub-baseline/INDEX.md) as a re-runnable, diffable snapshot |

**Prefer `probes/capture_baseline.py --to /tmp/now` over re-typing the probes.** It produces six files
that diff against the pristine 2026-08-27 baseline, which is how *"did anything on this hub change?"*
gets **answered** instead of argued about — see
[../findings/firmware-integrity-proof.md](../findings/firmware-integrity-proof.md).

The shape they were written to, kept because it is still the specification any future hub-touching
script must satisfy:

```python
#!/usr/bin/env python3
# READ-ONLY hub identification. Writes nothing to the hub.
# Host has pyserial 3.5 (verified 2026-08-25).
import sys, time, serial          # serial.Serial(..., timeout=...) never blocks forever

PORT, BAUD, DEADLINE = "/dev/spike", 115200, 25.0     # seconds, whole run

PROBES = [                        # read-only expressions ONLY -- see section 0 FORBIDDEN
    "import sys; print(sys.implementation)",
    "import os; print(os.uname())",
    "help('modules')",
    "import hub; print(dir(hub))",
    "import sys; print(sys.path)",
]

# 1. open with BOTH read and write timeouts; never a bare read()
# 2. send b"\x03" (Ctrl-C) to interrupt whatever is running, wait, drain
# 3. for each probe: write(probe + "\r\n"), then read_until(b">>>") under a per-probe deadline
# 4. append everything received to a transcript, verbatim, decoded errors="replace"
# 5. close the port in a finally: block  -- ALWAYS
# 6. print the transcript to stdout and save it; exit 0 if a ">>>" was ever seen, 2 otherwise
#    (exit 0 must mean "we observed a prompt", never merely "no exception")
```

```bash
#!/usr/bin/env bash
# scripts/identify-hub.sh -- the only entry point an agent invokes
set -euo pipefail
[ -e /dev/spike ] || { echo "UNKNOWN: /dev/spike absent -- hub not enumerated"; exit 3; }
timeout --signal=INT 45 python3 "$(dirname "$0")/identify_hub.py" \
  | tee "docs/findings/_hub-identify-$(date +%Y%m%dT%H%M%S).transcript.txt"
```

Rules the script must honour:

- **Belt and braces:** a per-read timeout in pyserial **and** an outer `timeout(1)`. Either alone
  eventually fails to save you.
- **An absent port returns UNKNOWN, never pass** — [../directives/honest-instrumentation.md](../directives/honest-instrumentation.md).
- **Assert a known-correct observation** (a `>>>` was seen), not exit code 0.
- **Idempotent and read-only.** Running it twice changes nothing, on the host or on the hub.
- No `except:` that swallows a failure into a green result.

---

## 7. Exit cleanly — do not leave the port locked

| Route used | Exit |
|---|---|
| `scripts/identify-hub.sh` | Nothing to do; the script closes the port in `finally` and exits. Confirm with 7.3. |
| `screen` (human at the machine) | **`Ctrl-A`** then **`k`**, answer `y`. **Not** `Ctrl-A d` — that detaches and keeps the port held. |
| A `screen` you already detached | `screen -ls` → `screen -X -S <session-id> quit` |
| ModemManager was stopped in § 3 | `sudo systemctl start ModemManager` |

| # | Final checks | Expected |
|---|---|---|
| 7.1 | `screen -ls` | `No Sockets found` |
| 7.2 | `ls /var/lock/LCK..ttyACM0 2>/dev/null` | No such file (the lock file is named for the real node, not for the `/dev/spike` symlink) |
| 7.3 | `sudo fuser -v /dev/spike` | No output — nobody holds the port |
| 7.4 | Unplug the hub, power it off, return it to the yellow box | Course rule: supplies live in the yellow box between classes |

Leaving a lock file or a detached `screen` behind is the most common way the *next* session concludes
"the hub is broken". Check 7.1–7.3 every time.

---

## 8. RESULT — fill this in, then file it as a finding

> ✅ **Filled in and filed for our hub on 2026-08-27 as
> [../findings/hub-first-contact-2026-08-27.md](../findings/hub-first-contact-2026-08-27.md).**
> ❌ **PREDICTION WRONG:** this section used to name the file `docs/findings/hub-os-identification.md`.
> That file does not exist and **must not be created** — a second identification finding is how a repo
> ends up with two answers. The block below stays for a *different* hub, or for a re-run after any
> hardware change.

Copy this block, fill every row (`UNKNOWN` is a valid, honest answer), and file it under
[../findings/](../findings/INDEX.md) with a row added to
[../findings/INDEX.md](../findings/INDEX.md). Then update [../scope.md](../scope.md) § Assumptions —
strike the `[UNKNOWN]` API-generation line — and the roadmap's M1 checkbox.

```text
HUB IDENTIFICATION RESULT
Date / time:              ____________________   Operator: ____________________
Host:                     Ubuntu 22.04.5 LTS, Python 3.10.12, pyserial 3.5
Hub powered from:         [ ] battery   [ ] USB
Route used:               [ ] scripts/identify-hub.sh   [ ] screen (human)

ENUMERATION
lsusb line (verbatim):    ____________________________________________
ID_VENDOR_ID / ID_MODEL_ID: ______________ / ______________
Device node + perms:      ____________________________________________
cdc_acm dmesg line:       ____________________________________________

INTERFERENCE
ModemManager active?      [ ] yes  [ ] no      mmcli -L result: ______________
Mitigation applied:       [ ] none needed  [ ] udev ignore rule  [ ] stopped for session
fuser /dev/spike:         ____________________

REPL
Prompt reached?           [ ] yes  [ ] no  →  if no, STOP; the result below is UNKNOWN
sys.implementation:       ____________________________________________
os.uname():               ____________________________________________
help('modules') output:   (attach transcript path) ______________________
dir(hub):                 ____________________________________________
Battery reading + form:   ____________________________________________

CONCLUSION
API generation:           [ ] SPIKE 3 (current)  [ ] SPIKE 2 (legacy)  [ ] AMBIGUOUS  [ ] UNKNOWN
Evidence it rests on:     ____________________________________________
Update prompt encountered? [ ] no   [ ] YES → STOPPED, nothing accepted, operator informed
Anything written to hub?  [ ] NO (required answer for THIS procedure -- writing
                          is docs/runbooks/deploy-to-hub.md, a different one)
Transcript file:          ____________________________________________
```

---

## 9. If anything asks to update — STOP

Any prompt, banner, or tool message about updating the Hub OS / firmware ends this procedure
immediately: **do not accept, do not dismiss-and-retry, do not "try the other cable".** Disconnect,
write down the exact wording, and give it to the operator. A Hub OS change is an ADR, not a click.

**Sources:** [../directives/hardware-safety.md](../directives/hardware-safety.md) ·
[../decisions/0001-stock-lego-firmware-only.md](../decisions/0001-stock-lego-firmware-only.md) ·
[../research/spike-prime-linux-toolchain.md](../research/spike-prime-linux-toolchain.md) ·
operator platform notes [../archives/operator-notes/2026-08-25_spike-platform-notes.md](../archives/operator-notes/2026-08-25_spike-platform-notes.md) · host measurements taken on this machine 2026-08-25 ·
**the result of actually running this runbook: [../findings/hub-first-contact-2026-08-27.md](../findings/hub-first-contact-2026-08-27.md)** ·
writing to the hub is a different procedure: [deploy-to-hub.md](./deploy-to-hub.md).
