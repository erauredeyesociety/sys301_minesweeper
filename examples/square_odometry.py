# examples/square_odometry.py — UMBmark-style square drive to CALIBRATE odometry.
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/square_odometry.py
#
# *** THIS PROGRAM DRIVES THE ROBOT. IT COMMANDS MOTION. ***
# It drives a CLOSED SQUARE: four straight legs and four ~90-degree pivot turns,
# using motor_pair for both and the hub gyro's yaw to decide when each turn has
# reached 90 degrees ("closing" the turn on the gyro). Encoders and yaw are
# streamed every tick so the drive can be replayed offline.
#
#   NEEDS A CLEAR, FLAT SQUARE OF FLOOR ABOUT 1 m ON A SIDE.
#   DO NOT run it on a desk or bench with the wheels down -- it drives off the edge.
#   Keep hands and cables clear. Be ready to catch the robot or cut power.
#   The PHYSICAL leg length is UNKNOWN: wheel diameter is unmeasured (that is the
#   whole point of this run), so LEG_DEGREES is in MOTOR DEGREES, not mm, and the
#   real size on the floor depends on your wheels. When in doubt, start SMALL.
#
# HOW IT STAYS SAFE ON A DESK (the only safe way to run it off a cleared floor):
#   Prop the chassis up so BOTH DRIVE WHEELS ARE OFF THE SURFACE -- a book or a
#   block under the frame. Wheels-up, the straight legs just spin the wheels in
#   place and the pivot turns spin them opposite; there is no translation and
#   nothing to fall. This still exercises the encoders, the gyro, and the
#   turn-closing logic, so you can confirm drive direction, turn direction, and
#   units BEFORE you ever put it on the floor. Do this dry run first.
#
# [UNVERIFIED] NEVER RUN ON REAL HARDWARE. Written 2026-09-01 against the API
# surface read off our own hub (docs/findings/hub-api-surface-2026-09-01.md,
# harvest-20260901T101832.txt) and the documented call shapes in
# docs/research/spike3-api-reference.md. No motor_pair call in this project has
# ever executed. Treat every reported number as suspect until this has run once.
#
# WHY A SQUARE, and the full offline regression it feeds (D_eff from a tape-
# measured leg, track width b, UMBmark closure): docs/plans/analysis-motion-quality.md.
# This demo only DRIVES and REPORTS headline numbers and streams the raw rows.
# Run once with DIRECTION = 1 and once with -1 for the cw/ccw (Type A/B) pair.
#
# MicroPython notes: no f-strings, no statistics module, no numpy, no dataclasses.
# Plain % formatting and plain loops only.

import time
import motor
import motor_pair
from hub import port, motion_sensor

# --- Ports (MEASURED 2026-09-01: A and B are the two motors) -----------------
PAIR = motor_pair.PAIR_1
LEFT_PORT = port.A
RIGHT_PORT = port.B

# --- Square geometry (the two things you tune) -------------------------------
# LEG_DEGREES is MOTOR degrees per straight leg, because mm is not yet
# convertible (WHEEL_DIAMETER_MM is unmeasured). On a nominal ~56 mm wheel this
# is roughly 1 m; on a bigger wheel it is more. START SMALLER for a first floor
# run and scale up once you have watched one square.
LEG_DEGREES = 2000            # [ASSUMED] ~1 m on a Ø56 wheel; UNKNOWN in mm
TURN_TARGET_DDEG = 900        # 90.0 degrees, in DECIDEGREES (yaw unit, measured)
SIDES = 4                     # a square

# DIRECTION flips the whole square cw<->ccw. Run both to get the cw/ccw pair.
DIRECTION = 1                 # +1 or -1

# Sign knobs -- flip either if the dry run shows the robot driving BACKWARD or
# CURVING on a "straight" leg (one motor is mounted mirrored; which side is a
# Stage-2 finding, see hub_motors.py). Left/right = +1 means "positive motor
# velocity drives this wheel forward".
LEFT_SIGN = 1
RIGHT_SIGN = 1

# --- Speeds (deg/s; the hub's own ceiling is 930, measured) ------------------
DRIVE_SPEED = 200             # straight-leg wheel speed, deg/s -- gentle
TURN_SPEED = 150              # pivot wheel speed, deg/s -- gentle, less overshoot

# --- Timing ------------------------------------------------------------------
PERIOD_MS = 50                # poll/stream interval (~20 Hz), the telemetry rate
SETTLE_MS = 600               # after each turn stop, watch yaw coast to rest
COUNTDOWN_S = 5               # abort window before anything moves
# Safety caps so a stuck gyro or a wrong sign can NEVER spin forever.
LEG_TIMEOUT_MS = 20000        # a leg that hasn't finished by here is aborted
TURN_TIMEOUT_MS = 8000        # a turn that hasn't reached 90 by here is aborted


