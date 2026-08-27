# examples/motor_encoder_verbose.py — everything a motor and its encoder will tell us, by hand.
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/motor_encoder_verbose.py --seconds 45
#
# [UNVERIFIED] NEVER RUN ON REAL HARDWARE. Written 2026-08-27 against the API
# surface read off our own hub (docs/archives/hub-baseline/03-api-surface.txt),
# not against a reading. Our two MEDIUM angular motors (45603) are going in as
# this is written and their PORTS ARE UNKNOWN -- which is why nothing here
# hard-codes a port. Delete this block once it has run and paste the real output
# into docs/findings/.
#
# IT NEVER COMMANDS MOTION -- every call below is a getter. No motor.run(), no
# run_for_degrees(), no run_for_time(), no set_duty_cycle(), no motor_pair.
# Driving a motor is the Builder's call on a built robot. A HUMAN turns the
# wheel instead: no calibration, no runaway, and three answers odometry needs.
#   * WHICH PORT IS WHICH -- the port whose count moves is the wheel your hand is on.
#   * WHICH WAY IS POSITIVE -- turn the wheel the way that drives the robot
#     forward, read the sign. hub_motors.py carries that flip as UNVERIFIED.
#   * UNITS PER WHEEL REVOLUTION -- net relative travel divided by counted
#     absolute_position wraps, instead of assuming 360.
#
# TWO THINGS IT TESTS RATHER THAN ASSUMES -- both [ASSUMED] until it runs:
#   (a) absolute_position() is bounded and wraps once per shaft revolution.
#       Section 5 prints its observed min/max, so the range is a measurement.
#   (b) relative_position() accumulates and does NOT wrap. If it does, its travel
#       total is not travel -- so a jump is counted and the per-rev derivation
#       is REFUSED rather than printed.
#
# MicroPython notes: no f-strings, no statistics module, no numpy.

import time
import motor
import device
from hub import port

STREAM_MS = 15000      # how long the hands-on-wheel phase lasts
PERIOD_MS = 100        # target interval between encoder samples
PRINT_EVERY = 5        # print one row in this many samples
WRAP_JUMP = 180        # a position jump bigger than this is a wrap, not a hand


PORTS = [("A", port.A), ("B", port.B), ("C", port.C),
         ("D", port.D), ("E", port.E), ("F", port.F)]
READERS = [("absolute_position", motor.absolute_position),
           ("relative_position", motor.relative_position),
           ("velocity", motor.velocity),
           ("get_duty_cycle", motor.get_duty_cycle),
           ("status", motor.status),
           ("info", motor.info)]


def try_read(fn, arg):
    # An empty port, or one holding something that is not a motor, raises.
    try:                       # None means "no answer", never 0.
        return fn(arg)
    except Exception:
        return None


print("=" * 62)
print("MOTOR + ENCODER DISCOVERY -- read only, nothing is driven")
print("=" * 62)

print("\n--- 1. WHAT EXISTS ---")
print("  motor:  " + ", ".join([a for a in dir(motor) if not a.startswith("_")]))
print("  device: " + ", ".join([a for a in dir(device) if not a.startswith("_")]))
print("\n  all six ports scanned, because ours are UNKNOWN:")
found = []
for name, p in PORTS:
    abs_pos = try_read(motor.absolute_position, p)
    print("    port %s  device.id=%-6s  %s"
          % (name, repr(try_read(device.id, p)),
             "no motor" if abs_pos is None
             else "MOTOR, absolute_position=%r" % (abs_pos,)))
    if abs_pos is not None:
        found.append((name, p))
print("  => %d motor(s): %s" % (len(found), ", ".join([n for n, p in found]) or "none"))
print("     Nothing else we own answers absolute_position(), so the device.id both\n"
      "     report IS the 45603's id -- a measurement. Put it in the port map.")

print("\n--- 2. ONE SAMPLE OF EACH, RAW ---")
print("  (units are what we are trying to LEARN -- nothing here is assumed)")
for name, p in found:
    print("  port %s:" % name)
    for label, fn in READERS:
        print("    %-22s %r" % (label + "()", try_read(fn, p)))

print("\n--- 3. CONSTANTS ---")
print("  the ints status() can carry, so a raw number above is decodable:")
for nm in ["READY", "RUNNING", "STALLED", "CANCELLED", "ERROR", "DISCONNECTED"]:
    if hasattr(motor, nm):
        print("    %-14s = %r" % (nm, getattr(motor, nm)))

