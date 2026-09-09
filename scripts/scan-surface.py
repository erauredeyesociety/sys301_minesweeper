#!/usr/bin/env python3
"""scan-surface.py — capture one LABELLED surface from the colour sensors. Operator-paced.

You hold the robot over a surface, you say go, this captures it and tags it. One command per
surface, appended to one file:

    ./scripts/scan-surface.py FLOOR
    ./scripts/scan-surface.py YELLOW_NOTE
    ./scripts/scan-surface.py PINK_NOTE
    ./scripts/scan-surface.py BLUE_TAPE

    ./scripts/analyse-survey.py            # then: does the detector actually work here?

This is ALSO the demo-day site-survey tool. The mine colour may change on the day and the floor
may not be the floor we tuned on, so the plan is not to guess in advance — it is to be able to
characterise the real arena in a couple of minutes before a run. Any label works; use the same
label twice and the samples pool.

WHY LABELLED: examples/color_live.py streams unlabelled rows and the operator has to remember
which second was which surface. A mis-attributed surface is worse than no capture, because it
looks like data.

Reads sensors only. Commands no motion.

HOW IT GETS THE PROGRAM ONTO THE HUB — two paths, and the default changed 2026-09-08
    DEFAULT: the program is uploaded to scratch SLOT 19 and started over LEGO's binary control
    protocol, and its print() output comes back as ConsoleNotification 0x21. That path sends **no
    Ctrl-C**, so the **Hub OS stays alive** — Bluetooth, the CONNECT button and slot_upload.py all
    still work after a survey. It does write program.py into slot 19 (a filesystem write, never
    firmware; slot 0 and the mission program are untouched).

    --repl : the old path — run the program in RAM through hub_programmer/run.py, writing nothing to
    the hub. run.py sends Ctrl-C, which KILLS the Hub OS; afterwards run ./scripts/restore-hub-os.py
    or power-cycle. This is also the automatic fallback if the slot path returns no rows, so the tool
    cannot lose a survey — it just tells you the Hub OS went down.

    Why: docs/findings/hub-os-vs-repl-2026-09-08.md
"""

import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "findings", "runs",
                   "surface-survey-%s.txt" % time.strftime("%Y-%m-%d"))
SECONDS = 5.0                 # capture window; --seconds overrides
SLOT = 19                     # scratch slot for surveys -- keeps slot 0 free for the mission program

# The on-hub program. Tokens are substituted with .replace(), never %, because the program itself
# uses % formatting and would fight a host-side % substitution.
HUB_PROGRAM = '''
import time
import color_sensor
import color
from hub import port

LABEL = "__LABEL__"
PORTS = (("C", port.C), ("D", port.D))

NAMES = {}
for _n in dir(color):
    if not _n.startswith("_"):
        NAMES[getattr(color, _n)] = _n


def fmt(v):
    return "" if v is None else str(v)


print("SCAN_BEGIN " + LABEL)
t0 = time.ticks_ms()
n = 0
while time.ticks_diff(time.ticks_ms(), t0) < __MS__:
    t = time.ticks_diff(time.ticks_ms(), t0)
    for pn, p in PORTS:
        try:
            c = color_sensor.color(p)
        except Exception:
            c = None
        try:
            refl = color_sensor.reflection(p)
        except Exception:
            refl = None
        try:
            v = color_sensor.rgbi(p)
        except Exception:
            v = (None, None, None, None)
        print("SV,%s,%s,%d,%s,%s,%s,%s,%s,%s,%s"
              % (LABEL, pn, t, fmt(c), NAMES.get(c, "") if c is not None else "",
                 fmt(refl), fmt(v[0]), fmt(v[1]), fmt(v[2]), fmt(v[3])))
    n += 1
    time.sleep_ms(100)
print("SCAN_END " + LABEL + " ticks=%d" % n)
'''


def median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def summarise(rows, port_name):
    """Compact per-port readout, printed immediately so the operator can re-do a bad hold."""
    sel = [r for r in rows if r[2] == port_name]
    if not sel:
        return "  %s: no rows" % port_name
    rs, gs, bs, refls, names = [], [], [], [], {}
    for r in sel:
        try:
            rr, gg, bb = int(r[7]), int(r[8]), int(r[9])
        except (ValueError, IndexError):
            continue
        tot = rr + gg + bb
        if tot <= 0:
            continue
        rs.append(100.0 * rr / tot)
        gs.append(100.0 * gg / tot)
        bs.append(100.0 * bb / tot)
        if r[6]:
            try:
                refls.append(int(r[6]))
            except ValueError:
                pass
        names[r[5]] = names.get(r[5], 0) + 1
    if not rs:
        return "  %s: %d rows, none usable (no chromaticity)" % (port_name, len(sel))
    top = sorted(names.items(), key=lambda kv: -kv[1])[0][0] if names else "?"
    refl = median(refls)
    return ("  %s: n=%-3d  r%%=%4.1f g%%=%4.1f b%%=%4.1f   refl=%-4s  builtin=%s"
            % (port_name, len(rs), median(rs), median(gs), median(bs),
               "?" if refl is None else int(refl), top))


