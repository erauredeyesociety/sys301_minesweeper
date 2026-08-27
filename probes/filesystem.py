#!/usr/bin/env python3
"""filesystem.py — what is on the hub's flash, and where would OUR code go?

os.listdir('/flash') returned README.txt, boot.py, config, main.py, program,
pybcdc.inf. sys.path is ['', '.frozen', '/flash', '/flash/lib']. Between them
that is the whole answer to "how do we deploy without the LEGO app" -- but only
if we read what is actually there instead of assuming.

STRICTLY READ-ONLY. Listings and file reads only. It does NOT write, delete,
rename, or create anything, and it never touches /flash/program contents in a
way that could disturb a stored program.

READS ARE TRUNCATED on purpose: a huge file would flood the serial link and
blow the deadline. Sizes are reported separately so truncation is visible.

    python3 probes/filesystem.py

Exit codes: 0 prompt seen · 2 no prompt · 3 no port · 4 busy · 5 no pyserial
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hubio                                                # noqa: E402

CAP = 1200          # bytes of any one file we are willing to pull over serial

PROBES = [
    ("listing /flash",
     "import os; print(os.listdir('/flash'))"),

    ("sizes",
     "import os; print([(f, os.stat('/flash/'+f)[6]) for f in os.listdir('/flash')])"),

    ("is there a lib/?",
     "import os; print('lib' in os.listdir('/flash'), os.listdir('/flash/lib') if 'lib' in os.listdir('/flash') else 'NO /flash/lib')"),

    ("program slots",
     "import os; print(os.listdir('/flash/program') if 'program' in os.listdir('/flash') else 'no program dir')"),

    ("config entry",
     "import os; print('config', os.stat('/flash/config')[0], os.stat('/flash/config')[6])"),

    ("README.txt",
     "print(open('/flash/README.txt').read(%d))" % CAP),

    ("boot.py",
     "print(open('/flash/boot.py').read(%d))" % CAP),

    ("main.py",
     "print(open('/flash/main.py').read(%d))" % CAP),

    ("filesystem free space",
     "import os; s = os.statvfs('/flash'); print('block', s[0], 'total', s[2], 'free', s[3], '=> bytes free', s[0]*s[3])"),

    ("mount points",
     "import os; print(os.listdir('/'))"),
]


def main():
    code, text = _hubio.run(
        PROBES,
        deadline=70.0,
        title="filesystem — read-only listing and reads of /flash",
    )
    print()
    print("WHY THIS MATTERS")
    print("  /flash/lib is on sys.path. If it exists and is writable, our pure")
    print("  modules (config, detector, sweep, odometry, ...) can live there and")
    print("  be imported by a program, without the LEGO app being involved.")
    print("  'program' is where stored slots live -- do not disturb them.")
    print("  Free space bounds how much we can deploy; record it.")
    return code


if __name__ == "__main__":
    sys.exit(main())
