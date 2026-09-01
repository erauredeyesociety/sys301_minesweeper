# examples/drive_straight_encoders.py — drive both wheels forward and watch them diverge.
#
# RUNS ON THE HUB.  ./hub_programmer/run.py examples/drive_straight_encoders.py --seconds 10
#
# *** THIS ONE MOVES THE ROBOT. *** It is the only example so far that commands
# motion, so read the safety notes before running it.
#
# WHY IT MOVES: track-width and heading calibration need RAW data on how far a
# straight-line command actually goes straight -- how much the two wheels
# diverge and how much the heading drifts per unit of wheel travel. A human
# turning a wheel by hand (motor_encoder_verbose.py) cannot give that; only a
# real, powered, timed move can. This is that move, kept as slow and short as it
# can be while still producing the numbers.
#
# HOW IT STAYS SAFE
#   * LOW SPEED: VELOCITY_DPS below is ~21% of the 930 deg/s ceiling the hub
#     reported for these motors (motor.info -> max_speed=930). Slow enough to
#     stop by hand.
#   * SHORT + CAPPED: it stops after DURATION_MS, and independently the instant
#     either wheel passes STOP_DEGREES of travel, so it cannot drive across a
#     room even if the timer logic is wrong.
#   * run.py's --seconds deadline sends Ctrl-C on expiry; the try/finally below
#     catches that (KeyboardInterrupt) and STOPS the motors. move_tank is a
#     "run until told otherwise" command, so WITHOUT that finally the wheels
#     would keep spinning after the program ends -- the finally is load-bearing.
#   * DESK / BENCH MODE: prop the two drive wheels off the table so they spin
#     free. You still get the encoder + sign data safely; only the yaw/straight-
#     line reading needs the robot on a floor with a clear ~2 m runway.
#   * FLOOR MODE: robot on the floor, ~2 m clear ahead, a hand ready to catch it.
#
# THE MIRRORED-MOTOR PROBLEM THIS EXPOSES
#   One drive motor is mounted mirror-imaged, so a single "positive" command can
#   spin the wheels in physically OPPOSITE senses -- +VELOCITY to both may make
#   the robot SPIN IN PLACE instead of going straight. Which side needs its sign
#   flipped is the UNVERIFIED flip carried in src/hub_motors.py, so each side's
#   sign is a CONSTANT below (LEFT_SIGN / RIGHT_SIGN). Section 4's output tells
#   you which combination drives straight and which side to record in hub_motors.py.
#
# READS: both motor encoders (relative_position, velocity) + IMU yaw (tilt yaw).
# MicroPython notes: no f-strings, no statistics, no numpy. % formatting only.
# This file lives in examples/ on purpose -- it touches the LEGO API, which the
# src/ purity rule forbids there but explicitly allows here.

import time
import motor
import motor_pair
import device
import hub
from hub import port

# --- Tuning. All slow/short on purpose; a moving demo earns no benefit of doubt.
VELOCITY_DPS = 200      # deg/s per wheel. ~21% of the measured 930 deg/s ceiling.
DURATION_MS = 3000      # hard time limit for the powered move.
STOP_DEGREES = 720      # travel cap: stop the instant EITHER wheel passes this
                        # (~2 wheel revs). Independent runaway guard.
PERIOD_MS = 100         # encoder/yaw sample interval.
PRINT_EVERY = 2         # print one row in this many samples.

# The mirrored-mount sign per side. Start both +1; if the robot spins instead of
# rolling, set ONE of these to -1 and re-run. This is the whole experiment.
LEFT_SIGN = 1
RIGHT_SIGN = 1

PAIR = motor_pair.PAIR_1        # [UNVERIFIED] pairing slot; PAIR_1/2/3 exist per dir().

# decidegrees: yaw wraps at +/-180 deg == +/-1800 decidegrees (MEASURED units).
YAW_HALF = 1800

PORTS = [("A", port.A), ("B", port.B), ("C", port.C),
         ("D", port.D), ("E", port.E), ("F", port.F)]

m = hub.motion_sensor


def try_read(fn, arg):
    # Empty port, or a non-motor, raises. None means "no answer", never 0.
    try:
        return fn(arg)
    except Exception:
        return None


def normalize(a):
    # Shortest-signed decidegree difference across the +/-180 deg wrap.
    while a > YAW_HALF:
        a -= 2 * YAW_HALF
    while a < -YAW_HALF:
        a += 2 * YAW_HALF
    return a


print("=" * 72)
print("DRIVE STRAIGHT + ENCODERS -- THIS MOVES THE ROBOT. Clear the floor.")
print("=" * 72)

print("\n--- 1. WHAT EXISTS (confirm the call names on THIS hub before calling) ---")
print("  motor_pair: " + ", ".join([a for a in dir(motor_pair) if not a.startswith("_")]))

print("\n--- 2. FIND THE MOTORS (ports are discovered, never hard-coded) ---")
found = []
for name, p in PORTS:
    abs_pos = try_read(motor.absolute_position, p)
    info = try_read(motor.info, p)
    print("    port %s  device.id=%-6s  %s"
          % (name, repr(try_read(device.id, p)),
             "no motor" if abs_pos is None
             else "MOTOR, info=%r" % (info,)))
    if abs_pos is not None:
        found.append((name, p))
