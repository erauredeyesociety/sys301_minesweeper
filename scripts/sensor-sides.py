#!/usr/bin/env python3
"""sensor-sides.py — work out WHICH COLOUR SENSOR IS LEFT AND WHICH IS RIGHT, by covering them.

    ./scripts/sensor-sides.py

You cover one sensor with a finger when prompted, then the other. It reports which PORT is on which
SIDE. Run it whenever the robot has been reassembled — including on demo day.

WHY THIS EXISTS
    docs/hardware/port-map.md records the MOTORS as physically confirmed (A = left, B = right) but for
    the colour sensors says only "mounted low, underneath" and "straddling robot width". The SIDE has
    never been confirmed, and the port map's own rule is that a blank in that column means the row is a
    plan and the code must not rely on it.

    It matters most for LINE FOLLOWING: the steering rule is "turn toward the sensor that sees the
    line". Get the sides backwards and the robot steers AWAY from the tape and loses it immediately.
    A cable swapped during assembly silently inverts that, and nothing else would catch it.

THE METHOD -- arrived at the hard way, 2026-09-08
    The probe is a STICKY NOTE, not a finger, and the baseline is BARE CARPET.

    Two earlier attempts failed and both failures were informative. Covering with a finger does not
    work: bare carpet already reads ~5, at the bottom of the scale, so a cover that DARKENS has
    nowhere to go. Putting paper under both sensors does not work either -- MEASURED, the sensors are
    spaced further apart than one sticky note, so it only ever covers one of them and the baseline
    comes out lopsided, which makes that sensor look like it "changed" in every phase.

    Carpet -> note is the right way round: it is a rise of 35-60 points (carpet 3-9, note 40-70,
    MEASURED docs/findings/runs/surface-survey-2026-09-08.txt), it needs only one small note, and it
    uses the exact surface the mission cares about. Held CLOSE the note saturates to ~99 and the
    built-in colour reads WHITE -- an even bigger, more unambiguous swing.

    THE PROBE CAN BE A NOTE OR A FINGERTIP, held just under the sensor and NOT touching the lens.
    Either is fine, because the test compares each port against ITS OWN baseline and only asks which
    one moved further. Nothing depends on the probe's absolute reflectance -- so a fingertip works
    regardless of the operator's skin tone, and so does any pale object to hand.

    Do NOT press a finger flat against the lens: it smears the optical window, and it is an odd
    optical case -- MEASURED 2026-09-08, one such run drove port C to 0 while port D rose 9 -> 47.
    Held slightly clear of the lens instead, the change is clean.

HOW IT DECIDES
    It does NOT assume covering makes the reading brighter or darker -- a finger is close and pale, the
    carpet is dark and far, so the sign depends on the surface underneath. It looks at which port
    CHANGES MOST from its own uncovered baseline. That works whichever way the change goes.

    If both ports change by a similar amount it says so and refuses to guess -- that means the finger
    covered both, or neither.

⚠ This uses hub_programmer/run.py, which sends Ctrl-C and KILLS the Hub OS. POWER-CYCLE the hub before
  the next slot upload (see docs/findings/colour-survey-and-first-detection-2026-09-08.md § 7).

Reads sensors only. Commands no motion. Writes nothing to the hub filesystem.
"""

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SETTLE_S = 4          # time to get your finger into position between phases
CAPTURE_S = 3         # time held still while sampling
# A port must change by at least this many reflectance points to count as "covered". Carpet reads 3-9
# and a finger at close range reads far higher, so a real cover is tens of points -- MEASURED
# 2026-09-08, docs/findings/runs/surface-survey-2026-09-08.txt.
MIN_CHANGE = 15
# The covered port must change at least this many times more than the other one, or the result is
# ambiguous (a finger over both, or over neither) and we refuse to guess.
MIN_RATIO = 3.0

HUB_PROGRAM = '''
import time
import color_sensor
from hub import port

PORTS = (("C", port.C), ("D", port.D))
SETTLE_MS = __SETTLE__
CAPTURE_MS = __CAPTURE__


def beep(hz, ms):
    try:
        import hub
        hub.sound.beep(hz, ms, 20)
    except Exception:
        pass


def refl(p):
    try:
        return color_sensor.reflection(p)
    except Exception:
        return None


def phase(tag, prompt):
    print("")
    print(">>> " + prompt)
    for s in range(SETTLE_MS // 1000, 0, -1):
        print("    %d ..." % s)
        beep(660, 60)
        time.sleep_ms(1000)
    beep(1320, 80)
    print("    HOLD STILL -- sampling " + tag)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < CAPTURE_MS:
        for pn, p in PORTS:
            v = refl(p)
            print("SS,%s,%s,%s" % (tag, pn, "" if v is None else str(v)))
        time.sleep_ms(100)
    beep(330, 150)


print("SENSOR SIDE TEST -- keep the robot still throughout")
print("SETUP: robot on BARE CARPET. PROBE = a sticky note OR a fingertip held just under")
print("       the sensor -- close but NOT touching the lens. Either works.")
phase("BASE", "Nothing under either sensor. Hands OFF. (expect both to read under 10)")
phase("LEFT", "Put the PROBE under the LEFT sensor only -- close, NOT touching.")
phase("RIGHT", "Move the PROBE to under the RIGHT sensor only.")
print("")
print("SS_DONE")
'''


