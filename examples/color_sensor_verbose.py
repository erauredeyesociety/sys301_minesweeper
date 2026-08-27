# examples/color_sensor_verbose.py — everything the colour sensor says, surface by surface.
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/color_sensor_verbose.py --seconds 90
#
# [UNVERIFIED] NEVER RUN ON REAL HARDWARE. We do not own a colour sensor as of
# 2026-08-27. Written against the API surface read off our own hub
# (docs/archives/hub-baseline/03-api-surface.txt), not against a reading. No
# number in this file was measured and there is no sample output anywhere in
# it. Delete this block the day the sensor arrives, and paste the real output
# into docs/findings/.
#
# ONE question: do the four surfaces the mission cares about SEPARATE for this
# sensor? Arena FLOOR, YELLOW STICKY NOTE (a mine), BLUE PAINTERS TAPE and
# SILVER/GREY DUCT TAPE (both boundary). color(), reflection() and rgbi() are
# printed side by side, one surface at a time, so the three can be compared
# instead of argued about. If two overlap, the DESIGN changes -- different
# tape, or a second cue -- not the threshold. Chromaticity r/(r+g+b) is the
# column to trust and what src/classify.py survives on: raw values move with
# lighting and sensor height, ratios largely do not. The rgbi scale (0-255?
# 0-1024?) is undocumented (src/hub_color.py) and is DERIVED here from the
# range actually seen.
#
# The port is DISCOVERED, never hard-coded: docs/hardware/port-map.md is empty
# and two motors are plugged in.
#
# IT NEVER COMMANDS MOTION and never writes a file. Every call is a getter.
#
# MicroPython notes: no f-strings, no statistics module, no numpy.

import math
import time
import color
import color_sensor
import device
from hub import port

SAMPLES = 40           # readings held per surface
PERIOD_MS = 100        # target interval between readings
SETTLE_MS = 8000       # time the operator gets to move onto the next surface
PRINT_EVERY = 5        # print one row in this many; every sample is kept

# key, what the operator physically does
SURFACES = (
    ("FLOOR", "Rest the sensor on the bare arena FLOOR, clear of tape and notes."),
    ("YELLOW", "A YELLOW STICKY NOTE is a mine. Lay one flat, sensor over its middle."),
    ("BLUE", "BLUE PAINTERS TAPE is boundary. Centre the sensor on it, not its edge."),
    ("GREY", "SILVER/GREY DUCT TAPE is boundary. Centre on it, not its edge."),
)

NAMES = {}
for _n in dir(color):
    if not _n.startswith("_"):
        NAMES[getattr(color, _n)] = _n


def cname(v):
    return NAMES.get(v, "?%r" % (v,))


def safe(fn, arg):
    # An empty port, or one holding a motor, raises. Never return 0 for "no
    # answer" -- the rule src/hub_*.py follows.
    try:
        return fn(arg)
    except Exception as exc:
        return "ERR %s" % exc


def stats(vals):
    lo = min(vals)
    hi = max(vals)
    total = 0
    for v in vals:
        total += v
    return lo, hi, float(total) / len(vals), hi - lo


def chroma(r, g, b):
    t = r + g + b
    if t <= 0:
        return 0.0, 0.0, 0.0
    return float(r) / t, float(g) / t, float(b) / t


print("=" * 62)
print("COLOUR SENSOR DISCOVERY -- color_sensor, four surfaces")
print("=" * 62)

print("\n--- 1. WHAT EXISTS ---")
print("  color_sensor: " + ", ".join([a for a in dir(color_sensor) if not a.startswith("_")]))
print("  color:        " + ", ".join(["%s=%r" % (NAMES[k], k) for k in sorted(NAMES.keys())]))
print("  No GREY, no SILVER. Duct tape has no native class -- color() can only")
print("  call it something it is not, so rgbi() is the only route to it.")

print("\n--- 2. WHICH PORT HAS A COLOUR SENSOR ---")
print("  All six asked, nothing hard-coded. A port counts only if reflection()")
print("  AND rgbi() both answer -- reflection alone may not raise on a motor.")
print("   port  ready       device.id   reflection()  rgbi()")

hits = []
for pname in ("A", "B", "C", "D", "E", "F"):
    p = getattr(port, pname)
    did = safe(device.id, p)
    refl = safe(color_sensor.reflection, p)
    raw = safe(color_sensor.rgbi, p)
    ok = (isinstance(refl, int)
          and isinstance(raw, (tuple, list)) and len(raw) >= 3)
    print("   %-4s  %-11s %-11s %-13s %s"
          % (pname, safe(device.ready, p), did, repr(refl), repr(raw)))
    if ok:
        hits.append((pname, p, did))

found = hits[0][1] if hits else None
if hits:
    print("  => %d answered (%s); using %s, raw device.id %r. Write port AND id"
          % (len(hits), ", ".join([h[0] for h in hits]), hits[0][0], hits[0][2]))
    print("     into docs/hardware/port-map.md.")
else:
    print("  => NO PORT ANSWERED. Sections 3-5 skipped; there is no data to take.")

print("\n--- 3. GUIDED SURFACE SWEEP ---")
print("  SAME HEIGHT over every surface -- roughly its ride height on the robot.")
print("  Different heights make these sections incomparable, and comparing")
print("  them is the only thing they are for.")
if found is None:
    print("  SKIPPED -- no sensor found.")

