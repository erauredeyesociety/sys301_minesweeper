#!/usr/bin/env python3
"""identify_hub.py — READ-ONLY SPIKE Prime hub identification.

Writes NOTHING to the hub. Every probe is an expression that only reads.
Implements the specification in docs/runbooks/hub-identification.md § 6.

Exit codes:
    0   a '>>>' prompt was observed AND probes ran   (the only success)
    2   port opened but no prompt was ever seen      (UNKNOWN, not failure)
    3   /dev/<port> absent — hub not enumerated
    4   port busy / permission denied
    5   pyserial missing

Never blocks: every read has a pyserial timeout, and an overall deadline is
enforced between probes. The port is closed in a finally: block, always.
"""

import os
import sys
import time

BAUD = 115200
DEADLINE = 30.0          # seconds for the whole run
PER_PROBE = 6.0          # seconds any single probe may take
PROMPT = b">>>"

# READ-ONLY expressions only. See runbook § 0 FORBIDDEN before adding one.
PROBES = [
    ("sys.implementation", "import sys; print(sys.implementation)"),
    ("os.uname",           "import os; print(os.uname())"),
    ("modules",            "help('modules')"),
    ("dir(hub)",           "import hub; print(dir(hub))"),
    ("sys.path",           "import sys; print(sys.path)"),
    ("sys.version",        "import sys; print(sys.version)"),
]


def pick_port():
    for cand in ("/dev/spike", "/dev/ttyACM0"):
        if os.path.exists(cand):
            return cand
    return None


def main():
    try:
        import serial
    except ImportError:
        print("NO_PYSERIAL: python3 -m pip install pyserial")
        return 5

    port = pick_port()
    if port is None:
        print("UNKNOWN: no /dev/spike or /dev/ttyACM0 — hub not enumerated")
        return 3

    started = time.monotonic()
    transcript = []
    saw_prompt = False
    ser = None

    def remaining():
        return DEADLINE - (time.monotonic() - started)

    try:
        ser = serial.Serial(port, BAUD, timeout=1.0, write_timeout=2.0)
    except serial.SerialException as exc:
        print("BUSY_OR_DENIED: %s: %s" % (port, exc))
        return 4

    try:
        transcript.append("# port: %s @ %d 8N1" % (port, BAUD))

        # Interrupt whatever is running and drain, without ever blocking.
        ser.reset_input_buffer()
        ser.write(b"\x03")          # Ctrl-C
        time.sleep(0.3)
        ser.write(b"\x03")          # again: a running program may swallow the first
        time.sleep(0.5)
        ser.write(b"\r\n")
        time.sleep(0.4)

        banner = ser.read(4096)
        if banner:
            transcript.append("# after Ctrl-C, hub said:")
            transcript.append(banner.decode("utf-8", errors="replace"))
        if PROMPT in banner:
            saw_prompt = True

        for name, expr in PROBES:
            if remaining() <= 1.0:
                transcript.append("# DEADLINE reached before probe: %s" % name)
                break

            transcript.append("\n===== %s =====\n>>> %s" % (name, expr))
            try:
                ser.write((expr + "\r\n").encode("ascii"))
            except serial.SerialTimeoutException:
                transcript.append("# WRITE TIMEOUT — hub not accepting input")
                break

            budget = min(PER_PROBE, max(0.5, remaining()))
            ser.timeout = budget
            chunk = ser.read_until(PROMPT, size=65536)
            text = chunk.decode("utf-8", errors="replace")
            transcript.append(text)
            if PROMPT in chunk:
                saw_prompt = True

    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    out = "\n".join(transcript)
    print(out)
    print("\n" + "=" * 60)
    if saw_prompt:
        print("RESULT: REPL prompt observed. Probes above are the hub's own words.")
        return 0
    print("RESULT: NO '>>>' prompt was ever seen. Everything above is raw port")
    print("        traffic, NOT a REPL answer. API generation stays UNKNOWN.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