print("  => %d motor(s): %s" % (len(found), ", ".join([n for n, p in found]) or "none"))

if len(found) != 2:
    print("\nSKIPPED THE DRIVE: a differential drive needs exactly 2 motors, found %d."
          % len(found))
    print("NOTHING WAS COMMANDED TO MOVE. Plug in both drive motors and re-run.")
    print("\nDONE.")
else:
    # First discovered port is the LEFT candidate; which is physically left is
    # itself unknown and is one of the things the run reveals.
    left_name, left_p = found[0]
    right_name, right_p = found[1]

    print("\n--- 3. POWERED MOVE -- LOW SPEED, %d ms, %d deg/s per wheel ---"
          % (DURATION_MS, VELOCITY_DPS))
    print("  LEFT  candidate = port %s  (command sign %+d)" % (left_name, LEFT_SIGN))
    print("  RIGHT candidate = port %s  (command sign %+d)" % (right_name, RIGHT_SIGN))
    print("  Watch yaw_d: near-flat = straight; a steady sweep = spinning -> flip a sign.")
    print("  Starting in 3 seconds. Hand ready.")
    time.sleep_ms(3000)

    yaw0 = m.tilt_angles()[0]
    base_l = motor.relative_position(left_p)
    base_r = motor.relative_position(right_p)
    print("\n  baseline: yaw0=%d ddeg  rel L=%d  rel R=%d  (raw hub values)"
          % (yaw0, base_l, base_r))
    print("      ms |   L rel   L vel |   R rel   R vel |    yaw   yaw_d")

    l_net = 0
    r_net = 0
    stop_reason = "loop fell through"
    try:
        # [UNVERIFIED] motor_pair.pair(pair, left, right): groups the two ports.
        motor_pair.pair(PAIR, left_p, right_p)
        # [UNVERIFIED] motor_pair.move_tank(pair, left_dps, right_dps): expected to
        # be the NON-BLOCKING "run until told otherwise" tank command (mirrors
        # motor.run). If instead it only works awaited inside runloop, the wheels
        # will NOT move and no error will show -- that null result is itself a
        # finding (we would then need runloop.run). Units expected deg/s;
        # acceleration left at its default.
        motor_pair.move_tank(PAIR, LEFT_SIGN * VELOCITY_DPS, RIGHT_SIGN * VELOCITY_DPS)

        t0 = time.ticks_ms()
        i = 0
        while True:
            elapsed = time.ticks_diff(time.ticks_ms(), t0)
            l_net = motor.relative_position(left_p) - base_l
            r_net = motor.relative_position(right_p) - base_r
            l_vel = motor.velocity(left_p)
            r_vel = motor.velocity(right_p)
            yaw = m.tilt_angles()[0]
            yaw_d = normalize(yaw - yaw0)

            if i % PRINT_EVERY == 0:
                print("  %6d | %7d %7d | %7d %7d | %6d %7d"
                      % (elapsed, l_net, l_vel, r_net, r_vel, yaw, yaw_d))

            if elapsed >= DURATION_MS:
                stop_reason = "reached DURATION_MS (%d ms)" % DURATION_MS
                break
            if abs(l_net) >= STOP_DEGREES or abs(r_net) >= STOP_DEGREES:
                stop_reason = "hit STOP_DEGREES travel cap (%d deg)" % STOP_DEGREES
                break

            i += 1
            time.sleep_ms(PERIOD_MS)
    finally:
        # Load-bearing: move_tank keeps running until stopped, and a Ctrl-C from
        # run.py's deadline lands here as KeyboardInterrupt. Stop every way we can.
        try:
            motor_pair.stop(PAIR)
        except Exception:
            pass
        try:
            motor.stop(left_p)
        except Exception:
            pass
        try:
            motor.stop(right_p)
        except Exception:
            pass
        print("  MOTORS COMMANDED TO STOP.")

    yaw_end = normalize(m.tilt_angles()[0] - yaw0)

    print("\n--- 4. WHAT THAT MEASURED ---")
    print("  stopped because: %s" % stop_reason)
    print("  net travel:  L(port %s) = %d deg   R(port %s) = %d deg"
          % (left_name, l_net, right_name, r_net))
    print("  divergence:  L - R = %d deg  (0 = wheels turned equally)"
          % (l_net - r_net))
    print("  heading:     yaw moved %d decidegrees (%.1f deg) start-to-end"
          % (yaw_end, yaw_end / 10.0))

    print("\n  READING IT:")
    print("   * yaw small, both wheels rolled the same physical way -> ~straight;")
    print("     LEFT_SIGN/RIGHT_SIGN (%+d/%+d) are correct." % (LEFT_SIGN, RIGHT_SIGN))
    print("   * yaw swept steadily / spun on the spot -> mirrored motor fighting:")
    print("     flip ONE sign and re-run. The side whose net travel is the WRONG")
    print("     sign for the way it drove is the one to flip; record which side")
    print("     counts UP under a positive command in src/hub_motors.py.")
    print("   * both wheels moved, net L != net R, yaw drifting -> that mismatch")
    print("     over this travel is the raw input for track-width + heading calib.")
    print("     Re-run a few times; carry the numbers, not a conclusion, to docs/findings/.")
    print("   * neither wheel moved, nothing raised -> move_tank likely needs")
    print("     runloop; note that and switch approach. Not a broken motor.")
    print("\nDONE.")
