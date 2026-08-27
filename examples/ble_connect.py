# examples/ble_connect.py — connect to the hub over BLE and enumerate what it offers.
#
# RUNS ON THE LAPTOP (bleak). Does not use the serial port -- and MUST NOT,
# because opening a USB REPL session sends Ctrl-C, which kills the Hub OS, and
# the Hub OS is what runs the Bluetooth stack. USB probing and BLE are mutually
# exclusive on this hub. That was measured, not assumed:
# docs/findings/hub-first-contact-2026-08-27.md
#
#   python3 examples/ble_connect.py                       # find a LEGO hub and connect
#   python3 examples/ble_connect.py 64:8C:BB:0A:1C:8C     # connect to a known address
#   python3 examples/ble_connect.py --listen 20           # then listen 20 s for notifications
#   python3 examples/ble_connect.py --wait 120           # wait longer for the button press
#
# WHY THIS DISCOVERS RATHER THAN ASSUMES
# LEGO publishes a BLE protocol, but hard-coding characteristic UUIDs from a
# document means a wrong document produces a silent failure that looks like
# broken hardware. This connects and asks the hub what it actually has, then
# prints it. What we learn here becomes the constants a real client uses.
#
# WHAT IT WILL NOT DO
#   * It connects to ONE device and never writes to it. No commands are sent,
#     no programs uploaded, no settings changed.
#   * With --listen it SUBSCRIBES to notifying characteristics and prints raw
#     bytes. Subscribing is a read-side operation; it does not instruct the hub.
#   * It will not connect to a device that does not look like LEGO, so it cannot
#     wander into another team's equipment by accident.

import asyncio
import sys

LEGO_COMPANY_ID = 0x0397
LEGO_SERVICE_16 = "fd02"

# Read from OUR hub over the USB cable, 2026-08-27. The advertisement does NOT
# carry this, so it cannot be used to pick the hub out of a scan -- but once
# connected, anything matching it is proof of identity.
OUR_DEVICE_UUID = "03970000-3600-1B00-1450-30514B323320"


def is_lego(name, adv):
    if adv.manufacturer_data and LEGO_COMPANY_ID in adv.manufacturer_data:
        return True
    for u in (adv.service_uuids or []):
        if LEGO_SERVICE_16 in u.lower():
            return True
    return "spike" in (name or "").lower()


