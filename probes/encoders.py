#!/usr/bin/env python3
"""encoders.py — READ-ONLY encoder stream while a human turns the wheels by hand.

Why a probe and not examples/motor_encoder_verbose.py: that one is run via
paste mode, which proved unreliable for a long file on this hub. This uses the
proven one-line-getter path (probes/_hubio) instead -- each sample is a single
REPL expression, read back with a deadline, so it cannot hang and does not
depend on paste mode taking.

It COMMANDS NO MOTION. It only reads absolute_position/relative_position while
YOU turn a wheel by hand. That answers, with zero risk on a desk:
  * which SIGN each wheel produces when turned the forward-driving way
  * how many encoder degrees per full wheel revolution (turn exactly one turn)
  * that both motors' encoders are alive

    python3 probes/encoders.py            # ~30 s, both motors A and B
    python3 probes/encoders.py 45         # for 45 s

Exit codes: 0 prompt seen · 2 no prompt · 3 no port · 4 busy · 5 no pyserial
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hubio                                                # noqa: E402

BAUD = 115200
PROMPT = b">>>"
MOTOR_IDS = (48, 49, 65)


def main(argv):
    seconds = 30.0
    for a in argv[1:]:
        try:
            seconds = float(a)
        except ValueError:
            pass

    try:
        import serial
    except ImportError:
        print("NO_PYSERIAL"); return 5
    port = _hubio.find_port()
    if port is None:
        print("UNKNOWN: no /dev/spike or /dev/ttyACM0"); return 3
    try:
        ser = serial.Serial(port, BAUD, timeout=1.0, write_timeout=2.0)
    except Exception as exc:
        print("BUSY_OR_DENIED: %s" % exc); return 4

    def line(expr, budget=2.5):
        ser.write((expr + "\r\n").encode("ascii"))
        ser.timeout = budget
        raw = ser.read_until(PROMPT, size=8192).decode("utf-8", errors="replace")
        for ln in raw.splitlines():
            s = ln.strip()
            if s and s != ">>>" and s != expr.strip():
                return s
        return ""

    saw = False
    try:
        ser.reset_input_buffer()
        ser.write(b"\x03"); time.sleep(0.3); ser.write(b"\r\n"); time.sleep(0.3)
        if PROMPT in ser.read(4096):
            saw = True
        # Which ports have motors? One safe one-liner per port.
        present = []
        for L in ("A", "B", "C", "D", "E", "F"):
            r = line("import device;from hub import port;exec(\"try:\\n print(device.id(port.%s))\\nexcept: print(-1)\")" % L)
            try:
                if int(r.strip()) in MOTOR_IDS:
                    present.append(L)
            except Exception:
                pass
        print("motors (device.id %s) on ports: %s" % ("/".join([str(i) for i in MOTOR_IDS]),
                                                       present or "NONE FOUND"))
        if not present:
            print("no motors detected; nothing to stream"); return 2

        print("\nTURN A WHEEL BY HAND -- the way that drives the robot FORWARD.")
        print("Do the LEFT wheel first, then the RIGHT. Watch the sign.\n")
        hdr = "  t(s) " + "".join(["  %s:abs   %s:rel " % (L, L) for L in present])
        print(hdr)

        t0 = time.monotonic()
        start = {}
        while time.monotonic() - t0 < seconds:
            row = "  %4.1f " % (time.monotonic() - t0)
            for L in present:
                a = line("import motor;from hub import port;print(motor.absolute_position(port.%s), motor.relative_position(port.%s))" % (L, L), budget=1.5)
                parts = a.split()
                if len(parts) >= 2:
                    ab, rel = parts[0], parts[1]
                    start.setdefault(L, rel)
                    row += " %6s %6s " % (ab, rel)
                else:
                    row += "   ?      ?   "
            print(row)
            time.sleep(0.4)

        print("\nNet relative movement (turn one full revolution to read deg/rev):")
        for L in present:
            last = line("import motor;from hub import port;print(motor.relative_position(port.%s))" % L)
            try:
                net = int(last) - int(start.get(L, "0"))
            except Exception:
                net = "?"
            print("  motor %s: net %s encoder-deg  (sign shows forward direction)" % (L, net))
    finally:
        try:
            ser.close()
        except Exception:
            pass
    return 0 if saw else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
