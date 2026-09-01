# The Hub OS runs the button, the radio, and the USB protocol — Ctrl-C kills all three

**Date:** 2026-09-01 · **Source:** the operator: *"when I press the BLE button nothing happens, I
have to restart the hub again, what is causing this? we need to figure it out… this is a lessons
learned moment."*

**WHEN** you want the hub's Bluetooth — the CONNECT button, advertising, a BLE connection —

**DON'T** interrupt the LEGO Hub OS first. Every REPL probe in this repo opens by sending **Ctrl-C**
(`0x03`) to force a MicroPython prompt, and **Ctrl-C interrupts the Hub OS.**

**BECAUSE** the CONNECT button, the BLE stack, *and* the USB control-protocol responder are all
**Hub OS services**. Interrupt the Hub OS and all three go dead at once — the button does nothing, the
hub will not advertise, and the control protocol stops answering — **and it does not recover on its
own. Only a restart brings it back.**

## How we know — the observation that confirmed it

| State | control protocol over USB (no Ctrl-C) | CONNECT button |
|---|---|---|
| Fresh boot, Hub OS running (`harvest.py` **phase 1**) | **answered** — DeviceUuidResponse | works |
| After any REPL probe sent Ctrl-C (`harvest.py` phase 2, `usb_protocol.py` after) | **silent** | dead |

Corroborated by `probes/hub_os_state.py` on 2026-08-27: after probing, the 5×5 matrix read all-zero
and `sys.modules` held only our uploaded `config` — the Hub OS was not running. The button
(`hub.button.CONNECT`) is a Hub OS function, so with the Hub OS gone there is nothing to answer it.

## The correction this forced — and it is a correction of a correction

On 2026-08-27 this project first hypothesised "USB probing suppresses BLE", then **retracted** it,
arguing: *a 120 s BLE scan with nothing touching the serial port still saw nothing, so if probing were
the cause, leaving the port alone should have restored advertising.*

**That retraction was wrong, and the reasoning was the flaw.** It assumed the Hub OS would
*self-recover* if left alone. It does not — once interrupted it stays down until a restart. So the
120 s of silence was fully consistent with the original hypothesis, not evidence against it. The
lesson inside the lesson: **"left it alone and nothing changed" only disproves a cause if the system
can recover on its own. Confirm that assumption before you lean on it.**

The original hypothesis is now the confirmed one. `docs/research/ble-bring-up.md` carries the
un-retraction with this same evidence.

## The fix

The operator asked whether we should *"specify to always enable bluetooth."* **That would not help,
and here is why:** `hub.config["hub_os_enable"] = True` in `/flash/boot.py` already enables the Hub OS
at every boot. The Hub OS is not disabled — we are **interrupting it after boot**. Editing `boot.py`
changes nothing about that (and `boot.py` is the one genuinely dangerous file on the hub —
[ADR-0001](../decisions/0001-stock-lego-firmware-only.md)). So:

1. **If you need Bluetooth, do not drop to the REPL.** Talk the **LEGO control protocol over USB**
   instead — it sends no Ctrl-C, leaves the Hub OS running, and already does identity, info, and
   (in progress) slot upload. `probes/usb_protocol.py` is the pattern.
2. **When you must use the REPL** (module upload to `/flash/lib`, `dir()` probing), accept that the
   Hub OS is now down and **restart it before expecting Bluetooth.** A physical power cycle works;
   `machine.soft_reset()` would reboot the interpreter → run `boot.py` → relaunch the Hub OS **without
   a physical restart**, but it is a reset call this project has treated as off-limits
   (`hub_programmer/run.py` refuses it) — **an operator decision, not something to trigger on
   initiative.**
3. **Harvest in the right order** — the control protocol and any BLE-state question come **before**
   the first Ctrl-C, never after ([harvest-while-the-cable-is-in.md](./harvest-while-the-cable-is-in.md)
   already orders `harvest.py` this way).

## How to apply

- **Advertising is a live-Hub-OS behaviour.** If the button does nothing, the Hub OS is almost
  certainly interrupted — restart, don't debug the button.
- **Never conclude "the radio is off for good"** from a probe session; you probably switched it off
  yourself with Ctrl-C.
- **Prefer the control protocol over the REPL** for anything the protocol can do, precisely because it
  keeps the Hub OS — and therefore Bluetooth — alive.

**Related:** [probe-with-scripts-not-commands.md](./probe-with-scripts-not-commands.md) ·
[harvest-while-the-cable-is-in.md](./harvest-while-the-cable-is-in.md) ·
[../findings/ble-protocol-2026-08-27.md](../findings/ble-protocol-2026-08-27.md) ·
[../research/ble-bring-up.md](../research/ble-bring-up.md)
