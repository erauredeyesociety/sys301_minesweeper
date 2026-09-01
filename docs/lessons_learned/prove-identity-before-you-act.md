# Prove you are talking to YOUR robot before you act on it

**Date:** 2026-08-27 · **Source:** we connected to another team's hub, on the first day we had
Bluetooth working at all.

**WHEN** connecting to any device in a shared space — a classroom, a lab bench, a workshop —

**DON'T** act on the first device that matches a *type* filter. Match on **identity**, and verify it
**before** you do anything, not after.

**BECAUSE** "it's a LEGO hub" is not "it's *our* LEGO hub", and in a room where every team has the
same kit, the type filter matches everybody.

## What happened

`examples/ble_connect.py` scanned for a LEGO hub and connected to the first one that advertised. It
found:

```
08:04:B4:3C:73:4D   rssi -81 dBm   name ''   mfr 0x0397 0101003c734d
```

**That is not our hub.** Ours is `64:8C:BB:0A:1C:8C`, advertising as `Team 21`. We connected to a
classmate's robot, enumerated its GATT services, and read its characteristics.

**No harm was done** — the script only reads, and it wrote nothing. But it *could* have been the
uploader. And the failure was silent: the run looked completely successful. We only noticed because
the expected telemetry never arrived, and the address in the log did not match the one we had written
down.

**The design was wrong in a way that looked right.** The script was even written knowing this problem
existed — its own header says *"it will not connect to a device that does not look like LEGO, so it
cannot wander into another team's equipment by accident."* That sentence is exactly backwards: looking
like LEGO is what *every* hub in the room does.

## Why the obvious fixes are not enough

| Identifier | Why it fails |
|---|---|
| **Display name** (`"Team 21"`) | User-settable. Anyone can set theirs to anything, including ours. |
| **Signal strength** | "The nearest one is probably mine" is a guess, and a classmate's hub on the next desk beats ours across the room. |
| **BLE MAC address** | Better, and we use it as a *filter* — but the address type is unverified and may be a resolvable private address, which **rotates**. |

**The only proof is an identifier the device cannot change and we read from a source we trust.** Ours
is `device_uuid`, read over the **USB cable** — point-to-point, so whatever answered is physically
plugged into this laptop. Confirmed to match over BLE:
[../findings/ble-protocol-2026-08-27.md](../findings/ble-protocol-2026-08-27.md).

## How to apply

- **Filter by address, prove by UUID.** Use the known BLE address to avoid connecting to strangers;
  once connected, send `DeviceUuidRequest 0x1A` and compare all 16 bytes before doing anything else.
- **Refuse, loudly, on a mismatch.** Disconnect and say which device it was. Do not fall back to
  "well, it's the only one here."
- **Prefer a transport that cannot be ambiguous.** The USB cable is point-to-point; a radio is not.
  When both work, the cable removes an entire class of error.
- **Read your own safety claims sceptically.** The header comment asserted a protection the code did
  not implement. A comment is not a control.

**Related:** [say-which-kind-of-verified.md](./say-which-kind-of-verified.md) ·
[a-tool-works-when-it-does-its-job.md](./a-tool-works-when-it-does-its-job.md) ·
[../findings/ble-protocol-2026-08-27.md](../findings/ble-protocol-2026-08-27.md)
