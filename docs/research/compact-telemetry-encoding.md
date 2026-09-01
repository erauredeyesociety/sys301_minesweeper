# Research — shrink the telemetry PAYLOAD instead of raising the link

**Type:** EXTERNAL research + repo synthesis · **Created:** 2026-09-01 · **Status:** designed,
**nothing here was run on our hub.** Every rate is COMPUTED from bracketed link parameters that are all
still `[UNVERIFIED]`; every codec claim is checked against our hub's MEASURED module list, not against a
telemetry run.

**Answers the operator's re-ask, verbatim intent:** *"do as much research as you can especially into the
bluetooth stuff like if there are ways around being able to use bluetooth while motors are in use."* This
document takes the **one lever the prior telemetry work left under-explored — the size of each record** —
and asks whether shrinking it makes **live** streaming feasible without touching the radio, the firmware,
or the BlueZ stack.

**This EXTENDS, and must not repeat,**
[telemetry-while-driving.md](./telemetry-while-driving.md). That document settled the architecture:

- A **SLOT** program runs under the live Hub OS, so it *can* drive motors and emit telemetry at once
  (`print()` → `ConsoleNotification`); the REPL route cannot (its Ctrl-C kills the Hub OS/radio).
- **Recommendation of account: LOG ON HUB** to a `/flash` CSV, retrieve over USB after the run, plus an
  optional ~3 Hz heartbeat. Full-rate live streaming of the **full** record is infeasible at the current
  link (~5–7 records/s at the floor).
- The reported "**MTU 23**" is a **bleak/BlueZ default, not a measured wire MTU**; MTU is **not** the main
  throughput lever — connection interval and packets-per-connection-event are, and DLE is the real
  multiplier.

All of that is **settled and unchanged here.** This document answers only: *given the link, how small can a
USEFUL live record be, and what does that do to the live rate?* The concurrency question — does `print()`
reach BLE while motors run at all — is orthogonal and still gated on bench tests **G4/G4b/G5**; a smaller
payload does not answer it, it only decides how much fits **once** it passes.

> Ground truth this builds on:
> [telemetry-while-driving.md](./telemetry-while-driving.md) ·
> [program-upload-protocol.md](./program-upload-protocol.md) ·
> [ble-bring-up.md](./ble-bring-up.md) ·
> [../findings/ble-protocol-2026-08-27.md](../findings/ble-protocol-2026-08-27.md) ·
> [../findings/hub-api-surface-2026-09-01.md](../findings/hub-api-surface-2026-09-01.md) ·
> [../../src/telemetry.py](../../src/telemetry.py).
> Governing rules: [../directives/hardware-safety.md](../directives/hardware-safety.md) ·
> [../decisions/0001-stock-lego-firmware-only.md](../decisions/0001-stock-lego-firmware-only.md).

---

## 0. The one-paragraph answer

**Yes — shrinking the payload is the single throughput lever fully under our control, and it is worth
more than raising the link.** A live-essential subset of the record packs into **~9 binary bytes**, which
survives the text-only `ConsoleNotification` channel as **~12 base64 characters** and fits in **one BLE
notification** instead of the **five** an ~89 B CSV line needs. That takes the achievable **live** rate
from **~6.7 rec/s** (full CSV, pessimistic floor) to **~33 rec/s** — a ~5× gain — **with no change to MTU,
connection interval, DLE, or any radio code**, on the day **G4** proves `print()` reaches BLE. The full
21-column record still goes, **whole**, to the `/flash` CSV log via `telemetry.py` unchanged; the compact
form is a **separate, versioned live channel**, not a subsetting of the log. **The catch that shapes the
whole design:** the sanctioned path is `print()`, and `ConsoleNotification` is a **NUL-terminated UTF-8
string** — so raw binary cannot go through it. It must be re-textualised (base64). On this text channel
binary still earns a real win: its **fixed** 12 chars stay in **one** notification unconditionally, whereas
a decimal-text subset of the same fields is variable-width (~18 chars) and **spills to two** notifications
unless the fields are shortened — but the *larger* binary advantage (no text inflation at all) appears only
on a raw-byte channel (`TunnelMessage`), which stays deferred.

