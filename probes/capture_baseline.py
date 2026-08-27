#!/usr/bin/env python3
"""capture_baseline.py — snapshot the hub EXACTLY as we found it.

The point is not the snapshot. The point is the DIFF.

If anything on this hub ever changes -- by us, by a teammate, by the LEGO app,
by a firmware update somebody accepted -- we need to be able to prove what
changed rather than argue about it. So this writes one file per probe into
docs/archives/hub-baseline/, in a stable order with stable formatting, and you
compare later runs against it with plain diff.

    python3 probes/capture_baseline.py                # write the baseline
    python3 probes/capture_baseline.py --to /tmp/now  # capture elsewhere
    diff -ru docs/archives/hub-baseline /tmp/now      # what changed since?

STRICTLY READ-ONLY on the hub. Listings, dir(), getters, and file reads. It
writes only to the HOST filesystem.

Exit codes: 0 captured · 2 no prompt · 3 no port · 4 busy · 5 no pyserial
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hubio                                                # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DEST = os.path.join(REPO, "docs", "archives", "hub-baseline")

# (filename, deadline, [(label, read-only expression), ...])
GROUPS = [
    ("01-identity.txt", 45.0, [
        ("uname",           "import os; print(os.uname())"),
        ("implementation",  "import sys; print(sys.implementation)"),
        ("version",         "import sys; print(sys.version)"),
        ("path",            "import sys; print(sys.path)"),
        ("device_uuid",     "import hub; print(hub.device_uuid())"),
        ("hardware_id",     "import hub; print(hub.hardware_id())"),
        ("machine unique_id", "import machine; print(machine.unique_id())"),
        ("platform",        "import platform; print(platform.platform())"),
    ]),

    ("02-modules.txt", 30.0, [
        ("help modules",    "help('modules')"),
    ]),

    ("03-api-surface.txt", 70.0, [
        ("dir hub",             "import hub; print(dir(hub))"),
        ("dir motor",           "import motor; print(dir(motor))"),
        ("dir motor_pair",      "import motor_pair; print(dir(motor_pair))"),
        ("dir runloop",         "import runloop; print(dir(runloop))"),
        ("dir color_sensor",    "import color_sensor; print(dir(color_sensor))"),
        ("dir color",           "import color; print(dir(color))"),
        ("dir color_matrix",    "import color_matrix; print(dir(color_matrix))"),
        ("dir distance_sensor", "import distance_sensor; print(dir(distance_sensor))"),
        ("dir force_sensor",    "import force_sensor; print(dir(force_sensor))"),
        ("dir device",          "import device; print(dir(device))"),
        ("dir orientation",     "import orientation; print(dir(orientation))"),
        ("dir motion_sensor",   "import hub; print(dir(hub.motion_sensor))"),
        ("dir light_matrix",    "import hub; print(dir(hub.light_matrix))"),
        ("dir light",           "import hub; print(dir(hub.light))"),
        ("dir button",          "import hub; print(dir(hub.button))"),
        ("dir sound",           "import hub; print(dir(hub.sound))"),
        ("dir port",            "import hub; print(dir(hub.port))"),
        ("dir bluetooth",       "import bluetooth; print(dir(bluetooth))"),
        ("dir bluetooth.BLE",   "import bluetooth; print(dir(bluetooth.BLE))"),
        ("dir machine",         "import machine; print(dir(machine))"),
        ("dir vfs",             "import vfs; print(dir(vfs))"),
    ]),

    ("04-filesystem.txt", 70.0, [
        ("root",            "import os; print(os.listdir('/'))"),
        ("flash",           "import os; print(sorted(os.listdir('/flash')))"),
        ("sizes",           "import os; print(sorted((f, os.stat('/flash/'+f)[6]) for f in os.listdir('/flash')))"),
        ("modes",           "import os; print(sorted((f, os.stat('/flash/'+f)[0]) for f in os.listdir('/flash')))"),
        ("program dir",     "import os; print(sorted(os.listdir('/flash/program')))"),
        ("config dir",      "import os; print(sorted(os.listdir('/flash/config')))"),
        ("statvfs",         "import os; print(os.statvfs('/flash'))"),
    ]),

    # The pristine contents of every stock file. This is the group that matters
    # most: if we ever overwrite main.py, this is what it said beforehand.
    ("05-stock-files.txt", 70.0, [
        ("README.txt",      "print(open('/flash/README.txt').read())"),
        ("boot.py",         "print(open('/flash/boot.py').read())"),
        ("main.py",         "print(open('/flash/main.py').read())"),
    ]),

    ("06-runtime-state.txt", 40.0, [
        ("battery_voltage", "import hub; print(hub.battery_voltage())"),
        ("battery_current", "import hub; print(hub.battery_current())"),
        ("temperature",     "import hub; print(hub.temperature())"),
        ("mem",             "import gc; gc.collect(); print('free', gc.mem_free(), 'alloc', gc.mem_alloc())"),
    ]),
]

# Values that legitimately differ every run. Kept in the capture, but flagged so
# a future diff is not read as "something changed on the hub" when it did not.
VOLATILE = "06-runtime-state.txt"


def main(argv):
    dest = DEFAULT_DEST
    if "--to" in argv:
        dest = argv[argv.index("--to") + 1]
    os.makedirs(dest, exist_ok=True)

    written, failed = [], []
    for filename, deadline, probes in GROUPS:
        print("--- %s" % filename)
        code, text = _hubio.run(probes, deadline=deadline,
                                title=filename, echo=False)
        if code != _hubio.OK:
            print("    FAILED (exit %d) — not written" % code)
            failed.append(filename)
            continue
        header = ["# hub baseline: %s" % filename,
                  "# READ-ONLY capture. Compare later runs with:",
                  "#   python3 probes/capture_baseline.py --to /tmp/now",
                  "#   diff -ru docs/archives/hub-baseline /tmp/now"]
        if filename == VOLATILE:
            header.append("# NOTE: these values change every run by design "
                          "(battery, temperature, free memory).")
            header.append("# A diff here is expected and means nothing on its own.")
        path = os.path.join(dest, filename)
        with open(path, "w") as fh:
            fh.write("\n".join(header) + "\n\n" + text + "\n")
        print("    wrote %s" % path)
        written.append(filename)

    print()
    print("=" * 62)
    if failed:
        print("INCOMPLETE: %d group(s) failed: %s" % (len(failed), ", ".join(failed)))
        print("The baseline is NOT trustworthy until every group captures.")
        return 2
    print("Baseline captured: %d files in %s" % (len(written), dest))
    print("Nothing was written to the hub.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