async def find_hub(seconds):
    """Wait for a LEGO hub and grab it the INSTANT it appears.

    The hub advertises only for a short window after the CONNECT button is
    pressed, so a fixed-length scan turns into a race the human has to win.
    This listens continuously and resolves on first sight instead, which means
    the operator can press the button whenever they like during the window.
    """
    from bleak import BleakScanner

    found = asyncio.Event()
    box = {}

    def on_detect(dev, adv):
        if box:
            return
        name = adv.local_name or dev.name or ""
        if is_lego(name, adv):
            box["dev"] = dev
            box["name"] = name
            box["adv"] = adv
            found.set()

    print("waiting up to %.0f s for a LEGO hub to advertise." % seconds)
    print("PRESS THE CONNECT BUTTON ON THE HUB NOW (the Bluetooth one).")
    print("Nothing may hold the USB serial port while this runs.")

    scanner = BleakScanner(detection_callback=on_detect)
    await scanner.start()
    try:
        await asyncio.wait_for(found.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass
    finally:
        await scanner.stop()

    if not box:
        print("\nNo LEGO hub advertised in that window.")
        print("  A hub advertises only while its Hub OS is RUNNING. If any probe")
        print("  in probes/ touched the USB port since the last power cycle, the")
        print("  Hub OS was interrupted by Ctrl-C and the radio went with it.")
        print("  Power-cycle the hub, stay off the serial port, and retry.")
        return None

    adv = box["adv"]
    print("\nFOUND  %s  rssi %s  %r" % (box["dev"].address, adv.rssi, box["name"]))
    for cid, data in (adv.manufacturer_data or {}).items():
        print("       mfr 0x%04X %s" % (cid, data.hex()))
    return box["dev"]


async def connect(device, listen_s):
    from bleak import BleakClient

    print("\nconnecting to %s (%r) ..." % (device.address, device.name))
    async with BleakClient(device, timeout=20.0) as client:
        print("CONNECTED: %s" % client.is_connected)
        try:
            print("negotiated MTU: %s" % client.mtu_size)
        except Exception:
            print("negotiated MTU: not reported by this backend")

        print("\n--- GATT SERVICES AND CHARACTERISTICS ---")
        notifiables = []
        for service in client.services:
            print("\nservice %s" % service.uuid)
            if service.description:
                print("   %s" % service.description)
            for ch in service.characteristics:
                props = ",".join(ch.properties)
                print("   char %s  [%s]" % (ch.uuid, props))
                if ch.description:
                    print("        %s" % ch.description)
                if "notify" in ch.properties or "indicate" in ch.properties:
                    notifiables.append(ch)
                if "read" in ch.properties:
                    try:
                        val = await client.read_gatt_char(ch)
                        printable = val.decode("utf-8", errors="replace").strip()
                        print("        read: %s" % val.hex())
                        if printable and printable.isprintable():
                            print("        text: %r" % printable)
                        if OUR_DEVICE_UUID.replace("-", "").lower() in val.hex().lower():
                            print("        *** MATCHES OUR USB-READ device_uuid ***")
                    except Exception as exc:
                        print("        read failed: %s" % type(exc).__name__)

        print("\n--- SUMMARY ---")
        print("  %d notifying characteristic(s)" % len(notifiables))
        for ch in notifiables:
            print("    %s" % ch.uuid)

        if listen_s > 0 and notifiables:
            print("\n--- LISTENING %.0f s FOR NOTIFICATIONS ---" % listen_s)
            print("  Press buttons on the hub; move it; watch what arrives.")

            def make_cb(uuid):
                def cb(_handle, data):
                    print("  %s  %3d bytes  %s" % (uuid[:8], len(data), data.hex()))
                return cb

            started = []
            for ch in notifiables:
                try:
                    await client.start_notify(ch, make_cb(ch.uuid))
                    started.append(ch)
                except Exception as exc:
                    print("  could not subscribe to %s: %s" % (ch.uuid[:8], type(exc).__name__))
            await asyncio.sleep(listen_s)
            for ch in started:
                try:
                    await client.stop_notify(ch)
                except Exception:
                    pass

        print("\ndisconnecting cleanly")
    print("disconnected")
    return 0


async def amain(argv):
    try:
        import bleak                                          # noqa: F401
    except ImportError:
        print("NO_BLEAK: python3 -m pip install --user bleak")
        return 5

    listen_s = 0.0
    if "--listen" in argv:
        listen_s = float(argv[argv.index("--listen") + 1])

    # How long to wait for the hub to show up. The default is generous because
    # the operator has to physically press a button, and a short window turns
    # this into a race they have to win.
    wait_s = 90.0
    if "--wait" in argv:
        wait_s = float(argv[argv.index("--wait") + 1])

    # BlueZ will only connect to a device it has seen in THIS session, so we
    # always scan first and hand bleak the discovered object rather than a bare
    # address string. Passing a string that BlueZ has not cached fails with
    # BleakDeviceNotFoundError, which reads like the hub is missing when it is
    # simply not in the cache.
    from bleak import BleakScanner

    wanted = None
    for a in argv[1:]:
        if a.count(":") == 5:
            wanted = a.upper()

    if wanted:
        print("looking for %s (scanning, because BlueZ must see it first)..." % wanted)
        device = await BleakScanner.find_device_by_address(wanted, timeout=15.0)
        if device is None:
            print("\n%s is not advertising right now." % wanted)
            print("  A hub advertises only while its Hub OS is running, and only")
            print("  for a limited window after the CONNECT button is pressed.")
            print("  Press CONNECT again and retry immediately.")
            return 1
    else:
        device = await find_hub(wait_s)
        if device is None:
            return 1
    return await connect(device, listen_s)


if __name__ == "__main__":
    sys.exit(asyncio.run(amain(sys.argv)))
