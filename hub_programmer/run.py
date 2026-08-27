#!/usr/bin/env python3
"""run.py — execute a Python file ON THE HUB and stream its output back.

The companion to upload.py. Where upload.py puts a module on the filesystem to
be imported later, this RUNS a program now.

By default it runs the program IN RAM and leaves nothing behind: the code goes
over the wire through MicroPython's paste mode and is never written to /flash.
That is what makes it safe for experiments -- an example script that turns out
to be wrong does not become litter on shared course equipment.

    ./hub_programmer/run.py examples/imu_verbose.py
    ./hub_programmer/run.py examples/imu_verbose.py --seconds 30
    ./hub_programmer/run.py examples/imu_verbose.py --save data/imu.txt

SAFETY
    * Nothing is written to the hub filesystem. Paste mode executes from RAM.
    * There is always a deadline. When it expires the script sends Ctrl-C to
      interrupt the program, so an infinite loop on the hub cannot hang this
      process -- and cannot hang the session that launched it.
    * The port is closed in a finally: block.
    * It refuses to run a file containing an obvious firmware call, because a
      typo in an example should not be able to reach machine.bootloader().

Exit codes: 0 ran · 1 the program raised · 2 refused · 3 no port/prompt
            4 busy · 5 no pyserial · 64 usage
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "probes"))
import _hubio                                                # noqa: E402

BAUD = 115200
PROMPT = b">>>"
PASTE_ENTER = b"\x05"          # Ctrl-E  -- enter paste mode
PASTE_EXEC = b"\x04"           # Ctrl-D  -- execute what was pasted
INTERRUPT = b"\x03"            # Ctrl-C

# A typo in an experiment must never be able to reach these.
FORBIDDEN = (
    "machine.bootloader", "machine.reset", "machine.soft_reset",
    "hub_os_enable", "os.remove", "os.rmdir", "os.rename", "vfs.mkfs",
    "open('/flash/boot", 'open("/flash/boot', "open('/flash/main", 'open("/flash/main',
)


def screen_for_danger(source):
    hits = [f for f in FORBIDDEN if f in source]
    return hits


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__.split("SAFETY")[0].strip())
        return 64

    local = args[0]
    if not os.path.exists(local):
        print("no such file: %s" % local)
        return 64

    seconds = 20.0
    if "--seconds" in argv:
        seconds = float(argv[argv.index("--seconds") + 1])
    save_to = argv[argv.index("--save") + 1] if "--save" in argv else None

    with open(local, "r") as fh:
        source = fh.read()

    danger = screen_for_danger(source)
    if danger:
        print("REFUSED: %s contains %s" % (local, ", ".join(danger)))
        print("  These can modify the hub or its firmware. Not runnable from here.")
        return 2

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
        ser = serial.Serial(port, BAUD, timeout=0.4, write_timeout=5.0)
    except Exception as exc:
        print("BUSY_OR_DENIED: %s: %s" % (port, exc))
        return 4

    collected = []
    try:
        ser.reset_input_buffer()
        ser.write(INTERRUPT)
        time.sleep(0.3)
        ser.write(b"\r\n")
        time.sleep(0.3)
        if PROMPT not in ser.read(4096):
            print("No '>>>' prompt — the hub is not presenting a REPL.")
            return 3

        print("running %s on the hub (deadline %.0fs, Ctrl-C sent on expiry)" % (local, seconds))
        print("-" * 62)

        # Paste mode: everything until Ctrl-D is buffered, then executed as one
        # unit. This is why indented multi-line code works here and does not at
        # the plain REPL.
        ser.write(PASTE_ENTER)
        time.sleep(0.3)
        ser.read(4096)                                   # swallow the paste-mode banner
        for line in source.splitlines():
            ser.write((line + "\r").encode("utf-8", errors="replace"))
            time.sleep(0.004)                            # do not outrun the hub's parser
        ser.write(PASTE_EXEC)

        started = time.monotonic()
        while time.monotonic() - started < seconds:
            chunk = ser.read(4096)
            if chunk:
                text = chunk.decode("utf-8", errors="replace")
                collected.append(text)
                sys.stdout.write(text)
                sys.stdout.flush()
            elif collected and collected[-1].rstrip().endswith(">>>"):
                break                                    # program finished on its own

        if time.monotonic() - started >= seconds:
            ser.write(INTERRUPT)
            time.sleep(0.3)
            tail = ser.read(4096).decode("utf-8", errors="replace")
            collected.append(tail)
            sys.stdout.write(tail)
            print("\n" + "-" * 62)
            print("deadline reached — sent Ctrl-C to stop the program on the hub")
    finally:
        try:
            ser.write(INTERRUPT)                         # leave the hub at a prompt
            ser.close()
        except Exception:
            pass

    out = "".join(collected)
    if save_to:
        # Paste mode echoes every line of the source back prefixed with '=== '.
        # Keeping that in the artifact buries the actual results under the
        # program that produced them, so strip it. The source is in git.
        clean = "\n".join([ln for ln in out.splitlines()
                           if not ln.startswith("=== ")])
        os.makedirs(os.path.dirname(os.path.abspath(save_to)), exist_ok=True)
        with open(save_to, "w") as fh:
            fh.write("# ran: %s\n# NOTE: this is program OUTPUT; the source is in %s\n\n"
                     % (local, local))
            fh.write(clean + "\n")
        print("\nsaved: %s (%d bytes of output)" % (save_to, len(clean)))

    if "Traceback" in out:
        print("\nThe program RAISED on the hub — see the traceback above.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
