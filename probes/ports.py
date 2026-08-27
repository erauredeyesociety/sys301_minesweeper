#!/usr/bin/env python3
"""ports.py — WHAT IS PLUGGED INTO A-F, right now?

Run it before plugging something in and again after. The difference is the
answer to two questions at once:
  * which port did the Builder actually use?
  * does this hub detect a device hot-plugged while it is running?

READ-ONLY. It asks each port to identify itself. It does NOT move a motor,
does NOT set a duty cycle, and does NOT change a device mode. Spinning a motor
is the Builder's call on a built robot, never a probe's on a bare hub.

    python3 probes/ports.py              # what is connected now
    python3 probes/ports.py --watch      # re-read every 2 s, 10 times

Exit codes: 0 prompt seen · 2 no prompt · 3 no port · 4 busy · 5 no pyserial
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hubio                                                # noqa: E402

LETTERS = ["A", "B", "C", "D", "E", "F"]

# device.id() raises when nothing is attached, so every call is wrapped in a
# single-line exec() -- a real multi-line try/except would put the REPL into
# continuation mode and make the reply unparseable.
def port_probe(letter):
    return (
        letter,
        'from hub import port; import device; '
        'exec("try:\\n print(\'%s ready=\', device.ready(port.%s), \'id=\', device.id(port.%s))\\n'
        'except Exception as e:\\n print(\'%s EMPTY\', type(e).__name__)")'
        % (letter, letter, letter, letter),
    )


BASE = [("port constants",
         "from hub import port; print([p for p in dir(port) if not p.startswith('_')])")]

TAIL = [("motor status sweep",
         'import motor; from hub import port; '
         'exec("for L in [\'A\',\'B\',\'C\',\'D\',\'E\',\'F\']:\\n'
         ' try:\\n  print(L, motor.status(getattr(port, L)))\\n'
         ' except Exception as e:\\n  print(L, \'-\', type(e).__name__)")')]


def one_pass(title):
    probes = BASE + [port_probe(l) for l in LETTERS] + TAIL
    return _hubio.run(probes, deadline=70.0, title=title)


def main(argv):
    if "--watch" in argv:
        for i in range(10):
            print("\n########## pass %d ##########" % (i + 1))
            code, _ = one_pass("ports pass %d" % (i + 1))
            if code != _hubio.OK:
                return code
            time.sleep(2.0)
        return 0

    code, text = one_pass("ports — what is attached to A-F")
    print()
    print("READING THIS")
    print("  'EMPTY' means nothing is attached to that port -- device.id() raises")
    print("  when the port is bare, and that exception IS the result, not a bug.")
    print("  An 'id=' number identifies the device type. Record which letter the")
    print("  Builder actually used; the code should not hard-code a guess.")
    print()
    print("  Run this BEFORE and AFTER plugging something in. If a port changes")
    print("  from EMPTY to an id without restarting the hub, hot-plug works and")
    print("  we have MEASURED it rather than assumed it.")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