---

## 1. The constraint that governs everything: the live channel is TEXT

The recommended transport is ordinary `print()`, wrapped by firmware as **`ConsoleNotification`
(0x21)** — and that message is `id + string[256]`, **NUL-terminated UTF-8** (primary source:
LEGO `messages.rst`, decoded host-side as `data[1:].rstrip(b'\0')` —
[program-upload-protocol.md](./program-upload-protocol.md) §2). Two consequences that a naive "pack it to
20 binary bytes" recommendation would get **wrong**:

1. **A `0x00` byte terminates the string.** Any packed record whose bytes include `0x00` (nearly all of
   them will) is truncated at the first null.
2. **Non-UTF-8 bytes corrupt the decode.** Arbitrary struct output is not valid UTF-8.

So on the sanctioned path, a compact record **must be re-encoded into printable ASCII** before `print()`.
The text-safe options and their cost:

| Encoding | inflation | 9 raw bytes → | on-hub cost |
|---|---|---|---|
| **base64** (`binascii.b2a_base64`) | ×4/3 (+33%) | **12 chars** | MEASURED-present, PROVEN on-hub (ADR-0007 deploy) |
| base85 / z85 | ×5/4 (+25%) | 12 chars (rounds up) | no stdlib helper; hand-rolled, not worth it |
| hex (`binascii.hexlify`) | ×2 (+100%) | 18 chars | present; simplest; doubles size |
| **decimal-text subset** (no packing) | n/a | ~18 chars, **value-dependent** | trivial (`print(a,b,c,...)`) |

**base64 is the right binary carrier** here: its codec is not merely present in the hub's MEASURED
`help('modules')` (`binascii`) but *already proven executing on the hub* — `hub_programmer/upload.py`
writes `binascii.a2b_base64(...)` **to the hub** and it runs (that is how ADR-0007 deploys). `struct` is
likewise in the MEASURED module list ([../findings/hub-api-surface-2026-09-01.md](../findings/hub-api-surface-2026-09-01.md)),
so a `struct.pack` packer runs hub-side against proven modules — no new dependency, no firmware anything.

> **Honest consequence, stated up front:** because the channel re-textualises, most of the win comes from
> **choosing few, small fields**, not from binary packing per se. But binary is not a wash here: a fixed
> **9-byte → 12-char** record lands in **one** notification *unconditionally*, while a decimal-text record
> of the same fields is **value-dependent** (~18 chars for a full-resolution `seq`/`yaw`) and **spills to
> two** notifications — halving the rate — unless the fields are shortened. So on this channel binary earns
> a **deterministic single notification**; its *larger* edge (no text inflation at all) appears only on a
> **raw-byte** channel — see §6.

### The only raw-binary escape, and why it stays deferred

`ble-bring-up.md` §3.5 enumerates the **four** ways data leaves the hub: `ConsoleNotification` (text),
`DeviceNotification` (fixed firmware telemetry, no custom fields), the identity replies, and
**`TunnelMessage` (0x50) — arbitrary bytes, `uint16` length**. `TunnelMessage` is the *only* channel that
would carry raw `struct` output with no text inflation. It stays **deferred**, unchanged from
[telemetry-while-driving.md](./telemetry-while-driving.md) §1.4: it needs hub-side tunnel code, it carries
a **known crash/power-off bug** on older builds, and it is `[UNVERIFIED]` on our 2025-03-27 firmware
(U-16). Driving `gatts_notify` from our own code is **forbidden** (must-not-own-the-radio, KU-M18). So the
compact-live design below targets `ConsoleNotification` + base64, and names `TunnelMessage` only as the
future path that would unlock the full binary saving.

