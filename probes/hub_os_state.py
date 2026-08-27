#!/usr/bin/env python3
"""hub_os_state.py — is the LEGO Hub OS actually RUNNING right now?

The question behind the question. /flash/boot.py sets
hub.config["hub_os_enable"] = True, so the Hub OS starts at boot -- but it is a
PROGRAM, and every probe in this folder opens by sending Ctrl-C to get a REPL
prompt. Ctrl-C interrupts programs. If we have been killing the Hub OS on every
connection, that would explain a hub that is powered and healthy and completely
silent over Bluetooth.

This looks for evidence either way WITHOUT restarting anything:
  * the 5x5 light matrix -- a live Hub OS draws its menu there, so lit pixels
    mean something is running and an all-dark matrix means nothing is drawing
  * the CONNECT button light
  * whether the button reads as pressed

READ-ONLY. It does not soft-reset, does not write, does not set a pixel.
Turning the display ON would destroy the evidence it is trying to collect.

    python3 probes/hub_os_state.py

Exit codes: 0 prompt seen · 2 no prompt · 3 no port · 4 busy · 5 no pyserial
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hubio                                                # noqa: E402

PROBES = [
    # The matrix as a whole. Any non-zero pixel means something is drawing.
    ("light_matrix pixels",
     "import hub; print([hub.light_matrix.get_pixel(x, y) "
     "for y in range(5) for x in range(5)])"),

    ("light_matrix total",
     "import hub; print('sum of all 25 pixels =', "
     "sum([hub.light_matrix.get_pixel(x, y) for y in range(5) for x in range(5)]))"),

    # Button states. All should read False if nobody is touching the hub.
    ("buttons",
     "import hub; b = hub.button; "
     "print('LEFT', b.pressed(b.LEFT), 'RIGHT', b.pressed(b.RIGHT), "
     "'CONNECT', b.pressed(b.CONNECT))"),

    ("button constant values",
     "import hub; b = hub.button; print('LEFT', b.LEFT, 'RIGHT', b.RIGHT, "
     "'CONNECT', b.CONNECT, 'POWER', b.POWER)"),

    ("light constants",
     "import hub; print('CONNECT', hub.light.CONNECT, 'POWER', hub.light.POWER)"),

    # What is the runtime actually doing?
    ("running modules",
     "import sys; print(sorted([m for m in sys.modules]))"),

    ("__main__ contents",
     "import sys; print(dir(sys.modules['__main__']) "
     "if '__main__' in sys.modules else 'no __main__')"),

    ("free memory",
     "import gc; gc.collect(); print('free', gc.mem_free(), 'alloc', gc.mem_alloc())"),
]


def main():
    code, text = _hubio.run(
        PROBES, deadline=60.0,
        title="hub_os_state — is the Hub OS running, or did we interrupt it?")
    print()
    print("READING THIS")
    print("  All 25 pixels reading 0 means NOTHING is drawing to the matrix.")
    print("  A live Hub OS shows its program menu, so an all-dark matrix is")
    print("  evidence we interrupted it with Ctrl-C -- and a stopped Hub OS")
    print("  cannot be running the Bluetooth stack that owns the radio.")
    print()
    print("  It is NOT proof: the Hub OS may idle the display. The decisive")
    print("  test is to power-cycle the hub, stay off the serial port")
    print("  entirely, and watch for an advertisement with:")
    print("    python3 examples/ble_watch.py 60")
    return code


if __name__ == "__main__":
    sys.exit(main())
