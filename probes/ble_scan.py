#!/usr/bin/env python3
"""ble_scan.py — WHO IS ADVERTISING? Passive BLE scan, from the host only.

Answers two questions the classroom will make urgent:
  1. Is our hub's Bluetooth actually ON and advertising? (Press the hub's
     Bluetooth button, re-run, and compare.)
  2. When several teams' hubs are advertising at once, WHICH ONE IS OURS?

This is a PASSIVE SCAN. It listens for advertisement packets and NEVER
connects, pairs, bonds, or writes. Connecting to somebody else's hub in a
classroom would be rude at best; this cannot do it.

It does not touch our hub either -- the hub is not involved in a scan at all.

    python3 probes/ble_scan.py               # 10 s scan, show everything
    python3 probes/ble_scan.py 20            # scan for 20 s
    python3 probes/ble_scan.py 10 --lego     # only likely-LEGO devices

Exit codes: 0 scan completed · 5 bleak missing · 6 adapter problem
"""

import asyncio
import sys

# LEGO System A/S, Bluetooth SIG company identifier 0x0397 (919).
# Our hub's device_uuid begins 03970000-..., the same 0397.
LEGO_COMPANY_ID = 0x0397

# LEGO's assigned 16-bit service UUID for the SPIKE/Powered Up hub service.
LEGO_SERVICE_16 = "fd02"

# Read from OUR hub over the USB cable on 2026-08-27. See docs/findings/.
OUR_DEVICE_UUID = "03970000-3600-1B00-1450-30514B323320"


def looks_lego(name, adv):
    if adv.manufacturer_data and LEGO_COMPANY_ID in adv.manufacturer_data:
        return True
    for u in (adv.service_uuids or []):
        if LEGO_SERVICE_16 in u.lower():
            return True
    n = (name or "").lower()
    return any(k in n for k in ("spike", "lego", "hub", "technic"))


async def scan(seconds, lego_only):
    try:
        from bleak import BleakScanner
    except ImportError:
        print("NO_BLEAK: python3 -m pip install --user bleak")
        return 5

    print("Passive BLE scan for %.0f s. Never connects." % seconds)
    print("Our hub's USB-read device_uuid: %s" % OUR_DEVICE_UUID)
    print("-" * 66)

    try:
        found = await BleakScanner.discover(timeout=seconds, return_adv=True)
    except Exception as exc:
        print("ADAPTER_PROBLEM: %s" % exc)
        print("  Check: rfkill list bluetooth ; systemctl is-active bluetooth")
        return 6

    if not found:
        print("Nothing advertising at all. Either nothing is nearby, or the")
        print("adapter is not scanning. Verify with: bluetoothctl scan on")
        return 0

    rows = []
    for addr, (dev, adv) in found.items():
        name = adv.local_name or dev.name or ""
        rows.append((looks_lego(name, adv), adv.rssi if adv.rssi is not None else -999,
                     addr, name, adv))
    rows.sort(key=lambda r: (not r[0], -r[1]))

    lego_seen = 0
    for is_lego, rssi, addr, name, adv in rows:
        if lego_only and not is_lego:
            continue
        tag = "  <== LOOKS LEGO" if is_lego else ""
        if is_lego:
            lego_seen += 1
        print("\n%s  rssi %4d dBm  %s%s" % (addr, rssi, name or "(no name)", tag))
        for u in (adv.service_uuids or []):
            print("    service   %s" % u)
        for cid, data in (adv.manufacturer_data or {}).items():
            marker = "  (LEGO)" if cid == LEGO_COMPANY_ID else ""
            print("    mfr 0x%04X%s  %s" % (cid, marker, data.hex()))
        for u, data in (adv.service_data or {}).items():
            print("    svcdata   %s  %s" % (u, data.hex()))

    print("\n" + "=" * 66)
    print("%d device(s) advertising; %d look like LEGO." % (len(rows), lego_seen))
    if lego_seen == 0:
        print()
        print("NO LEGO HUB IS ADVERTISING.")
        print("  Most likely reasons, in order:")
        print("   1. The hub's Bluetooth is not in advertising mode. Press the")
        print("      hub's Bluetooth button and re-run this scan.")
        print("   2. The hub is already CONNECTED to something -- a connected")
        print("      hub generally stops advertising.")
        print("   3. USB may suppress advertising on this firmware. UNVERIFIED;")
        print("      test by unplugging USB, running on battery, and re-scanning.")
    else:
        print()
        print("To tell WHICH hub is ours: compare the manufacturer-data bytes")
        print("above against our USB-read device_uuid. Record the match in")
        print("docs/findings/ so the next session does not have to re-derive it.")
    return 0


def main(argv):
    seconds = 10.0
    for a in argv[1:]:
        if not a.startswith("-"):
            try:
                seconds = float(a)
            except ValueError:
                pass
    return asyncio.run(scan(seconds, "--lego" in argv))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
