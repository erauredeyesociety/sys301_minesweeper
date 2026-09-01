# examples/color_classify_demo.py — read BOTH colour sensors and CLASSIFY each
# reading, side by side with the sensor's own guess, so we can see what separates.
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/color_classify_demo.py
#
# THIS IS THE SOFTWARE HALF OF GATE 1 (colour separability). color_live.py is the
# measurement; this file is the interpretation laid next to it. It reads what
# color_live.py reads -- rgbi() on ports C and D -- and adds two columns:
#     * color()          the hub's BUILT-IN colour guess (a nearest-neighbour
#                         match against LEGO's eight brick colours -- known to
#                         miss on pastel matte paper: color-discrimination.md 2.2)
#     * OURS             our own classification from the r:g:b ratios
# Printing both next to the raw numbers is the whole point: it shows, per surface,
# whether the RATIOS separate the four surfaces the mission cares about and whether
# the built-in guess can be trusted for any of them.
#
# The four surfaces to separate (a downward sensor sees one at a time):
#     the floor  ·  a YELLOW STICKY NOTE (mine)  ·  BLUE tape (boundary)  ·  other
# The hard case named in the team transcript is BLUE TAPE vs a BLUE NOTE: two blue
# surfaces that ratios alone may not tell apart. When a reading is blue but not
# confidently the boundary tape, this reports UNKNOWN -- it never forces a class.
# A wrong colour stated confidently is worse than an honest UNKNOWN.
#
# NOT the real classifier. src/classify.py is the mission path: calibrated
# chromaticity centroids, nearest-centroid, three rejection gates
# (color-discrimination.md 4.3). That needs run-start calibration data this desk
# demo has none of, so this uses fixed placeholder thresholds instead. Its job is
# to let the operator eyeball separability at GATE 1, not to ship.
#
# WHAT TO DO WHILE IT RUNS
#   Hold each surface under sensor C in turn, ~16 mm away, and HOLD IT STILL for a
#   few seconds so a stable block of rows appears. Note out loud which is which --
#   the log has no idea. Then check: does OURS agree with the surface you are
#   holding? Do two different surfaces ever print the same ratios?
#
# READ-ONLY: reads sensors, commands NO motion. Safe on a desk.
# MicroPython: no f-strings, no statistics, no numpy, no enum, no typing.

import time
import color_sensor
import color
from hub import port

PORTS = (("C", port.C), ("D", port.D))
PERIOD_MS = 250

# --- classification thresholds, in chromaticity units (percent of r+g+b) ---
# [UNVERIFIED] -- every number below is a placeholder SHAPE, not a tuning. It is
# guessed from what yellow and blue "should" do to r:g:b, and MUST be replaced by
# real values once GATE 1 (color_live.py) measures floor / yellow note / blue tape
# / silver tape on the actual arena, under the actual lights. Record the measured
# value next to the surface and lighting it came from, per CLAUDE.md.
MIN_TOTAL     = 5      # r+g+b below this: too little light to trust a ratio
                       #   -> UNKNOWN. The rgbi() scale is undocumented on SPIKE 3,
                       #   so this raw cutoff is itself [UNVERIFIED].
YELLOW_B_MAX  = 20.0   # yellow note: blue% at or below this ...
YELLOW_RG_MIN = 34.0   # ... AND both red% and green% at or above this
                       #   (yellow = red + green, so blue is starved)
BLUE_B_MIN    = 42.0   # blue tape: blue% at or above this ...
BLUE_R_MAX    = 26.0   # ... AND red% at or below this
BLUEISH_B_MIN = 34.0   # blue% above this but short of BLUE_B_MIN: blue, but not
                       #   confidently the boundary tape -> UNKNOWN. This is the
                       #   blue-tape-vs-blue-note guard band.
FLOOR_SPREAD  = 12.0   # floor: max(r%,g%,b%) - min(...) at or below this, i.e. a
                       #   near-neutral grey surface. [ASSUMED] the floor is
                       #   neutral; GATE 1 confirms or kills that.

# built-in colour code -> constant name, for the color() column
NAMES = {}
for _n in dir(color):
    if not _n.startswith("_"):
        NAMES[getattr(color, _n)] = _n


def name_of(code):
    return NAMES.get(code, "?")


def classify(tot, rp, gp, bp):
    # Returns a class name, or "UNKNOWN:<reason>" when the ratios do not place the
    # reading confidently. Same policy as src/classify.py -- reject, do not guess.
    if tot < MIN_TOTAL:
        return "UNKNOWN:low-signal"
    is_yellow = bp <= YELLOW_B_MAX and rp >= YELLOW_RG_MIN and gp >= YELLOW_RG_MIN
    is_blue = bp >= BLUE_B_MIN and rp <= BLUE_R_MAX
    if is_yellow and is_blue:
        return "UNKNOWN:ambiguous"       # signatures overlap -- cannot force one
    if is_yellow:
        return "yellow-note"
    if is_blue:
        return "blue-tape"
    if bp >= BLUEISH_B_MIN:
        return "UNKNOWN:blue?"           # blue, but not confidently the tape
    spread = max(rp, gp, bp) - min(rp, gp, bp)
    if spread <= FLOOR_SPREAD:
        return "floor"                   # near-neutral -- the background [ASSUMED]
    return "other"                       # distinctly coloured, but not a target


print("=" * 78)
print("COLOUR CLASSIFY -- GATE 1. Hold each surface under sensor C and keep it still.")
print("=" * 78)
print("")
print("  Surfaces that matter: floor | YELLOW note | BLUE tape | other")
print("  OURS is from the ratios, using [UNVERIFIED] placeholder thresholds.")
print("  It reports UNKNOWN (with a reason) rather than force an ambiguous class.")
print("  Compare OURS against the built-in 'name' column AND the surface in hand.")
print("")
print("   t(s)  P  clr name      refl |   r    g    b    i |  r%    g%    b%  | OURS")
print("  " + "-" * 74)

t0 = time.ticks_ms()

while True:
    t = time.ticks_diff(time.ticks_ms(), t0) / 1000.0
    for label, p in PORTS:
        try:
            c = color_sensor.color(p)
            refl = color_sensor.reflection(p)
            rgbi = color_sensor.rgbi(p)
        except Exception as e:
            print("  %5.1f  %s  READ FAILED %s" % (t, label, type(e).__name__))
            continue

        if rgbi is None:
            print("  %5.1f  %s  rgbi() returned None -- no reading this tick" % (t, label))
            continue

        r, g, b, i = rgbi[0], rgbi[1], rgbi[2], rgbi[3]
        tot = r + g + b
        if tot > 0:
            rp = 100.0 * r / tot
            gp = 100.0 * g / tot
            bp = 100.0 * b / tot
        else:
            rp = gp = bp = 0.0

        ours = classify(tot, rp, gp, bp)

        print("  %5.1f  %s  %4d %-9s %4d | %4d %4d %4d %4d | %5.1f %5.1f %5.1f | %s"
              % (t, label, c, name_of(c), refl, r, g, b, i, rp, gp, bp, ours))

    time.sleep_ms(PERIOD_MS)
