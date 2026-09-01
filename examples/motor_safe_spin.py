# examples/motor_safe_spin.py — the FIRST motor move: a small, slow, one-at-a-time spin.
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/motor_safe_spin.py
#
# *** THIS ONE COMMANDS MOTION. *** Every other example so far is read-only; this
# is not. Read the safety paragraph before running it.
#
# HOW IT STAYS SAFE ON A DESK
#   * LIFT THE ROBOT OR PUT IT ON BLOCKS first, so the wheels spin in free air and
#     the robot cannot drive off the bench. This is the whole safety story -- the
#     code cannot make an airborne wheel dangerous.
#   * SMALL fixed angle: STEP_DEG (90) motor output-shaft degrees per move. A
#     quarter turn, not a run across the room.
#   * SLOW: SPEED_DPS (100 deg/s) against a MEASURED ceiling of 930 deg/s -- about
#     11% of top speed, roughly one quarter-turn per second.
#   * ONE MOTOR AT A TIME, with a pause between, so the operator watches exactly
#     one wheel and nothing lurches.
#   * A try/finally stops every motor no matter how the run ends (AB2 degraded
#     mode: on any fault, stop the motors).
#   Because it moves the robot, this is a BUILDER-operated run on a built, LIFTED
#   robot -- never a bare-hub probe.
#
# WHY IT EARNS ITS KEEP
#   It proves the drive stack end to end -- discover motor -> command a move ->
#   the awaitable completes under runloop -> the encoder confirms it -- and it
#   returns the FIRST degrees-COMMANDED-vs-degrees-MOVED datum. It reads the
#   encoder (relative_position, cumulative degrees) BEFORE and AFTER each move and
#   prints the delta against the command, so the operator can see with their own
#   eyes that the wheel turned the amount asked for. That delta is the beginning
#   of the odometry error budget.
#
# PORTS ARE DISCOVERED, NOT HARD-CODED. It scans A-F and drives only ports whose
# device.id says a motor is there (ours read 48; 49/65 are the other angular
# motors, per probes/devices.py). If no motor answers, it drives nothing.
#
# [UNVERIFIED] Written against the API surface read off our own hub, not yet run.
# The run_for_degrees signature and the runloop idiom are confirmed from repo docs
# (docs/research/spike3-api-reference.md, operator platform notes); its exact
# return value / blocking semantics are [UNVERIFIED] until this run.
#
# MicroPython notes: no f-strings, no statistics module, no numpy.

import time
import motor
import device
import runloop
from hub import port

STEP_DEG = 90        # motor output-shaft degrees commanded per move -- a quarter turn
SPEED_DPS = 100      # deg/s. LOW on purpose; MEASURED ceiling is 930 deg/s
PAUSE_MS = 1500      # wait between motors, so one wheel is watched at a time
SETTLE_MS = 300      # let the shaft settle after a move before reading the encoder

# device.id() values that mean "a motor is here". Ours MEASURED 48 (Medium Angular
# 45603); 49 (Large) and 65 (Small) are the other angulars -- accepted so a swapped
# motor is still found rather than silently skipped. See probes/devices.py.
MOTOR_DEVICE_IDS = (48, 49, 65)

PORTS = [("A", port.A), ("B", port.B), ("C", port.C),
         ("D", port.D), ("E", port.E), ("F", port.F)]

# Reverse-map the motor status ints to their names, so the value run_for_degrees
# returns can be printed by NAME. Built from the hub's own constants -- the integer
# values are [UNVERIFIED] on our hub, so never hard-code them (spike3-api-reference).
STATUS_NAMES = {}
for _n in ["READY", "RUNNING", "STALLED", "CANCELLED", "ERROR", "DISCONNECTED"]:
    if hasattr(motor, _n):
        STATUS_NAMES[getattr(motor, _n)] = _n


def status_name(code):
    return STATUS_NAMES.get(code, "?")


def try_id(p):
    # device.id() raises on an empty port; that exception IS "nothing here".
    try:
        return device.id(p)
    except Exception:
        return None


print("=" * 66)
print("MOTOR SAFE SPIN -- this COMMANDS MOTION")
print("=" * 66)
print("")
print("  >>> LIFT THE ROBOT OR PUT IT ON BLOCKS BEFORE RUNNING. <<<")
print("  >>> The wheels WILL turn. Keep them off the ground.     <<<")
print("")
print("  Plan: %d deg at %d deg/s, one motor at a time, %d ms between."
      % (STEP_DEG, SPEED_DPS, PAUSE_MS))
print("  Encoder is read before and after each move to confirm it turned.")
print("")

print("--- 1. FIND THE MOTORS (device.id, no motion) ---")
found = []
for name, p in PORTS:
    did = try_id(p)
    if did is None:
        print("    port %s  empty" % name)
    elif did in MOTOR_DEVICE_IDS:
        print("    port %s  device.id=%d  MOTOR -- will spin" % (name, did))
        found.append((name, p))
    else:
        print("    port %s  device.id=%d  not a motor -- skipped" % (name, did))
print("  => %d motor(s) to drive: %s"
      % (len(found), ", ".join([n for n, p in found]) or "none"))


async def spin_one(name, p):
    # relative_position is cumulative motor-shaft degrees -- the right encoder for a
    # before/after delta (absolute_position wraps at ~+/-180 and would confuse it).
    before = motor.relative_position(p)
    print("")
    print("  port %s: encoder BEFORE = %d deg. Commanding +%d deg at %d deg/s ..."
          % (name, before, STEP_DEG, SPEED_DPS))
    # Awaitable under runloop. Positive degrees = clockwise seen from the motor top
    # (per-motor, NOT per-robot -- this demo makes no 'forward' claim). BRAKE default.
    result = await motor.run_for_degrees(p, STEP_DEG, SPEED_DPS)
    await runloop.sleep_ms(SETTLE_MS)
    after = motor.relative_position(p)
    moved = after - before
    print("  port %s: encoder AFTER  = %d deg  -> moved %d deg (commanded %d)"
          % (name, after, moved, STEP_DEG))
    print("           run_for_degrees returned %r (%s); miss = %d deg"
          % (result, status_name(result), moved - STEP_DEG))


async def spin_all():
    try:
        for i in range(len(found)):
            name, p = found[i]
            await spin_one(name, p)
            if i < len(found) - 1:
                print("  ...pausing %d ms..." % PAUSE_MS)
                await runloop.sleep_ms(PAUSE_MS)
    finally:
        # Stop every motor we found, whatever happened above (AB2 degraded mode).
        for name, p in found:
            try:
                motor.stop(p)
            except Exception:
                pass


print("")
print("--- 2. SPIN EACH MOTOR, SMALL AND SLOW ---")
if not found:
    print("  SKIPPED: no motor answered on any port. Nothing is driven.")
    print("  Plug a motor in and re-run. (Ports A and B held our motors last.)")
else:
    print("  Starting in 3 seconds -- last chance to confirm the robot is lifted.")
    time.sleep_ms(3000)
    runloop.run(spin_all())

print("")
print("  READING THIS: 'moved' should track 'commanded' (%d). A small, repeatable" % STEP_DEG)
print("  miss is backlash/control lag and becomes a calibration constant; a large")
print("  or random miss means the wheel slipped, stalled, or the encoder scale is")
print("  not 1:1 with output degrees. Either way this is the first real number.")
print("")
print("DONE.")