runs = []
all_ch = [[], [], [], []]
sec = 0
for key, howto in (SURFACES if found is not None else ()):
    sec += 1
    print("\n--- 3.%d SURFACE: %s ---" % (sec, key))
    print("  %s  Sampling starts in %d seconds." % (howto, SETTLE_MS // 1000))
    time.sleep_ms(SETTLE_MS)

    refls = []
    ch = [[], [], [], []]
    hist = {}
    bad = 0
    print("     n  color()     refl |     r     g     b     i |    r'    g'    b'")
    t0 = time.ticks_ms()
    for n in range(SAMPLES):
        c = safe(color_sensor.color, found)
        refl = safe(color_sensor.reflection, found)
        v = safe(color_sensor.rgbi, found)
        if not (isinstance(refl, int)
                and isinstance(v, (tuple, list)) and len(v) >= 3):
            # Dropped, never substituted. A synthetic 0 here would show up in
            # section 4 as a measurement, and it is not one.
            bad += 1
            time.sleep_ms(PERIOD_MS)
            continue

        refls.append(refl)
        for k in range(3):
            ch[k].append(v[k])
            all_ch[k].append(v[k])
        if len(v) > 3:
            ch[3].append(v[3])
            all_ch[3].append(v[3])
        hist[c] = hist.get(c, 0) + 1

        cr, cg, cb = chroma(v[0], v[1], v[2])
        if n % PRINT_EVERY == 0:
            print("   %3d  %-10s %4s | %5s %5s %5s %5s | %5.3f %5.3f %5.3f"
                  % (n, cname(c), refl, v[0], v[1], v[2],
                     v[3] if len(v) > 3 else "-", cr, cg, cb))
        time.sleep_ms(PERIOD_MS)
    elapsed = time.ticks_diff(time.ticks_ms(), t0)

    # The measured cost of one three-call read is what bounds sweep speed.
    print("  %d good, %d unreadable, %d ms => %.1f ms/sample (asked for %d)"
          % (len(refls), bad, elapsed, float(elapsed) / SAMPLES, PERIOD_MS))
    if not refls:
        print("  NOTHING READABLE here. Left out of section 5 rather than compared")
        print("  against a number we do not have.")
        continue
    print("                        min    max     mean  spread")
    lo, hi, mrefl, sp = stats(refls)
    print("    %-12s %6d %6d %8.1f %6d" % ("reflection", lo, hi, mrefl, sp))
    mean_rgb = []
    for k, label in ((0, "rgbi r"), (1, "rgbi g"), (2, "rgbi b"), (3, "rgbi i")):
        if not ch[k]:
            print("    %-12s absent from this rgbi() tuple" % label)
            continue
        lo, hi, mean, sp = stats(ch[k])
        mean_rgb.append(mean)
        print("    %-12s %6d %6d %8.1f %6d" % (label, lo, hi, mean, sp))
    cr, cg, cb = chroma(mean_rgb[0], mean_rgb[1], mean_rgb[2])
    print("    mean chromaticity   r'=%.3f  g'=%.3f  b'=%.3f" % (cr, cg, cb))
    print("    color() said:       "
          + ", ".join(["%s x%d" % (cname(cv), hist[cv]) for cv in hist]))
    runs.append((key, mrefl, cr, cg, cb))

print("\n--- 4. rgbi SCALE, DERIVED FROM WHAT WE ACTUALLY SAW ---")
top = 0
for k, label in ((0, "r"), (1, "g"), (2, "b"), (3, "i")):
    if not all_ch[k]:
        continue
    lo, hi, mean, sp = stats(all_ch[k])
    top = hi if hi > top else top
    print("  channel %s over the whole run: min %6d  max %6d" % (label, lo, hi))
if not all_ch[0]:
    print("  No samples taken. Nothing to derive.")
elif top > 255:
    print("  => it CANNOT be 0-255 -- a channel reached %d. Only a saturating" % top)
    print("     white proves where the ceiling actually is.")
else:
    print("  => INCONCLUSIVE at %d. Both 0-255 and 0-1024 still fit. Hold the" % top)
    print("     sensor close over bright WHITE paper and re-run: a channel past")
    print("     255 settles it. Do not write an absolute threshold until it does.")

print("\n--- 5. SEPARABILITY -- what this whole script exists for ---")
if len(runs) < 2:
    print("  Fewer than two surfaces measured. Nothing to compare.")
else:
    print("   pair                d(reflection)   d(chromaticity)")
    worst = None
    worst_pair = ""
    for a in range(len(runs)):
        for b in range(a + 1, len(runs)):
            ka, ra, ar, ag, ab = runs[a]
            kb, rb, br, bg, bb = runs[b]
            dc = math.sqrt((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2)
            print("   %-18s %11.1f %17.4f" % (ka + " vs " + kb, abs(ra - rb), dc))
            if worst is None or dc < worst:
                worst = dc
                worst_pair = ka + " vs " + kb
    print("  closest pair in chromaticity: %s at %.4f" % (worst_pair, worst))
    print("")
    print("  HOW TO READ IT: compare each gap against the SPREAD printed for those")
    print("  two surfaces in section 3. Gap bigger than both spreads => a threshold")
    print("  exists and src/classify.py can be built. Gap inside them => the answer")
    print("  is a design change (other tape, second cue, lower sensor), not a")
    print("  cleverer number. Trust chromaticity: reflection moves with the room.")

print("\nDONE.")