---

## 2. Which fields matter LIVE, and which are log-only

A blind/supervising operator watching a laptop needs to answer three questions — *is it alive and
progressing? is it healthy? is it finding mines?* — not to reconstruct the trajectory. That is a handful
of fields. Everything diagnostic (encoders, per-axis IMU, raw RGB, reflection, distance) is for the
**offline** analysis and belongs in the `/flash` log at full rate, where bytes are nearly free.

Mapping `telemetry.COLUMNS` (21 fields) to the two tiers:

| `telemetry.COLUMNS` field | Live? | Why |
|---|---|---|
| `seq` | **LIVE** | detect gaps/stalls; **aligns a heartbeat to the exact `/flash` CSV row** |
| `t_ms` | log-only | clock reconciliation is done **offline** against the whole log (lower-envelope fit); host RX time + `seq` suffice live |
| `state` | **LIVE** | which state-machine state (SWEEP/TURN/REPORT/FAULT…) — the core "what is it doing" |
| `det_state` | **LIVE** | is the detector armed/seeing — the "is it seeing" question |
| `lane` | **LIVE** | pass index — the "is it progressing" question |
| `count` | **LIVE** | deduped mine count — the "is it finding mines" question |
| `yaw_ddeg` | **LIVE** | heading; lets the operator see it is tracking a lane (or spinning) |
| `pitch_ddeg`,`roll_ddeg` | log-only | diagnostic attitude |
| `accx_mg`,`accy_mg`,`accz_mg` | log-only | diagnostic; bumps/shoves analysed offline |
| `encL_deg`,`encR_deg` | log-only | odometry reconstruction offline |
| `cmdL_pct`,`cmdR_pct` | log-only | stall diagnosis offline (cmd vs enc) |
| `reflection_pct`,`r`,`g`,`b` | log-only | classifier post-mortem offline |
| `distance_mm` | log-only | not fitted; empty anyway |

**Live-essential set: `seq, state, det_state, lane, count, yaw_ddeg` + a health `flags` byte.** Seven
logical quantities. A status **`flags` bitfield** (degraded / fault / turn-unconverged / boundary-stop /
det-L-active / det-R-active) is *added* live even though it is not a single CSV column — it is exactly the
supervisor's "is it healthy" signal and costs one byte. This is the reconciliation with
`competition-program-design.md` §4.6's rule *"thin by rate, never by columns"*: **that rule protects the
CSV log's one-parser invariant** — the `/flash` line is still emitted whole. The compact live record is a
**different channel with its own versioned parser**, so choosing a subset for it is allowed; it is not
subsetting the CSV.

---

## 3. The compact live record — a ~9-byte layout