def norm_ddeg(d):
    # Wrap a decidegree DELTA into (-1800, 1800], so unwrapping across the
    # +/-180 deg (=+/-1800 ddeg) seam accumulates instead of jumping ~3600.
    a = d % 3600
    if a > 1800:
        a -= 3600
    return a


def port_has_motor(p):
    # None-safe: a getter on an empty port raises. No exception => a motor reads.
    try:
        motor.relative_position(p)
        return True
    except Exception:
        return False


def stream_row(tag, t_ms, enc_l, enc_r, raw_yaw, cum):
    # Raw values first: exactly what the hub reported, no interpretation. This
    # is the telemetry the offline analysis replays.
    print("  %-9s t=%6d ms | encL %8d encR %8d | yaw %6d ddeg  cum %8d ddeg"
          % (tag, t_ms, enc_l, enc_r, raw_yaw, cum))


def drive_leg(leg_index, cum, prev_raw):
    # Straight leg: both wheels forward. Stop when the MEAN of the two wheels'
    # |travel| reaches LEG_DEGREES. Mean-of-magnitudes is used on purpose so the
    # stop works whichever sign convention the wheels turn out to have; the raw
    # signed encoder values are still streamed for the analysis.
    base_l = motor.relative_position(LEFT_PORT)
    base_r = motor.relative_position(RIGHT_PORT)
    motor_pair.move_tank(PAIR, int(LEFT_SIGN * DRIVE_SPEED),
                         int(RIGHT_SIGN * DRIVE_SPEED))
    t0 = time.ticks_ms()
    d_l = 0
    d_r = 0
    timed_out = False
    while True:
        el = time.ticks_diff(time.ticks_ms(), t0)
        cur_l = motor.relative_position(LEFT_PORT)
        cur_r = motor.relative_position(RIGHT_PORT)
        d_l = cur_l - base_l
        d_r = cur_r - base_r
        raw = motion_sensor.tilt_angles()[0]
        cum = cum + norm_ddeg(raw - prev_raw)
        prev_raw = raw
        stream_row("leg %d" % leg_index, el, cur_l, cur_r, raw, cum)
        progress = (abs(d_l) + abs(d_r)) // 2
        if progress >= LEG_DEGREES:
            break
        if el >= LEG_TIMEOUT_MS:
            timed_out = True
            break
        time.sleep_ms(PERIOD_MS)
    motor_pair.stop(PAIR)
    return cum, prev_raw, d_l, d_r, el, timed_out


def pivot_turn(turn_index, cum, prev_raw):
    # Pivot in place: one wheel forward, one back. Stop when the accumulated yaw
    # for THIS corner reaches 90 deg in magnitude -- the gyro closes the turn.
    # Magnitude, again, so it works whatever sign the yaw moves; the signed
    # achieved angle is what we report.
    cum_start = cum
    l_vel = int(LEFT_SIGN * TURN_SPEED * DIRECTION)
    r_vel = int(-RIGHT_SIGN * TURN_SPEED * DIRECTION)
    motor_pair.move_tank(PAIR, l_vel, r_vel)
    t0 = time.ticks_ms()
    timed_out = False
    while True:
        el = time.ticks_diff(time.ticks_ms(), t0)
        raw = motion_sensor.tilt_angles()[0]
        cum = cum + norm_ddeg(raw - prev_raw)
        prev_raw = raw
        stream_row("turn %d" % turn_index, el,
                   motor.relative_position(LEFT_PORT),
                   motor.relative_position(RIGHT_PORT), raw, cum)
        if abs(cum - cum_start) >= TURN_TARGET_DDEG:
            break
        if el >= TURN_TIMEOUT_MS:
            timed_out = True
            break
        time.sleep_ms(PERIOD_MS)
    motor_pair.stop(PAIR)
    # Settle: motors are stopped, but the robot coasts/brakes. Keep tracking yaw
    # so the achieved angle includes overshoot -- the overshoot IS the error.
    ts = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), ts) < SETTLE_MS:
        el = time.ticks_diff(time.ticks_ms(), ts)
        raw = motion_sensor.tilt_angles()[0]
        cum = cum + norm_ddeg(raw - prev_raw)
        prev_raw = raw
        stream_row("settle %d" % turn_index, el,
                   motor.relative_position(LEFT_PORT),
                   motor.relative_position(RIGHT_PORT), raw, cum)
        time.sleep_ms(PERIOD_MS)
    achieved = cum - cum_start
    return cum, prev_raw, achieved, timed_out


print("=" * 74)
print("SQUARE DRIVE -- UMBmark-style odometry calibration.  THIS ROBOT MOVES.")
print("=" * 74)
print("")
print("  Needs a clear ~1 m square of flat floor, OR the wheels propped up off a")
print("  desk (see the file header). LEG_DEGREES=%d motor deg per leg, DIRECTION=%d,"
      % (LEG_DEGREES, DIRECTION))
print("  drive %d deg/s, turn %d deg/s, 90 deg target = %d ddeg."
      % (DRIVE_SPEED, TURN_SPEED, TURN_TARGET_DDEG))
print("")

