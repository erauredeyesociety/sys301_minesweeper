# examples/ble_watch.py — watch BLE advertisements arrive and vanish, live.
#
# RUNS ON THE LAPTOP (bleak), NOT on the hub. It never touches the serial port,
# which is the entire point: we suspect our own probes have been switching the
# hub's radio off.
#
#   python3 examples/ble_watch.py 60
#
# WHY THIS EXISTS
# A one-shot scan answers "is it advertising right now". It cannot answer "what
# did pressing that button DO", because the answer is a CHANGE and a single
# sample has nothing to compare against. This logs appearances and
# disappearances against a clock, so the operator can press the CONNECT button,
# power-cycle, or unplug USB, and read straight off the log what changed.
#
# THE HYPOTHESIS IT WAS WRITTEN TO TEST
# /flash/boot.py sets hub.config["hub_os_enable"] = True. The Hub OS is a
# PROGRAM. Every probe in probes/ opens with Ctrl-C to get a REPL prompt, and
# Ctrl-C interrupts programs. So we may have been killing the LEGO stack that
# owns the radio every time we looked at the hub -- which would explain a hub
# that is powered, healthy, and completely silent over the air.
#
# So: DO NOT open the serial port while this runs.
#
# It NEVER connects, pairs, or bonds. Passive listening only -- other teams'
# hubs are not ours to touch.

import asyncio
import sys
import time

LEGO_COMPANY_ID = 0x0397          # LEGO System A/S, Bluetooth SIG
LEGO_SERVICE_16 = "fd02"
OUR_DEVICE_UUID = "03970000-3600-1B00-1450-30514B323320"   # read over USB


def is_lego(name, adv):
    if adv.manufacturer_data and LEGO_COMPANY_ID in adv.manufacturer_data:
        return True
    for u in (adv.service_uuids or []):
        if LEGO_SERVICE_16 in u.lower():
            return True
    n = (name or "").lower()
    return any(k in n for k in ("spike", "lego", "technic"))


async def watch(seconds):
    try:
        from bleak import BleakScanner
    except ImportError:
        print("NO_BLEAK: python3 -m pip install --user bleak")
        return 5

    seen = {}
    t0 = time.monotonic()

    def stamp():
        return "%6.1fs" % (time.monotonic() - t0)

    def on_detect(dev, adv):
        name = adv.local_name or dev.name or ""
        lego = is_lego(name, adv)
        key = dev.address
        if key not in seen:
            seen[key] = lego
            if lego:
                print("\n%s  *** LEGO DEVICE APPEARED ***" % stamp())
                print("           address %s   rssi %s dBm" % (dev.address, adv.rssi))
                print("           name    %r" % name)
                for u in (adv.service_uuids or []):
                    print("           service %s" % u)
                for cid, data in (adv.manufacturer_data or {}).items():
                    tag = "  <- LEGO company id" if cid == LEGO_COMPANY_ID else ""
                    print("           mfr 0x%04X %s%s" % (cid, data.hex(), tag))
                print("           our USB-read uuid: %s" % OUR_DEVICE_UUID)
                print("           ^ compare those bytes to decide if this hub is ours")
            elif name:
                print("%s  + %-28s %s" % (stamp(), name[:28], dev.address))

    print("Watching for %.0f s. NOTHING may hold the serial port while this runs." % seconds)
    print("Try, one at a time, leaving a gap between each so the log is readable:")
    print("  1. press the CONNECT button (the Bluetooth one) briefly")
    print("  2. press and hold it")
    print("  3. unplug the USB cable so the hub runs on battery")
    print("  4. power the hub off and on, and do not run any probe afterwards")
    print("-" * 66)

    scanner = BleakScanner(detection_callback=on_detect)
    await scanner.start()
    try:
        await asyncio.sleep(seconds)
    finally:
        await scanner.stop()

    legos = [a for a, l in seen.items() if l]
    print("-" * 66)
    print("%d device(s) seen; %d LEGO." % (len(seen), len(legos)))
    if not legos:
        print("")
        print("NO LEGO HUB APPEARED for the whole window.")
        print("If you power-cycled and stayed off the serial port and it is still")
        print("silent, the Ctrl-C hypothesis is WRONG and the radio is off for")
        print("another reason. That is a real result -- record it.")
    return 0


def main(argv):
    seconds = 60.0
    for a in argv[1:]:
        try:
            seconds = float(a)
        except ValueError:
            pass
    return asyncio.run(watch(seconds))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
