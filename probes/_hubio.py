"""_hubio.py — the one safe way this project talks to the hub over USB.

Every probe script in ./probes/ imports run() from here. Nothing else opens
the serial port. That is deliberate: a hand-typed `screen` or `cat /dev/ttyACM0`
blocks forever and hangs the session, which is why probes are scripts.

SAFETY CONTRACT — do not weaken any of these:
  * READ-ONLY. Probes may call dir(), getters, and listings. They may NOT move a
    motor, write a file, change a setting, or touch firmware.
  * Never a bare read(). Every read has a pyserial timeout AND an overall deadline.
  * The port is closed in a finally: block, always.
  * Success means a '>>>' was actually observed -- never merely "no exception".

Exit codes shared by every probe:
    0  REPL prompt observed, output is the hub's own words
    2  port opened but no prompt ever appeared  (UNKNOWN, not success)
    3  no /dev/spike or /dev/ttyACM0            (hub not enumerated)
    4  port busy or permission denied
    5  pyserial missing
"""

import os
import sys
import time

BAUD = 115200
PROMPT = b">>>"
PER_PROBE = 6.0

NO_PYSERIAL, NO_PORT, BUSY, NO_PROMPT, OK = 5, 3, 4, 2, 0


def find_port():
    """The udev rule gives us /dev/spike; fall back to the raw node."""
    for cand in ("/dev/spike", "/dev/ttyACM0"):
        if os.path.exists(cand):
            return cand
    return None


def run(probes, deadline=60.0, title="", echo=True):
    """Send read-only expressions to the hub REPL and return (exit_code, text).

    probes  -- list of (label, expression) pairs. READ-ONLY expressions only.
    deadline -- seconds for the whole run, enforced between probes.
    """
    try:
        import serial
    except ImportError:
        print("NO_PYSERIAL: python3 -m pip install pyserial")
        return NO_PYSERIAL, ""

    port = find_port()
    if port is None:
        print("UNKNOWN: no /dev/spike or /dev/ttyACM0 — hub not enumerated.")
        print("         Plug in the USB cable and switch the hub on.")
        return NO_PORT, ""

    started = time.monotonic()
    out = []
    if title:
        out.append("# %s" % title)
    out.append("# port %s @ %d 8N1   deadline %.0fs" % (port, BAUD, deadline))
    saw_prompt = False
    ser = None

    def left():
        return deadline - (time.monotonic() - started)

    try:
        ser = serial.Serial(port, BAUD, timeout=1.0, write_timeout=2.0)
    except Exception as exc:                      # SerialException and friends
        print("BUSY_OR_DENIED: %s: %s" % (port, exc))
        print("  Something holds the port. Check: fuser -v %s" % port)
        print("  A Chrome tab with the SPIKE web app holds it EXCLUSIVELY.")
        return BUSY, ""

    try:
        # Interrupt whatever is running, twice -- a busy loop can eat the first.
        ser.reset_input_buffer()
        ser.write(b"\x03")
        time.sleep(0.3)
        ser.write(b"\x03")
        time.sleep(0.3)
        ser.write(b"\r\n")
        time.sleep(0.4)
        if PROMPT in ser.read(4096):
            saw_prompt = True

        for label, expr in probes:
            if left() <= 1.0:
                out.append("\n# DEADLINE reached before: %s" % label)
                break
            out.append("\n===== %s =====" % label)
            try:
                ser.write((expr + "\r\n").encode("ascii"))
            except Exception:
                out.append("# WRITE TIMEOUT — hub stopped accepting input")
                break
            ser.timeout = min(PER_PROBE, max(0.5, left()))
            chunk = ser.read_until(PROMPT, size=65536)
            if PROMPT in chunk:
                saw_prompt = True
            out.append(_clean(chunk.decode("utf-8", errors="replace"), expr))
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    text = "\n".join(out)
    if echo:
        print(text)
        print("\n" + "=" * 62)
        if saw_prompt:
            print("RESULT: REPL prompt observed — the above is the hub's own words.")
        else:
            print("RESULT: no '>>>' ever seen — the above is NOT a REPL answer.")
    return (OK if saw_prompt else NO_PROMPT), text


def _clean(text, expr):
    """Drop the REPL's echo of our own command and the trailing prompt."""
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s == ">>>":
            continue
        if s == expr.strip() or s.lstrip() == expr.strip():
            continue
        lines.append(ln.rstrip())
    return "\n".join(lines)


def value(text, label):
    """Pull one probe's output back out of a transcript, for scripts that parse."""
    marker = "===== %s =====" % label
    if marker not in text:
        return None
    tail = text.split(marker, 1)[1]
    for stop in ("\n=====", "\n# DEADLINE"):
        if stop in tail:
            tail = tail.split(stop, 1)[0]
    return tail.strip() or None
