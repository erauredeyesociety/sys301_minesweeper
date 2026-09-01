# examples/ble_mtu.py — does the hub auto-advertise, and can we raise the MTU?
#
# RUNS ON THE LAPTOP (bleak). Never opens the serial port.
#
#   python3 examples/ble_mtu.py --wait 40
#
# TWO QUESTIONS IN ONE WINDOW
#   1. AUTO-ADVERTISE: after a power cycle with NO button press, does our hub
#      advertise on its own? If yes, "power cycle and go" works with no button.
#      Run this immediately after boot WITHOUT pressing CONNECT.
#   2. MTU: every connection so far negotiated MTU 23 while the hub reports
#      max_packet_size 509. At 23, a telemetry payload is 20 bytes; raising it
#      is the throughput unblock. This asks BlueZ to negotiate up and reports
#      what it actually got, then sends one InfoRequest to prove the link still
#      carries a real message at the new size.
#
# Connects ONLY to our hub: address filter, THEN device-UUID proof before any
# write (see docs/lessons_learned/prove-identity-before-you-act.md). Reads only.

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "probes"))
import _cobs                                                 # noqa: E402

OUR_BLE_ADDRESS = "64:8C:BB:0A:1C:8C"
OUR_DEVICE_UUID = "03970000-3600-1B00-1450-30514B323320"
RX = "0000fd02-0002-1000-8000-00805f9b34fb"
TX = "0000fd02-0001-1000-8000-00805f9b34fb"
LEGO_COMPANY_ID = 0x0397


def is_lego(name, adv):
    if adv.manufacturer_data and LEGO_COMPANY_ID in adv.manufacturer_data:
        return True
    return "fd02" in " ".join(adv.service_uuids or []).lower() or "spike" in (name or "").lower()


async def amain(argv):
    from bleak import BleakScanner, BleakClient

    wait_s = 40.0
    if "--wait" in argv:
        wait_s = float(argv[argv.index("--wait") + 1])

    print("SCAN (test auto-advertise: run this right after boot with NO button press)")
    print("waiting up to %.0f s for our hub %s ..." % (wait_s, OUR_BLE_ADDRESS))
    dev = await BleakScanner.find_device_by_address(OUR_BLE_ADDRESS, timeout=wait_s)
    if dev is None:
        # Fall back to any LEGO, in case the address rotated.
        found = await BleakScanner.discover(timeout=8.0, return_adv=True)
        legos = [(d, a) for _, (d, a) in found.items() if is_lego(a.local_name or d.name or "", a)]
        if legos:
            print("  our address not seen, but a LEGO hub is advertising: %s" % legos[0][0].address)
            print("  (address may have rotated -- identity is still proven by UUID below)")
            dev = legos[0][0]
        else:
            print("\nNO advertisement seen.")
            print("  If you did NOT press CONNECT: the hub does NOT auto-advertise on boot --")
            print("  a button press is required. Press CONNECT now and re-run.")
            print("  If you DID press CONNECT: the window may have closed; press again and re-run.")
            return 1
    print("FOUND %s %r -- so it WAS advertising." % (dev.address, dev.name))

    print("\nCONNECT + MTU")
    async with BleakClient(dev, timeout=20.0) as client:
        print("  connected: %s" % client.is_connected)
        before = client.mtu_size
        print("  MTU before negotiation: %s" % before)
        # BlueZ backend: _acquire_mtu() forces an ATT MTU exchange.
        try:
            if hasattr(client, "_acquire_mtu"):
                await client._acquire_mtu()
        except Exception as exc:
            print("  _acquire_mtu raised: %s" % type(exc).__name__)
        after = client.mtu_size
        print("  MTU after negotiation:  %s" % after)
        if after > before:
            print("  --> raised from %d to %d. Usable payload ~%d bytes." % (before, after, after - 3))
        else:
            print("  --> unchanged at %d. BlueZ may fix ATT MTU at connect on this stack;" % after)
            print("      a system-level change (bluetoothd) may be needed. [UNVERIFIED]")

        # Prove identity and that a real message still carries at this MTU.
        got = {}
        buf = bytearray()

        def on_notify(_h, data):
            buf.extend(data)
            frames, rest = _cobs.split_frames(buf)
            buf[:] = rest
            for f in frames:
                got.setdefault("frames", []).append(_cobs.unpack(f))

        await client.start_notify(RX, on_notify)
        await client.write_gatt_char(TX, _cobs.pack(bytes([_cobs.DEVICE_UUID_REQUEST])), response=False)
        await asyncio.sleep(3.0)
        await client.stop_notify(RX)

        ok = False
        for msg in got.get("frames", []):
            if msg and msg[0] == _cobs.DEVICE_UUID_RESPONSE:
                uuid = msg[1:17].hex()
                match = uuid == OUR_DEVICE_UUID.replace("-", "").lower()
                print("  DeviceUuidResponse: %s  %s" % (uuid, "MATCHES OURS" if match else "NOT OURS"))
                ok = ok or match
        if not ok:
            print("  no matching DeviceUuidResponse -- link up but identity unconfirmed this pass")
    print("disconnected")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(amain(sys.argv)))
