# examples/color_live.py — stream BOTH colour sensors so surfaces can be compared live.
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/color_live.py --seconds 90
#
# THIS IS GATE 1. It is the measurement that can invalidate the whole detection
# design, and it needs no robot -- just the sensors, the surfaces, and a hand.
#
# The mission must separate FOUR surfaces with a downward colour sensor:
#     the floor · a YELLOW STICKY NOTE (mine) · BLUE PAINTERS TAPE (boundary)
#     · SILVER/GREY DUCT TAPE (boundary)
# There is no GREY or SILVER constant in the `color` module, and silver tape is
# specular, so built-in colour ID may be the wrong instrument for it. That is
# what this run finds out.
#
# WHAT TO DO WHILE IT RUNS
#   Hold each surface under sensor C in turn, about 16 mm away, and HOLD IT
#   STILL for a few seconds so a stable block of rows appears for each. Say out
#   loud (or note the time) which surface is which -- the log has no idea.
#
# WHY IT PRINTS NORMALISED RATIOS TOO
#   Raw r/g/b move with distance, ambient light and battery. The RATIOS
#   r/(r+g+b) etc. mostly do not, so a threshold written in ratio units still
#   works tomorrow on a different floor. Raw values are printed as well because
#   the rgbi() RANGE is still unknown and only raw values can reveal it.
#
# READ-ONLY: reads sensors, commands no motion.
# MicroPython: no f-strings, no statistics, no numpy.

import time
import color_sensor
import color
from hub import port

PORTS = (("C", port.C), ("D", port.D))
PERIOD_MS = 250

NAMES = {}
for _n in dir(color):
    if not _n.startswith("_"):
        NAMES[getattr(color, _n)] = _n


def name_of(code):
    return NAMES.get(code, "?")


print("=" * 74)
print("COLOUR SENSORS -- LIVE. Hold each surface under sensor C and keep it still.")
print("=" * 74)
print("")
print("  Surfaces that matter: floor | YELLOW note | BLUE tape | SILVER tape")
print("  Watch the 'name' column and the r:g:b ratios, not the raw numbers.")
print("")
print("   t(s)  P  color name      refl |   r    g    b    i | r%%   g%%   b%%")
print("  " + "-" * 70)

t0 = time.ticks_ms()
seen_min = [9999, 9999, 9999, 9999]
seen_max = [0, 0, 0, 0]

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

        r, g, b, i = rgbi[0], rgbi[1], rgbi[2], rgbi[3]
        for k, v in enumerate((r, g, b, i)):
            if v < seen_min[k]:
                seen_min[k] = v
            if v > seen_max[k]:
                seen_max[k] = v

        tot = r + g + b
        if tot > 0:
            rp = 100.0 * r / tot
            gp = 100.0 * g / tot
            bp = 100.0 * b / tot
        else:
            rp = gp = bp = 0.0

        print("  %5.1f  %s  %4d %-9s %4d | %4d %4d %4d %4d | %4.1f %4.1f %4.1f"
              % (t, label, c, name_of(c), refl, r, g, b, i, rp, gp, bp))

    time.sleep_ms(PERIOD_MS)
