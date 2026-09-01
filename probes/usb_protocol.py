#!/usr/bin/env python3
"""usb_protocol.py — does LEGO's COBS control protocol run over the USB CABLE?

THE QUESTION, AND WHY IT MATTERS MORE THAN IT SOUNDS
  /flash/main.py does NOT autorun -- measured 2026-08-27, after a real power
  cycle, with the Hub OS enabled. So the Hub OS owns the boot path and the way
  to run a program is its own SLOT mechanism, which LEGO drives with this
  protocol.

  We have that protocol working over BLE. But BLE means a short advertising
  window, a button press, and a classroom full of look-alike hubs -- we already
  connected to somebody else's by accident. If the SAME protocol answers on the
  USB cable, all of that goes away: the cable is point-to-point, always
  available, and cannot pick the wrong robot.

  This probe finds out, and it is the difference between "we can deploy a
  runnable program" and "we can only deploy an importable module".

HOW IT DIFFERS FROM EVERY OTHER PROBE HERE
  It does NOT send Ctrl-C. Every other probe opens with Ctrl-C to force a
  MicroPython REPL, which interrupts the Hub OS -- and the Hub OS is the thing
  we are trying to talk to. Sending 0x03 here would defeat the experiment.
  LEGO's XOR-by-3 framing guarantees 0x03 never appears in a frame, which is
  precisely what makes this safe on a port that also hosts a REPL.

READ-ONLY: sends InfoRequest and DeviceUuidRequest. Both are queries.

    python3 probes/usb_protocol.py

Exit codes: 0 the hub answered · 2 no answer · 3 no port · 4 busy · 5 no pyserial
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cobs                                                 # noqa: E402
import _hubio                                                # noqa: E402

BAUD = 115200
REQUESTS = (
    ("InfoRequest", _cobs.INFO_REQUEST),
    ("DeviceUuidRequest", _cobs.DEVICE_UUID_REQUEST),
)
OUR_DEVICE_UUID = "03970000-3600-1B00-1450-30514B323320"


def main():
    try:
        import serial
    except ImportError:
        print("NO_PYSERIAL: python3 -m pip install pyserial")
        return 5

    port = _hubio.find_port()
    if port is None:
        print("UNKNOWN: no /dev/spike or /dev/ttyACM0 — hub not enumerated.")
        return 3

    try:
        ser = serial.Serial(port, BAUD, timeout=0.5, write_timeout=3.0)
    except Exception as exc:
        print("BUSY_OR_DENIED: %s: %s" % (port, exc))
        return 4

    print("Speaking LEGO's COBS protocol over %s. NO Ctrl-C is sent." % port)
    print("-" * 66)

    frames = []
    buf = bytearray()
    try:
        ser.reset_input_buffer()
        for label, msg_id in REQUESTS:
            frame = _cobs.pack(bytes([msg_id]))
            print("\n-> %-20s id 0x%02X  as %s" % (label, msg_id, frame.hex(" ")))
            ser.write(frame)
            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline:
                chunk = ser.read(256)
                if chunk:
                    buf.extend(chunk)
                    got, buf = _cobs.split_frames(buf)
                    buf = bytearray(buf)
                    for f in got:
                        frames.append(f)
                        print("<- raw   %s" % f.hex(" "))
    finally:
        try:
            ser.close()
        except Exception:
            pass

    print("\n" + "=" * 66)
    if not frames:
        print("NO FRAMES CAME BACK.")
        print("  This almost certainly means the LEGO Hub OS is NOT RUNNING right now.")
        print("  The Hub OS answers this protocol, AND runs the CONNECT button, AND")
        print("  the BLE advertising -- and a prior Ctrl-C from any probe interrupts it.")
        print("  Once interrupted it does NOT recover on its own: it needs a restart")
        print("  (power cycle, or machine.soft_reset()). This protocol DID answer over")
        print("  USB on a freshly-booted hub -- see docs/findings/ (harvest phase 1) --")
        print("  so 'no frames' is a state, not a firmware limitation.")
        print("  Fix: restart the hub and run THIS (no Ctrl-C) before any REPL probe.")
        return 2

    print("THE HUB ANSWERED OVER USB. %d frame(s)." % len(frames))
    for f in frames:
        msg = _cobs.unpack(f)
        print("\n  decoded: %s" % msg.hex(" "))
        if not msg:
            continue
        print("  message id 0x%02X" % msg[0])
        info = _cobs.parse_info_response(msg)
        if info:
            for k, v in info.items():
                print("    %-22s %s" % (k, v))
        if msg[0] == _cobs.DEVICE_UUID_RESPONSE:
            got = msg[1:17].hex()
            print("    device uuid            %s" % got)
            if got.lower() == OUR_DEVICE_UUID.replace("-", "").lower():
                print("    *** matches our USB-read UUID -- identity confirmed ***")

    print("\nWHY THIS IS THE UNBLOCK")
    print("  The control protocol is reachable on the cable, so a program can be")
    print("  uploaded to a SLOT and started WITHOUT the BLE advertising window,")
    print("  without a button press, and with no chance of hitting another team's")
    print("  hub. The Hub OS stays running, so print() still reaches BLE as a")
    print("  ConsoleNotification -- which is the telemetry path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
