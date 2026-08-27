#!/usr/bin/env python3
"""import_check.py — do our uploaded modules actually import ON THE HUB?

Uploading a file and verifying its hash proves the bytes arrived. It does NOT
prove the module works: MicroPython is a subset, and our pure modules were
written on a laptop running CPython 3.10. f-strings, dataclasses, enum, typing
and plenty else are absent or different on the hub.

This is the check that catches that. It imports each module and reports what
the hub says -- an ImportError or a SyntaxError here is a real result and the
whole reason to run it before writing mission code.

READ-ONLY in the sense that matters: it writes nothing to the filesystem. It
does execute module top-level code by importing it, which for our pure modules
is constants and function definitions.

    python3 probes/import_check.py                 # check what we have uploaded
    python3 probes/import_check.py config detector # check specific modules

Exit codes: 0 all imported · 1 at least one failed · 2 no prompt · 3 no port
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hubio                                                # noqa: E402

# The pure modules, in dependency order -- config first, since others import it.
DEFAULT = ["config", "calibration", "detector", "sweep",
           "result", "odometry", "classify", "telemetry"]


def main(argv):
    wanted = [a for a in argv[1:] if not a.startswith("-")] or DEFAULT

    probes = [("listing", "import os; print(sorted(os.listdir('/flash/lib')))")]
    for m in wanted:
        # One physical line: exec() keeps the REPL out of continuation mode.
        probes.append((
            m,
            'exec("try:\\n import %s\\n print(\'OK %s\')\\n'
            'except Exception as e:\\n print(\'FAIL %s\', type(e).__name__, e)")' % (m, m, m),
        ))
    probes.append(("free memory",
                   "import gc; gc.collect(); print('free', gc.mem_free())"))

    code, text = _hubio.run(probes, deadline=90.0,
                            title="import_check — do uploaded modules import on the hub?")
    if code != _hubio.OK:
        return code

    ok = [m for m in wanted if ("OK %s" % m) in text]
    bad = [m for m in wanted if ("FAIL %s" % m) in text]
    missing = [m for m in wanted if m not in ok and m not in bad]

    print()
    print("SUMMARY")
    print("  imported : %s" % (", ".join(ok) if ok else "none"))
    if bad:
        print("  FAILED   : %s" % ", ".join(bad))
        print("             ^ read the traceback above. A SyntaxError usually means")
        print("               CPython-only syntax (f-strings, typing, dataclasses).")
    if missing:
        print("  no answer: %s  (not uploaded, or the probe timed out)" % ", ".join(missing))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