def sv_rows(lines):
    """Pull the well-formed SV, data rows out of whatever the capture path returned."""
    rows = [ln.strip().split(",") for ln in lines if ln.strip().startswith("SV,")]
    return [r for r in rows if len(r) >= 11]


def capture_via_slot(source, seconds):
    """Upload to a slot, start it, read ConsoleNotification 0x21. NO Ctrl-C, Hub OS survives.

    [UNVERIFIED -- no hardware 2026-09-08.] Built from parts that ARE measured: slot upload +
    ProgramFlow Start + streamed console output ran on our hub 2026-09-03
    (docs/findings/sensor-fusion-and-slot-wall-2026-09-03.md, UPDATE section).
    """
    sys.path.insert(0, os.path.join(REPO, "hub_programmer"))
    import slot_upload                                        # noqa: E402
    lines, tail = [], [""]

    def on_console(text):
        # 0x21 carries whatever piece the hub sent; one printed line can span several
        # messages, so reassemble here rather than trusting message boundaries.
        tail[0] += text
        while "\n" in tail[0]:
            one, tail[0] = tail[0].split("\n", 1)
            lines.append(one)

    code = slot_upload.upload_and_capture(source, SLOT, seconds + 12.0, on_console)
    if tail[0]:
        lines.append(tail[0])
    return code, lines


def capture_via_repl(source, seconds):
    """The original path: run in RAM over the REPL, writing nothing to the hub filesystem.
    hub_programmer/run.py sends Ctrl-C, so THIS STOPS THE HUB OS."""
    scratch = os.environ.get("TMPDIR", "/tmp")
    tmp = os.path.join(scratch, "scan_surface_hub.py")
    with open(tmp, "w") as fh:
        fh.write(source)
    proc = subprocess.run(
        [sys.executable, os.path.join(REPO, "hub_programmer", "run.py"), tmp,
         "--seconds", str(seconds + 12)],
        capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).splitlines()


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__.split("Reads sensors")[0].strip())
        return 64
    label = args[0].strip().upper().replace(" ", "_").replace(",", "")
    seconds = SECONDS
    if "--seconds" in argv:
        seconds = float(argv[argv.index("--seconds") + 1])

    source = (HUB_PROGRAM
              .replace("__LABEL__", label)
              .replace("__MS__", str(int(seconds * 1000))))

    print("=" * 70)
    print("SCANNING: %s   (%.0f s)  -- hold it still" % (label, seconds))
    print("=" * 70)

    how = "REPL" if "--repl" in argv else "slot %d" % SLOT
    if "--repl" in argv:
        code, lines = capture_via_repl(source, seconds)
    else:
        code, lines = capture_via_slot(source, seconds)
        if code == 2:
            # slot_upload proved the hub is NOT ours. Never fall back: the REPL path has no
            # identity check at all, and running a program on someone else's hub is worse than
            # capturing nothing. (Over USB this should be impossible -- say so if it happens.)
            print("")
            print("IDENTITY MISMATCH -- that is not our hub. Nothing captured, nothing run.")
            return 2
        if not sv_rows(lines):
            print("")
            print("no SV rows over the slot path (exit %d) -- falling back to the REPL." % code)
            print("  the fallback sends Ctrl-C and WILL stop the Hub OS. Afterwards:")
            print("    ./scripts/restore-hub-os.py     (or power-cycle: single press off, on)")
            code, lines = capture_via_repl(source, seconds)
            how = "REPL (fallback)"
    # Paste mode echoes the source back prefixed "=== ", so take only real data lines.
    rows = sv_rows(lines)

    if not rows:
        print("\n".join(lines)[-1500:])
        print("")
        print("NO SAMPLES CAPTURED. Nothing was written.")
        print("  path %s, exit %d. Is the hub plugged in and switched on?" % (how, code))
        return 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    new = not os.path.exists(OUT)
    with open(OUT, "a") as fh:
        if new:
            fh.write("# surface survey -- labelled colour-sensor captures\n")
            fh.write("# SV,label,port,t_ms,color_code,color_name,reflection,r,g,b,i\n")
        fh.write("# --- %s  %s  (%.0f s) ---\n" % (label, time.strftime("%H:%M:%S"), seconds))
        for r in rows:
            fh.write(",".join(r) + "\n")

    print("")
    print(summarise(rows, "C"))
    print(summarise(rows, "D"))
    print("")
    print("appended %d rows -> %s   (via %s)" % (len(rows), os.path.relpath(OUT, REPO), how))
    if how.startswith("REPL"):
        print("  ⚠ the REPL path sent Ctrl-C: the Hub OS is now STOPPED (no Bluetooth, no")
        print("    slot upload) until it is restarted -- ./scripts/restore-hub-os.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