Little-endian (matches the LEGO wire convention and `slot_upload.py`'s framing), fixed width,
self-identifying by a version byte:

```
off  field              type   encoding / range
0    ver                u8     = BIN_VERSION; host rejects on mismatch
1    seq                u16    low 16 bits of Recorder.seq (wraps ~65535; aligns to /flash CSV row)
3    state | det_state  u8     (state<<4) | det_state ; each 0..15  (bit-packed, two enums in one byte)
4    lane               u8     pass index 0..255
5    count              u8     deduped mine count 0..255
6    yaw_ddeg           i16    decidegrees, -1800..1800 (same fixed-point as the yaw_ddeg column)
8    flags              u8     bit0 degraded · bit1 fault · bit2 turn_unconverged ·
                               bit3 boundary_stop · bit4 detL_active · bit5 detR_active
                        total = 9 bytes
```

**Encodings used, and deliberately NOT used:**

- **Fixed-point** — `yaw_ddeg` is decidegrees (already the record's unit), so heading rides in an `i16`
  with 0.1° resolution and no float on the wire. This is all the fixed-point the live set needs.
- **Bit-packing** — `state` and `det_state` are small enums, so they share one byte (4 bits each);
  `flags` is a bitfield. We stop there: `lane`/`count` get a full byte each for readability, because the
  record already fits one notification and shaving two more bytes buys nothing (§4).
- **Delta encoding — deliberately omitted.** `seq`/`t_ms` are monotonic and would compress under deltas,
  but (a) the record already fits one packet, so there is nothing to gain, and (b) deltas make a lost
  packet desync the stream. Fixed absolute fields are more robust. Delta encoding is the tool to reach
  for **only if** the live field set ever grows past one notification.
- **Round-robin fields — available, not recommended.** If the team later wants *more* than the essential
  subset streamed live while keeping every heartbeat to exactly one notification, send a fixed core
  (`ver,seq,state,count,flags` = 6 B) plus **one** rotating `(field_id, value)` slot that cycles through
  the log-grade fields; the host reassembles a fuller record over K packets, each extra field refreshed
  every `K / rate` seconds. Cost: host reassembly state and per-field staleness. Because the essential
  subset **already fits one packet**, this is unnecessary today — carry it as a known technique, not a
  build item (aggressive minimalism).

**On the wire:** 9 bytes → `base64` → **12 chars** (9 is a clean multiple of 3, zero padding). Run through
LEGO's own XOR-COBS framing on the host (`probes/_cobs.py`, **no hardware**): id byte + text + NUL, framed,
= **16 B** — comfortably **one** notification at the 20 B usable payload, with **4 chars of margin** before
the one-notification cliff. The measured relation is **framed = text_chars + 4**, so the cliff sits at
**16 text chars = 12 raw bytes**; the 9-byte layout is deliberately under it. (Host-confirmed the same way
the prior docs confirmed `InfoRequest → 00 00 02`; only the on-hub emission is `[UNVERIFIED]`, gated on G4.)

---

## 4. The rate math — payload shrink vs the link levers

**Model (all `[UNVERIFIED]`, computed, bracketed exactly as the prior docs):** connection interval
`I = 30 ms`; packets-per-connection-event `PE ∈ {1 pessimistic, 4 conservative}`; usable notify payload
`U = ATT_MTU − 3 = 20 B` at MTU 23. Notifications/s `= PE × 1000/I ∈ {33.3, 133}`. Records/s
`= notif_per_s ÷ ceil(framed_bytes / U)`.

Framed sizes below are **host-confirmed** through LEGO's XOR-COBS (`probes/_cobs.py`, no hardware):

| Encoding | framed wire | notif / record | **rec/s @ 30 ms, PE 1→4** |
|---|---|---|---|
| **Full CSV** — all 21 columns (~89 B) | **94 B** | **5** | **6.7 → 26.7** *(matches settled floor)* |
| Decimal-text subset (~18 chars, full-res) | **22 B** | **2** | **16.7 → 66.7** |
| **base64(9 B) live record** (§3) | **16 B** | **1** | **33.3 → 133** |
| base64(14 B) richer live record | 24 B | 2 | 16.7 → 66.7 |

Read three things off this table:

1. **The 5×.** Full CSV → compact binary = **5 notifications → 1**, i.e. **~5× the record rate** at every
   bracket, purely from choosing few small fields. This is the payload lever, and it is entirely ours.
2. **Binary beats decimal here — by a full notification.** A full-resolution decimal subset is ~18 chars →
   **2** notifications (row 2), because it is over the 16-char cliff *and* its width varies with the values
   (a 5-digit `seq` or a large `yaw` pushes it over unpredictably, run to run). The fixed **9-byte** binary
   record is **always** 12 chars → 16 B → **1** notification (row 3). So binary carries a full-resolution
   field set at **half** the notification cost of decimal, deterministically.
3. **Stay under one notification.** The cliff (host-confirmed) is `framed ≤ 20 B` ⟺ **16 text chars** ⟺
   **12 raw bytes** base64'd. The 9-byte layout sits **4 chars** under it by design; row 4 shows a 14-byte
   record (20 base64 chars) already over it.

**Does this need any link change? No.** But for completeness, the other levers, ranked by
controllability × payoff:

| Lever | Effect on our compact record | Controllable here? |
|---|---|---|
| **Payload shrink (§3)** | **~5×** (5 notif → 1) | **Fully — no radio/BlueZ/firmware change.** RECOMMENDED |
| **Connection interval** 30 → 7.5 ms | up to **~4×** (more events/s); compact → ~133–533 rec/s | Root debugfs write; **`[UNVERIFIED]` BlueZ-central honours it** (§5) |
| **ATT MTU** 23 → 247 | **~0** — a record already at 1 notification stays 1 notification | Read-only on BlueZ; **moot once shrunk** |
| **DLE** (27 → 251 B LL PDU) | **0** — a ~17 B notification already fits one LL PDU | **Irrelevant to small records** (§5) |

The inversion worth stating plainly: **MTU and DLE, the levers the early notes fixated on, do nothing for a
record that already fits one notification.** MTU-raise and payload-shrink are *substitutes* for the full
CSV record (either collapses 5 notifications to 1); once you have shrunk, MTU is spent. DLE only ever helped
a payload big enough to fragment across multiple 27-B link-layer PDUs — the full CSV, or a bulk log dump —
never a 17-byte heartbeat.

---

## 5. Connection interval and DLE on BlueZ — concretely

### 5.1 Connection interval — the biggest *link* lever, but the BlueZ knob is unreliable

Sustained notify rate scales **∝ 1/interval**: at a fixed `PE`, going 30 ms → 7.5 ms is **4×** the
events/s and thus ~4× the rate. On Linux the interval is negotiated by BlueZ (central) from what the
**hub (peripheral) requests**; there is **no bleak API** to set it per-connection. The system-wide knobs:

```bash
# units are 1.25 ms; 6 = 7.5 ms (the LE minimum), 24 = 30 ms (default), 40 = 50 ms
cat /sys/kernel/debug/bluetooth/hci0/conn_min_interval   # default 24
cat /sys/kernel/debug/bluetooth/hci0/conn_max_interval   # default 40
echo 6  | sudo tee /sys/kernel/debug/bluetooth/hci0/conn_min_interval   # BEFORE connecting
echo 12 | sudo tee /sys/kernel/debug/bluetooth/hci0/conn_max_interval
```

`[UNVERIFIED]`, and flagged as such by the sources: writing these changes the parameters BlueZ *requests*
for **new** connections, but **as a central, BlueZ may not apply the comparison at all**, and there are
open BlueZ issues where it **rejects** peripheral-initiated Connection Parameter Updates (bluez/bluez#847).
So this *may* raise the rate and *may* be silently ignored — it must be **read back with `btmon`** (§5.3),
not assumed. It also needs root, costs hub battery/airtime, and the hub's own requested parameters may
override. **Do not design around it; try it only if the compact record still needs more rate**, which is
unlikely. (Connection-interval adaptation as the primary BLE rate/latency control is corroborated in the
literature — e.g. the *CABLE* interval-adaptation work — but treat that as indicative, not
this-pairing-specific; the PDF was not fetched.)

### 5.2 DLE — available or not, it does not help the compact record

Data Length Extension (BLE 4.2) grows the link-layer PDU from **27 B to up to 251 B**, so a large ATT
notification is not chopped into many 27-B PDUs. The hub is BLE 4.2 (LEGO spec) and BlueZ 5.64 + a modern
adapter negotiate DLE **automatically at connect** when both sides support it — so it is *plausibly already
on*, `[UNVERIFIED]` for this specific hub+adapter. **But it is irrelevant to this design:** our ~17 B
notification is smaller than one 27-B LL PDU, so it is never fragmented and DLE changes nothing for it. DLE
matters only for **large** payloads — the full CSV line, or a **BLE bulk log dump** — and the settled plan
retrieves the log over **USB** (deterministic, ~21 s vs ~69–276 s over BLE), where there is no LL PDU at
all. So: check DLE for completeness, but it is a lever for a path we do not take.

### 5.3 Reading what actually got negotiated (free, read-only over BLE)

None of these *set* anything; they *measure* the link so the numbers above stop being brackets. Do them
once G4 opens a connection:

```python
# In the host capture client, AFTER connect. Guard the private call to the BlueZ backend.
if hasattr(client, "_backend") and hasattr(client._backend, "_acquire_mtu"):
    await client._backend._acquire_mtu()          # forces the real MTU; else mtu_size is the 23 default
print("mtu_size:", client.mtu_size)
ch = client.services.get_characteristic("0000fd02-0002-1000-8000-00805f9b34fb")  # notify char
print("max_write_without_response_size:", ch.max_write_without_response_size)     # = ATT_MTU - 3
```

```bash
sudo btmon | grep -iE "Connection Complete|Conn Interval|Data Length|LL_LENGTH"
#   LE Connection Complete            -> the negotiated connection interval (settles U-7)
#   LL_LENGTH_REQ / LL_LENGTH_RSP     -> whether DLE was negotiated, and the agreed max octets (settles U-8)
#   count notifications/s in the client to get achieved bytes/s (this is gate G3, the number that binds)
```

`[UNVERIFIED]` until run: MTU, interval, `PE`, and DLE are all still bracketed — but every one of them is
read **without writing to the hub**, so they can be closed the day the link comes up.

---

## 6. What the binary sibling of `src/telemetry.py` looks like

`telemetry.py` stays the **record of account** — CSV to `/flash`, one canonical parser, unchanged. The
compact form is a **sibling module** that is a *second encoder of the same schema*, not a second schema.
Design rules:

1. **One schema, two encoders.** The field **order and units** stay owned by `telemetry.COLUMNS`. The
   sibling names the subset it carries and pins each to its `COLUMNS` field, so a column rename cannot
   silently desync the live channel (the same discipline the v1→v2 `accx→accx_mg` rename forced).
2. **`seq` is the SAME counter** (its low 16 bits), so every heartbeat **joins to an exact `/flash` CSV
   row** offline. The integrity story (`seq`/`sum_seq`/`t_ms`, `expected_sum_seq`) continues to live in the
   whole CSV log; the heartbeat borrows only `seq`.
3. **Text-safe by construction** — the packer's bytes go out **only** via base64. Never `print()` the raw
   `struct` bytes (NUL-termination + UTF-8, §1).
4. **Fixed width, version-guarded** — a garbled or truncated heartbeat fails the length/version check and
   is dropped, never misparsed.
5. **Pure, MicroPython-subset** — no f-strings, no dataclasses, no typing; `struct` + `binascii`, both
   MEASURED-present and (for base64) proven on-hub.

Sketch (illustrative — **not** an edit to `src/`; the recommended change list is §7):

```python
# telemetry_bin.py -- compact LIVE sibling of telemetry.py. PURE. host + hub.
# ONE schema (telemetry.COLUMNS), TWO encoders: telemetry.py = canonical CSV; this = live subset.
import struct           # MEASURED in help('modules')
import binascii         # MEASURED; a2b/b2a_base64 PROVEN executing on-hub (ADR-0007 deploy)

BIN_VERSION = 1
_LIVE_FMT = "<BHBBBhB"          # ver u8, seq u16, state|det u8, lane u8, count u8, yaw_ddeg i16, flags u8
LIVE_SIZE = struct.calcsize(_LIVE_FMT)   # == 9

# health bits carried live but not a single CSV column
F_DEGRADED, F_FAULT, F_TURN_UNCONVERGED = 0x01, 0x02, 0x04
F_BOUNDARY_STOP, F_DETL, F_DETR         = 0x08, 0x10, 0x20

def pack_live(seq, state, det_state, lane, count, yaw_ddeg, flags):
    """9 raw bytes. Caller clamps yaw_ddeg to +-1800; enums to 0..15; counters to 0..255/0xFFFF."""
    return struct.pack(_LIVE_FMT, BIN_VERSION, seq & 0xFFFF,
                       ((state & 0x0F) << 4) | (det_state & 0x0F),
                       lane & 0xFF, count & 0xFF, yaw_ddeg, flags & 0xFF)

def emit_live(seq, state, det_state, lane, count, yaw_ddeg, flags):
    """ONE ConsoleNotification, ~12 chars. b2a_base64 returns b'...\\n'; strip it, print adds its own."""
    print(binascii.b2a_base64(pack_live(seq, state, det_state, lane, count,
                                        yaw_ddeg, flags)).decode("ascii").rstrip())

# --- host side (CPython) ---
def unpack_live(text):
    raw = binascii.a2b_base64(text)
    if len(raw) != LIVE_SIZE or raw[0] != BIN_VERSION:
        return None                      # garbled/old frame -> drop, never misparse
    _, seq, sd, lane, count, yaw_ddeg, flags = struct.unpack(_LIVE_FMT, raw)
    return {"seq": seq, "state": sd >> 4, "det_state": sd & 0x0F,
            "lane": lane, "count": count, "yaw_ddeg": yaw_ddeg, "flags": flags}
```

**Second, optional use — the RAM ring.** If a slot program cannot write `/flash` and the fallback is a
bounded RAM ring (competition-program-design §4.4), the **full** 21-field record packed with `struct`
(~24 B) instead of stored as an ~89 B CSV line roughly **quadruples** ring capacity for the same heap. That
is a *different* packer (all fields, no base64 — it is dumped, not `print()`-streamed, and can be base64'd
once at dump time). Build it **only if** U-11 shows `/flash` is unwritable from a slot program; the `/flash`
CSV via `telemetry.py` is preferred and needs no packing at all.

---

## 7. Recommended changes to OTHER files — NOT applied here

Per the minimalism constraint, this document is the only new file. The following are **recommendations**;
the files are **not** edited.

| File | Recommended change | Why |
|---|---|---|
| `docs/research/INDEX.md` | Add a row for this doc. (`./scripts/check-docs.py` will flag it as un-indexed until then.) | INDEX-coverage rule |
| `src/telemetry_bin.py` (**new**) | Add the §6 sibling **only when live telemetry is actually built** (after G4). Pure module; import the field names it carries from `telemetry.COLUMNS`. | Keeps one schema, two encoders; no schema fork |
| `src/config.py` | When live is enabled, keep `TELEMETRY_LIVE_ENABLED=False` default; add `TELEMETRY_LIVE_FORMAT="bin"` (vs `"csv"`) so the live channel can select the compact encoder without touching the `/flash` log format | Value, not architecture |
| `docs/plans/competition-program-design.md` | §4.6: note that "thin by rate, not columns" governs the **CSV log**; the **live** channel may use the compact `telemetry_bin` subset (a separate versioned parser), which is what makes the ~3 Hz heartbeat — or a modest live stream — fit the pessimistic floor with margin | Reconciles the subset with the one-parser rule |
| `docs/research/telemetry-while-driving.md` | Cross-reference this doc from §2.1 / §3.5 as the payload-side companion to the link-side MTU analysis; both feed gate G3 | Keeps the two telemetry docs in sync |

---

## 8. `[UNVERIFIED]` register — what settles each

Nothing below was run on our hub. Rows that duplicate the prior doc's gates cite them rather than
re-listing the test.

| # | Open point | Confidence | The check |
|---|---|---|---|
| C-1 | Does `print()` from a slot program reach the host as `ConsoleNotification` at all? | INFERRED | **G4** (telemetry-while-driving §5) — the crux; a smaller payload is moot until this passes |
| C-2 | Framed wire size of a 12-char base64 line through LEGO's XOR-COBS | **HOST-CONFIRMED 16 B** (`probes/_cobs.py`; framed = text + 4; cliff at 16 chars) | closed for the transport framing; on-hub emission still gated on G4/U-4 |
| C-3 | Does the hub emit `ConsoleNotification` per-`print()`, per-line, or padded to 256 B? (padding would erase the shrink) | UNVERIFIED | **U-4** — compare received framed length of a short vs long line |
| C-4 | Real ATT MTU / connection interval / `PE` / DLE on this pairing | UNVERIFIED (bracketed) | §5.3 — `_acquire_mtu()`, `btmon`, count notif/s (**G3**) |
| C-5 | Does writing `conn_min/max_interval` change the negotiated interval with BlueZ as central? | UNVERIFIED (sources say it may be ignored) | Write it, reconnect, read the interval in `btmon` (§5.1) |
| C-6 | Does a smaller/less frequent `print()` reduce the no-listener stall risk? | INFERRED (secondary benefit) | Fold into **G4b** — smaller TX bursts, same test |
| C-7 | On-hub `struct.pack` + `b2a_base64` cost per record vs plain CSV `str.join` | UNMEASURED | Time both on-hub against the loop period (U-10 companion) |

**The one line that matters:** the compact encoding is **~5× the live rate for free**, but it changes
*how much fits*, not *whether anything fits* — that is still **G4**. Build `telemetry_bin.py` the day G4
passes, not before.

---

## 9. Sources

- **Primary — LEGO/spike-prime-docs:** `messages.rst` (`ConsoleNotification 0x21 = id + string[256]`,
  NUL-terminated UTF-8; `TunnelMessage 0x50` arbitrary bytes), `encoding.rst` (XOR-COBS framing),
  `connect.rst`. Rendered: <https://lego.github.io/spike-prime-docs/messages.html>.
- **Our MEASURED ground truth:** [../findings/hub-api-surface-2026-09-01.md](../findings/hub-api-surface-2026-09-01.md)
  and [../findings/hub-first-contact-2026-08-27.md](../findings/hub-first-contact-2026-08-27.md)
  (`help('modules')` lists `struct`, `binascii`, `hashlib`, `deflate`, `zlib`);
  `hub_programmer/upload.py` (base64 decode PROVEN executing on-hub, ADR-0007);
  [../findings/ble-protocol-2026-08-27.md](../findings/ble-protocol-2026-08-27.md) (FD02 chars, MTU 23,
  `max_packet_size` 509).
- **Repo synthesis:** [telemetry-while-driving.md](./telemetry-while-driving.md) (architecture, gates
  G3/G4/G4b/G5, MTU-is-not-the-lever), [program-upload-protocol.md](./program-upload-protocol.md)
  (`ConsoleNotification` reassembly, no download message), [ble-bring-up.md](./ble-bring-up.md) §3.5/§4
  (four data-out channels, must-not-drive-the-radio), [../../src/telemetry.py](../../src/telemetry.py)
  (`COLUMNS`, `Recorder`, integrity trailer).
- **BLE throughput / BlueZ (secondary):** Memfault *BLE Throughput Primer* (DLE 27→251 B, MTU-without-DLE
  ~20–33%); BlueZ `conn_min_interval`/`conn_max_interval` debugfs (units 1.25 ms, default 24/40) and the
  central-role caveat — linux-bluetooth list + bluez/bluez#847, #717 (rejected/ignored Connection Parameter
  Updates); bleak has no per-connection interval API (bleak#149). Connection-interval adaptation as the BLE
  rate/latency lever — *CABLE* (indicative, PDF not fetched). All `[UNVERIFIED]` against **this** hub+adapter
  until read back with `btmon`.
