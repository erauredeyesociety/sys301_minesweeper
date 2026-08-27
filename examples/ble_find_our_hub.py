#!/usr/bin/env python3
# examples/ble_find_our_hub.py — which BLE advertisement is OUR hub?
#
# RUNS ON THE HOST, NOT THE HUB.  python3 examples/ble_find_our_hub.py 90
# Exit: 0 the watch ran (found or not -- a null result is still a result)
#       5 bleak missing · 6 the Bluetooth adapter would not start
#
# [UNVERIFIED] THIS HAS NEVER RUN ON HARDWARE. Written and audited 2026-08-27.
# probes/ble_scan.py HAS run: 12 s, 581 advertising devices, ZERO LEGO by
# company id, service UUID or name (docs/findings/hub-first-contact-2026-08-27.md
# § 4a). The identity match below has never had anything to match against.
# Paste the real output into docs/findings/ the first time it does.
#
# ONE JOB: decide which BLE address is ours. Its two neighbours do not:
#   probes/ble_scan.py    a SNAPSHOT -- "who is in the room right now".
#   examples/ble_watch.py appear/vanish log, to test whether our own serial
#                         probes were killing the radio. Matches no bytes.
# This one adds TIME (anything first seen after a quiet BASELINE is a CANDIDATE,
# even with a silent payload -- an appearance correlated with a button press is
# evidence that three failed content tests are not) and BYTES (every device, on
# every packet, matched against the identity read off our hub over USB).
#
# It NEVER connects, pairs or bonds; there is no connect call in this file.
# Host-side, so full CPython 3.10 + bleak (3.0.2 here) -- the MicroPython
# subset rules do not apply to this file.

import asyncio
import sys
import time

WATCH_S = 90.0         # run time, argv[1] overrides; rounds up to a whole
                       # number of HEARTBEAT_S sleeps
BASELINE_S = 20.0      # first seen before this = crowd, after = candidate
HEARTBEAT_S = 10.0     # "still alive" line while nothing is happening

# 4, not 3: every device is re-matched on every packet, so this runs tens of
# thousands of times per run and a 3-byte coincidence stops being unlikely.
MIN_MATCH_BYTES = 4

LEGO_COMPANY_ID = 0x0397   # LEGO System A/S, Bluetooth SIG. Corroborated: our
                           # own device_uuid begins 03970000-.
LEGO_SERVICE_16 = "fd02"   # 0000FD02-…, LEGO Hub OS 3 GATT service -- from
                           # LEGO's published protocol docs, NOT measured here
                           # (docs/research/bluetooth-control-plane.md).

# Read off OUR hub over USB on 2026-08-27: machine.unique_id()
# (docs/findings/hub-first-contact-2026-08-27.md § 1). device_uuid() is
# 03970000- followed by these same twelve bytes, so this is the whole identity.
OUR_UNIQUE_ID = b"6\x00\x1b\x00\x14P0QK23 "

# address -> [first_t, count, best_rssi, name, state]
# state 0 unreported · 1 announced, content tests still open · 2 identified
seen = {}
lego_hits = []   # addresses that tripped a LEGO content test
id_hits = []     # addresses whose raw bytes matched OUR_UNIQUE_ID
t0 = time.monotonic()


def log(tag, text):
    print("t=%6.1fs  %-9s %s" % (time.monotonic() - t0, tag, text))


def looks_lego(name, adv):
    if adv.manufacturer_data and LEGO_COMPANY_ID in adv.manufacturer_data:
        return True
    for u in (adv.service_uuids or []):
        if LEGO_SERVICE_16 in u.lower():
            return True
    n = (name or "").lower()
    return ("spike" in n) or ("lego" in n) or ("technic" in n)


def longest_run(needle, blob):
    # Longest contiguous piece of needle appearing anywhere in blob. Twelve
    # bytes, so the naive double loop is free and obviously correct.
    best = b""
    for i in range(len(needle)):
        for j in range(i + len(best) + 1, len(needle) + 1):
            if needle[i:j] in blob:
                best = needle[i:j]
            else:
                break
    return best


def identity_hit(addr, adv):
    # EVERY device, not just the interesting ones: our hub may already have
    # been advertising when the baseline started.
    try:
        blob = bytes.fromhex(addr.replace(":", "").replace("-", ""))
    except ValueError:
        blob = b""      # macOS hands out a CoreBluetooth UUID, not a MAC
    for _, data in (adv.manufacturer_data or {}).items():
        blob += bytes(data)
    for _, data in (adv.service_data or {}).items():
        blob += bytes(data)
    fwd = longest_run(OUR_UNIQUE_ID, blob)
    rev = longest_run(OUR_UNIQUE_ID[::-1], blob)
    hit = fwd if len(fwd) >= len(rev) else rev
    if len(hit) < MIN_MATCH_BYTES:
        return b""
    if addr not in id_hits:
        id_hits.append(addr)
    return hit


def dump(adv, hit):
    for u in (adv.service_uuids or []):
        print("             service   %s" % u)
    for cid, data in (adv.manufacturer_data or {}).items():
        mark = "  (LEGO 0x0397)" if cid == LEGO_COMPANY_ID else ""
        print("             mfr 0x%04X%s  %s" % (cid, mark, bytes(data).hex()))
    for u, data in (adv.service_data or {}).items():
        print("             svcdata   %s  %s" % (u, bytes(data).hex()))
    if hit:
        print("             *** %s -- %d of our %d identity bytes, %s"
              % ("MATCH" if len(hit) == len(OUR_UNIQUE_ID) else "PARTIAL",
                 len(hit), len(OUR_UNIQUE_ID), hit.hex()))
        print("             *** all twelve is proof; fewer is a lead only.")