def median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def main():
    source = (HUB_PROGRAM
              .replace("__SETTLE__", str(int(SETTLE_S * 1000)))
              .replace("__CAPTURE__", str(int(CAPTURE_S * 1000))))
    tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), "sensor_sides_hub.py")
    with open(tmp, "w") as fh:
        fh.write(source)

    budget = 3 * (SETTLE_S + CAPTURE_S) + 15
    proc = subprocess.Popen(
        [sys.executable, os.path.join(REPO, "hub_programmer", "run.py"), tmp,
         "--seconds", str(budget)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    # Tee: the operator MUST see the prompts as they happen, and we need the rows for the verdict.
    # Data rows are suppressed from the terminal so the prompts are not buried.
    rows = []
    for line in proc.stdout:
        t = line.rstrip()
        if t.startswith("SS,"):
            f = t.split(",")
            if len(f) == 4 and f[3] != "":
                try:
                    rows.append((f[1], f[2], int(f[3])))
                except ValueError:
                    pass
        else:
            print(t)
            sys.stdout.flush()
    proc.wait()

    if not rows:
        print("")
        print("NO SAMPLES. Is the hub plugged in and at a REPL prompt? (run.py exit %d)"
              % proc.returncode)
        return 1

    def med(tag, port_name):
        vals = [v for (t, p, v) in rows if t == tag and p == port_name]
        return median(vals)

    base = dict((p, med("BASE", p)) for p in ("C", "D"))
    print("")
    print("=" * 62)
    print("  phase    port C   port D")
    print("  " + "-" * 30)
    for tag in ("BASE", "LEFT", "RIGHT"):
        print("  %-7s %7s  %7s"
              % (tag,
                 "--" if med(tag, "C") is None else "%.0f" % med(tag, "C"),
                 "--" if med(tag, "D") is None else "%.0f" % med(tag, "D")))

    if base["C"] is None or base["D"] is None:
        print("\nNo baseline for one sensor -- cannot decide.")
        return 1

    def decide(tag):
        """Which port moved furthest from ITS OWN baseline during this phase, or None if unclear."""
        deltas = {}
        for p in ("C", "D"):
            m = med(tag, p)
            deltas[p] = None if m is None else abs(m - base[p])
        if deltas["C"] is None or deltas["D"] is None:
            return (None, deltas)
        hi, lo = ("C", "D") if deltas["C"] >= deltas["D"] else ("D", "C")
        if deltas[hi] < MIN_CHANGE:
            return (None, deltas)                       # nothing was really covered
        if deltas[lo] > 0 and deltas[hi] / max(deltas[lo], 1e-9) < MIN_RATIO:
            return (None, deltas)                       # both moved -- ambiguous
        return (hi, deltas)

    left_port, dl = decide("LEFT")
    right_port, dr = decide("RIGHT")
    print("")
    print("  change vs baseline -- LEFT phase:  C %s  D %s"
          % (dl.get("C"), dl.get("D")))
    print("  change vs baseline -- RIGHT phase: C %s  D %s"
          % (dr.get("C"), dr.get("D")))
    print("=" * 62)
    print("")

    if left_port and right_port and left_port != right_port:
        print("  RESULT:  LEFT = port %s        RIGHT = port %s" % (left_port, right_port))
        print("  Both phases agree, and they name different ports. This is a solid result.")
        print("")
        print("  Record it in docs/hardware/port-map.md with today's date.")
        return 0

    # Two phases that disagree, or one that was unclear, is NOT a result. Say so rather than
    # picking the more confident half -- a wrong side silently inverts every line-following rule.
    print("  INCONCLUSIVE -- not recording a guess.")
    if left_port and right_port and left_port == right_port:
        print("    Both phases pointed at port %s. The same sensor was probably covered twice," % left_port)
        print("    or one finger covered both. Re-run and check you are moving between them.")
    else:
        print("    A phase showed no clear change (needs >= %d points, and >= %.0fx the other port)."
              % (MIN_CHANGE, MIN_RATIO))
        print("    Cover the sensor fully, close to the lens, and keep the robot still. Re-run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