print("\n--- 4. MANUAL TURN -- %d SECONDS, YOUR HAND ON THE WHEEL ---" % (STREAM_MS // 1000))
if not found:
    print("  SKIPPED: no motor answered on any port. Plug one in and re-run.")
else:
    print("    1. Put your hand on ONE wheel -- the one the team calls LEFT.")
    print("    2. Turn it the way that would drive the robot FORWARD.")
    print("    3. SLOWLY, steadily, ONE DIRECTION ONLY, several FULL turns.")
    print("  Slowly: more than half a shaft turn per %d ms sample and a wrap goes\n"
          "  uncounted. One direction: reversing adds travel without adding wraps.\n"
          "  reset_relative_position() is never called -- the baseline is subtracted\n"
          "  instead, leaving the hub's own count as we found it.\n"
          "  Starting in 3 seconds." % PERIOD_MS)
    time.sleep_ms(3000)

first_rel = [motor.relative_position(p) for name, p in found]
prev_abs = [motor.absolute_position(p) for name, p in found]
last_rel = list(first_rel)
abs_lo = list(prev_abs)
abs_hi = list(prev_abs)
path = [0] * len(found)
wraps = [0] * len(found)
rel_jumps = [0] * len(found)

if found:
    print("\n  baseline as found: rel=%r  abs=%r" % (first_rel, prev_abs))
    print("  rel and abs below are RAW hub values, offset by nothing.")
    hdr = "     ms"
    for name, p in found:
        hdr += " | %8s %6s %6s" % (name + " rel", "abs", "vel")
    print(hdr)

i = 0
t0 = time.ticks_ms()
while found and time.ticks_diff(time.ticks_ms(), t0) < STREAM_MS:
    line = "  %5d" % time.ticks_diff(time.ticks_ms(), t0)
    for k in range(len(found)):
        p = found[k][1]
        r = motor.relative_position(p)
        a = motor.absolute_position(p)
        d_abs = a - prev_abs[k]
        if d_abs < -WRAP_JUMP:
            wraps[k] += 1
        elif d_abs > WRAP_JUMP:
            wraps[k] -= 1
        d_rel = r - last_rel[k]
        if abs(d_rel) > WRAP_JUMP:
            rel_jumps[k] += 1
        path[k] += abs(d_rel)
        if a < abs_lo[k]:
            abs_lo[k] = a
        if a > abs_hi[k]:
            abs_hi[k] = a
        last_rel[k] = r
        prev_abs[k] = a
        line += " | %8d %6d %6d" % (r, a, motor.velocity(p))
    if i % PRINT_EVERY == 0:
        print(line)
    i += 1
    time.sleep_ms(PERIOD_MS)
elapsed_ms = time.ticks_diff(time.ticks_ms(), t0)

print("\n--- 5. WHAT THAT MEASURED ---")
if i > 0:
    print("  %d samples in %d ms => %.1f ms/sample actual, %d requested"
          % (i, elapsed_ms, float(elapsed_ms) / i, PERIOD_MS))
for k in range(len(found)):
    net = last_rel[k] - first_rel[k]
    print("\n  port %s  net rel %d | path %d | abs wraps %d | abs seen %d..%d"
          % (found[k][0], net, path[k], wraps[k], abs_lo[k], abs_hi[k]))
    print("    (abs seen is the MEASURED span -- the wrap width, never confirmed)")
    if path[k] == 0:
        print("    => NEVER MOVED. Not the wheel your hand was on.")
        continue
    if net > 0:
        print("    => turning FORWARD counts UP: positive = forward on port %s."
              % found[k][0])
    elif net < 0:
        print("    => turning FORWARD counts DOWN: port %s is the side needing the\n"
              "       sign flip hub_motors.py carries as UNVERIFIED." % found[k][0])
    print("       (true only for the wheel your hand was actually on)")
    if rel_jumps[k] > 0:
        print("    => per-revolution REFUSED: relative_position jumped more than %d\n"
              "       units %d time(s), so it wraps as well and its travel total is\n"
              "       not travel. That is itself a finding -- write it down."
              % (WRAP_JUMP, rel_jumps[k]))
        continue
    if wraps[k] == 0:
        print("    => per-revolution INCONCLUSIVE: absolute_position never wrapped.\n"
              "       Turn through at least two FULL revolutions and re-run.")
        continue
    if path[k] > (abs(net) * 6) // 5:
        print("    => per-revolution REFUSED: path %d exceeds net %d, so the wheel\n"
              "       reversed. Net wraps and total travel no longer describe the\n"
              "       same motion. Turn one direction only and re-run."
              % (path[k], abs(net)))
        continue
    per_rev = float(abs(net)) / abs(wraps[k])
    print("    => %.1f relative units per absolute_position wrap" % per_rev)
    if per_rev > 340.0 and per_rev < 380.0:
        print("       ~360, so one shaft revolution is 360 units and both position\n"
              "       readings share a single scale.")
    else:
        print("       NOT ~360: either gearing sits between encoder and wheel, or\n"
              "       wraps were missed because the turn outran %d ms sampling. Turn\n"
              "       slower and re-run before believing this number." % PERIOD_MS)

print("\n  WHY THIS MATTERS: odometry is (units / units_per_rev) * pi * diameter.\n"
      "  The per-rev figure above is the first of those two. The wheel diameter is\n"
      "  the other, and that one needs a ruler, not a script.")
print("\nDONE.")