def on_adv(dev, adv):
    now = time.monotonic() - t0
    addr = dev.address
    rssi = adv.rssi if adv.rssi is not None else -999
    name = adv.local_name or getattr(dev, "name", None) or ""

    rec = seen.get(addr)
    if rec is None:
        rec = seen[addr] = [now, 1, rssi, name, 0]
    else:
        rec[1] += 1
        rec[2] = max(rec[2], rssi)
        if name and not rec[3]:
            rec[3] = name       # the name usually arrives in a LATER packet
        name = rec[3]
    if rec[4] == 2:
        return

    # Re-tested every packet on purpose: BLE splits a device's story across
    # ADV_IND and SCAN_RSP, so the manufacturer data that proves LEGO can
    # arrive long after first sighting. Testing once would miss it.
    lego = looks_lego(name, adv)
    hit = identity_hit(addr, adv)
    line = "%s  rssi %4d  %s" % (addr, rssi, name or "(no name)")

    if lego or hit:
        rec[4] = 2
        if lego and addr not in lego_hits:
            lego_hits.append(addr)
        log("LEGO" if lego else "IDENTITY", line)
        dump(adv, hit)
    elif rec[4] == 0:
        rec[4] = 1              # announce once; keep testing, don't re-print
        if rec[0] >= BASELINE_S:
            log("CANDIDATE", line + "   <== appeared AFTER the baseline")
            dump(adv, hit)
        else:
            log("baseline", line)


async def watch(seconds):
    try:
        from bleak import BleakScanner
    except ImportError:
        print("NO_BLEAK: python3 -m pip install --user bleak")
        return 5

    print("=" * 70)
    print("BLE APPEARANCE WATCH -- listens only, never connects")
    print("  our hub's USB-read unique_id : %s" % OUR_UNIQUE_ID.hex())
    print("  baseline %.0fs, then watching to %.0fs" % (BASELINE_S, seconds))
    print("  Nothing may hold the serial port. Do nothing until WATCH PHASE,")
    print("  then press CONNECT (the API's name for the Bluetooth button) -- or")
    print("  unplug USB then, to test whether USB suppresses the radio.")
    if seconds <= BASELINE_S:
        print("  WARNING: %.0fs is inside the %.0fs baseline -- no watch phase,"
              % (seconds, BASELINE_S))
        print("  no candidates. Ask for longer than the baseline.")
    print("-" * 70)

    # Default (active) scan: it sends SCAN_REQ, which is how scan-response
    # payloads and most names arrive. BlueZ's true passive mode needs
    # or_patterns filters, which would hide the unnamed strangers we came for.
    scanner = BleakScanner(detection_callback=on_adv)
    try:
        await scanner.start()
    except Exception as exc:
        print("ADAPTER_PROBLEM: %s" % exc)
        print("  Check: rfkill list bluetooth ; systemctl is-active bluetooth")
        return 6

    announced = False
    try:
        while time.monotonic() - t0 < seconds:
            await asyncio.sleep(HEARTBEAT_S)
            if not announced and time.monotonic() - t0 >= BASELINE_S:
                announced = True
                log("PHASE", ">>> WATCH PHASE -- press CONNECT now <<<")
            log("...", "%d devices, %d LEGO, %d identity hits"
                % (len(seen), len(lego_hits), len(id_hits)))
    except KeyboardInterrupt:
        log("PHASE", "interrupted -- summarising what was seen so far")
    finally:
        await scanner.stop()

    late = [a for a in seen if seen[a][0] >= BASELINE_S]
    print("\n" + "=" * 70)
    print("%d device(s) total; %d appeared after the baseline; %d look LEGO."
          % (len(seen), len(late), len(lego_hits)))
    for a in late:
        first, count, rssi, name = seen[a][:4]
        print("  t=%6.1fs  %s  rssi %4d  x%-4d %s" % (first, a, rssi, count, name))
    if lego_hits or id_hits:
        print("\nRecord the winning address and its bytes in docs/findings/, so")
        print("the next session identifies our hub by lookup, not by re-deriving.")
        return 0

    print("\nNO LEGO HUB IDENTIFIED. That is a result, not a failure. In order:")
    print("  1. The radio is not advertising. Press CONNECT and watch for a")
    print("     CANDIDATE line at that instant -- this script's whole point,")
    print("     and it works on a payload that says nothing at all.")
    print("  2. USB suppresses advertising. UNVERIFIED -- re-run on battery,")
    print("     cable out. That costs the REPL, so it is the operator's call.")
    print("  3. Already connected to something; a connected hub stops advertising.")
    print("  4. It burst-advertises after the press and this run missed it.")
    print("  NOT a reason: Hub OS 2. We read 1.24.0 / SPIKE 3 off this hub.")
    return 0


run_s = WATCH_S
if len(sys.argv) > 1:
    try:
        run_s = float(sys.argv[1])
    except ValueError:
        print("Usage: python3 examples/ble_find_our_hub.py [seconds]")
        sys.exit(1)

sys.exit(asyncio.run(watch(run_s)))