# Refuse to pair/drive unless BOTH motor ports actually answer -- pairing an
# empty port and driving one wheel is how a bench test lurches off a table.
if not (port_has_motor(LEFT_PORT) and port_has_motor(RIGHT_PORT)):
    print("  *** ABORT: both motors must read on their ports before this can run.")
    print("      LEFT_PORT motor present:  %r" % port_has_motor(LEFT_PORT))
    print("      RIGHT_PORT motor present: %r" % port_has_motor(RIGHT_PORT))
    print("      Nothing was driven. Check the port map and re-run.")
else:
    print("  Both motors read. Starting in %d s -- LIFT IT or CLEAR THE FLOOR NOW."
          % COUNTDOWN_S)
    for s in range(COUNTDOWN_S, 0, -1):
        print("    %d..." % s)
        time.sleep_ms(1000)
    print("  GO.\n")
    print("  Streaming raw encoders and yaw every ~%d ms:" % PERIOD_MS)

    legs = []
    turns = []
    cum = 0
    # Seed the heading reference from the first reading -- no reset_yaw needed,
    # since we only ever use yaw DIFFERENCES. cum is heading relative to start.
    prev_raw = motion_sensor.tilt_angles()[0]
    print("  (heading reference seeded at raw yaw = %d ddeg)\n" % prev_raw)

    try:
        motor_pair.pair(PAIR, LEFT_PORT, RIGHT_PORT)
        for side in range(1, SIDES + 1):
            cum, prev_raw, d_l, d_r, el, lto = drive_leg(side, cum, prev_raw)
            legs.append((d_l, d_r, el, lto))
            cum, prev_raw, achieved, tto = pivot_turn(side, cum, prev_raw)
            turns.append((achieved, tto))
    finally:
        # Safety net: always stop and release, even on an exception or Ctrl-C.
        try:
            motor_pair.stop(PAIR)
            motor_pair.unpair(PAIR)
        except Exception:
            pass

    print("\n" + "=" * 74)
    print("RESULTS")
    print("=" * 74)

    print("\n--- STRAIGHT LEGS (motor degrees) ---")
    print("  leg   encL      encR    R/L      ms   note")
    for k in range(len(legs)):
        d_l, d_r, el, lto = legs[k]
        if d_l != 0:
            ratio = float(d_r) / float(d_l)
            ratio_s = "%6.3f" % ratio
        else:
            ratio_s = "   n/a"
        note = "TIMED OUT" if lto else ""
        print("   %2d  %8d  %8d  %s  %6d   %s"
              % (k + 1, d_l, d_r, ratio_s, el, note))
    print("  R/L offset from 1.0 = diameter-mismatch signature; one tape-measured")
    print("  leg turns encL/encR into D_eff (host-side, analysis-motion-quality.md).")

    print("\n--- PIVOT TURNS (gyro-closed, decidegrees) ---")
    print("  turn  achieved   |achieved|   err vs 90   note")
    corner_err_sum = 0
    running = 0
    for k in range(len(turns)):
        achieved, tto = turns[k]
        err = abs(achieved) - TURN_TARGET_DDEG   # + = overshoot, - = undershoot
        corner_err_sum += err
        running += err
        note = "TIMED OUT (stuck gyro? wrong dir?)" if tto else ""
        print("   %2d   %8d   %8d    %+8d   (run %+d)  %s"
              % (k + 1, achieved, abs(achieved), err, running, note))
    if len(turns) > 0:
        print("  accumulated corner error: %+d ddeg total, %+.1f ddeg/corner mean"
              % (corner_err_sum, float(corner_err_sum) / len(turns)))
    print("  err = |achieved| - 90deg (+ overshoot, - undershoot). Sign vs cw/ccw")
    print("  is the Type A/B split -- run DIRECTION +1 and -1 and compare.")

    print("\n--- LOOP CLOSURE (UMBmark end-to-end) ---")
    ideal = SIDES * TURN_TARGET_DDEG          # 3600 ddeg for a 4-sided square
    closure = abs(cum) - ideal
    print("  final accumulated yaw : %+d ddeg = %+.1f deg" % (cum, cum / 10.0))
    print("  ideal for %d corners   : %d ddeg = %.1f deg (sign follows DIRECTION)"
          % (SIDES, ideal, ideal / 10.0))
    print("  closure error         : %+d ddeg = %+.1f deg" % (closure, closure / 10.0))
    print("  Whether the geometry COMPOSES round the loop -- NOT position error,")
    print("  which needs the wheel constants (host-side, analysis-motion-quality.md).")

    any_timeout = False
    for _, _, _, lto in legs:
        if lto:
            any_timeout = True
    for _, tto in turns:
        if tto:
            any_timeout = True
    if any_timeout:
        print("\n  *** A leg or turn TIMED OUT. If turns timed out, check the raw yaw")
        print("      column above: if it never moved, the gyro was stuck (a known")
        print("      SPIKE pathology) and nothing here about heading is believable.")

print("\nDONE.")
